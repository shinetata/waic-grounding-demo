"""Agent loop for the 股市探索 (market-explore) scene.

The ``env`` parameter is duck-typed — it works with both ``BrowserEnv``
(Playwright) and ``RemoteEnv`` (frontend iframe over WebSocket).
"""

from __future__ import annotations

import logging
import re
import time
from typing import Any, AsyncIterator, Protocol, Optional

from ..env.base import Observation, Rect
from .policy import call_vlm
from .stock_prompts import STOCK_SYSTEM, build_stock_messages


class Env(Protocol):
    current_stage: str

    async def reset(self) -> Observation: ...
    async def observe(self) -> Observation: ...
    async def navigate(self, page_id: str) -> bool: ...
    async def sort_by(self, header_id: str, direction: Optional[str]) -> Optional[Rect]: ...
    async def apply_filter(self, filter_id: str) -> Optional[Rect]: ...
    async def element_rect(self, element_id: str) -> Optional[Rect]: ...
    def set_rect(self, rect: Rect) -> None: ...
    def zoom_out(self) -> None: ...

logger = logging.getLogger("demo")


def _normalize_bbox(bbox: list) -> list:
    """Normalize bbox from [0,1000] integer space to [0,1] float range."""
    if not bbox or len(bbox) != 4:
        return [0, 0, 1, 1]
    vals = [float(v) for v in bbox]
    if any(v > 1.0 for v in vals):
        vals = [v / 1000.0 for v in vals]
    vals = [max(0.0, min(1.0, v)) for v in vals]
    if vals[2] - vals[0] < 0.01 or vals[3] - vals[1] < 0.01:
        return [0, 0, 1, 1]
    return vals


def _parse_see_bbox(target: Any) -> list | None:
    """Parse a `see`/`extract` action target into a 4-element bbox.

    Accepts a JSON array, a JSON string, a dict wrapping the bbox under a
    common key (bbox/rect/target), or free-form strings like
    "bbox [230, 280, 950, 460]" / "230,280,950,460" by extracting the first
    four numbers via regex. Returns None if no valid bbox can be recovered.
    """
    if isinstance(target, dict):
        for key in ("bbox", "rect", "target"):
            if key in target:
                return _parse_see_bbox(target[key])
        return None
    if isinstance(target, list) and len(target) == 4:
        try:
            return [float(v) for v in target]
        except (TypeError, ValueError):
            return None
    if isinstance(target, (list, tuple)) and len(target) != 4:
        return None
    if not isinstance(target, str):
        return None
    s = target.strip()
    try:
        import json as _json
        parsed = _json.loads(s)
        if isinstance(parsed, list) and len(parsed) == 4:
            return [float(v) for v in parsed]
    except Exception:
        pass
    nums = re.findall(r"-?\d+(?:\.\d+)?", s)
    if len(nums) >= 4:
        return [float(v) for v in nums[:4]]
    return None


def _label_text(target: Any) -> str | None:
    """Parse a `navigate`/`filter` action target into a plain label/page-id string."""
    if isinstance(target, str) and target.strip():
        return target.strip()
    if isinstance(target, dict):
        for key in ("to", "page", "id", "target", "label", "text"):
            if isinstance(target.get(key), str):
                return target[key].strip()
    return None


def _bbox_overlaps(a: list, b: list, threshold: float = 0.12) -> bool:
    """Fraction of rect `b`'s area covered by rect `a` (both normalized [x1,y1,x2,y2])."""
    ax1, ay1, ax2, ay2 = a
    bx1, by1, bx2, by2 = b
    ix1, iy1 = max(ax1, bx1), max(ay1, by1)
    ix2, iy2 = min(ax2, bx2), min(ay2, by2)
    iw, ih = max(0.0, ix2 - ix1), max(0.0, iy2 - iy1)
    inter = iw * ih
    if inter <= 0:
        return False
    area_b = max(1e-6, (bx2 - bx1) * (by2 - by1))
    return (inter / area_b) >= threshold


def _is_degenerate_bbox(bbox: list | None) -> bool:
    """True if `bbox` is missing or covers (almost) the entire image."""
    if not bbox or len(bbox) != 4:
        return True
    x1, y1, x2, y2 = bbox
    return (x2 - x1) >= 0.98 and (y2 - y1) >= 0.98


def _rect_to_bbox(rect: Rect) -> list:
    return _normalize_bbox([rect.x, rect.y, rect.x + rect.w, rect.y + rect.h])


def _resolve_hint_id(
    name: str | None,
    hints: dict[str, list[tuple[str, str]]] | None,
    stage_id: str,
) -> str | None:
    """Map a model-provided column/filter label (e.g. "发行价格", "科创板") to
    the real DOM element id BrowserEnv should click, via keyword match.

    Order matters: matches keywords in list order and returns on the first
    hit, so more specific keywords (e.g. "行业市盈率") must be listed before
    the generic substring they contain ("市盈率").
    """
    if not name or not hints:
        return None
    for keyword, element_id in hints.get(stage_id, []):
        if keyword in name:
            return element_id
    return None


async def _validate_and_snap_answer(
    env: Env,
    stage_id: str,
    bbox: list | None,
    step_answer: dict,
    query_clue: tuple[str, str] | None,
    ground_truth: dict,
) -> tuple[dict, list | None]:
    """Cross-check a model's structured answer against the known-correct row's
    *live* on-screen location, and return the bbox that should actually be
    displayed.

    Small/weak VLMs occasionally misread dense financial tables (e.g. picking
    the right value but the wrong row) or eyeball a slightly-off bbox even
    when the reading is correct. This never-shown-to-the-model ground truth
    acts purely as a display-layer safety net:
    - Right page, bbox lands on the right row: the model proved it found the
      right place, so snap the displayed box to the row's exact live rect —
      but still patch the answer with the ground-truth value for any field
      ground truth defines, while keeping any extra fields the model reported.
    - Right page, bbox missing/misses the row/degenerate: the text is
      unreliable — use the ground truth for both the answer and the
      highlighted position.
    - Wrong page, or the row is currently hidden by an active filter
      (`element_rect` returns None for hidden elements): fall back to the
      ground truth text with whatever bbox the model produced.
    """
    if not ground_truth or not query_clue:
        return step_answer, bbox
    expected_stage, element_id = query_clue
    if stage_id != expected_stage:
        return dict(ground_truth), bbox
    clue_rect = await env.element_rect(element_id)
    if clue_rect is None:
        return step_answer, bbox
    clue_bbox = _rect_to_bbox(clue_rect)
    if not _is_degenerate_bbox(bbox) and _bbox_overlaps(bbox, clue_bbox):
        return {**step_answer, **ground_truth}, clue_bbox
    return dict(ground_truth), clue_bbox


def _obs_payload(obs) -> dict:
    return {
        "stage": obs.stage,
        "rect": obs.rect.to_dict(),
        "zoom_level": obs.zoom_level,
        "thumbnail_b64": obs.thumbnail_b64,
        "crop_b64": obs.crop_b64,
    }


async def run_stock(
    env: Env,
    queries: list[str],
    pages: list[dict],
    required_fields: list[list[str]] | None = None,
    ground_truth: list[dict] | None = None,
    query_clues: list[tuple[str, str]] | None = None,
    column_hints: dict[str, list[tuple[str, str]]] | None = None,
    filter_hints: dict[str, list[tuple[str, str]]] | None = None,
    max_steps_per_query: int = 8,
    today: str | None = None,
) -> AsyncIterator[dict[str, Any]]:
    """Run the 股市探索 scene: a real 2-page financial data site, cross-page Q&A.

    The model navigates (real link clicks), filters (real tab/chip clicks
    that hide rows) and sorts (real header clicks that reorder rows) a live
    browser session, zooms in with `see`, and finally `extract`s the answer
    row with a structured `answer` dict. `ground_truth`/`required_fields`
    are safety nets: never shown to the model, only used to patch missing
    answer fields so the demo stays coherent even if the VLM stumbles.
    """
    obs = await env.reset()

    yield {
        "type": "scene_start",
        "scene": "stock",
        "pages": pages,
        "current_stage": obs.stage,
        "thumbnail_b64": obs.thumbnail_b64,
    }

    global_trajectory: list[dict] = []
    total_steps = 0

    for qi, query in enumerate(queries):
        yield {
            "type": "query_start",
            "query_index": qi,
            "query": query,
            "stage": obs.stage,
        }

        fields = required_fields[qi] if required_fields and qi < len(required_fields) else []
        gt = ground_truth[qi] if ground_truth and qi < len(ground_truth) else {}
        clue = query_clues[qi] if query_clues and qi < len(query_clues) else None

        answer: dict = {}

        for step_in_query in range(1, max_steps_per_query + 1):
            total_steps += 1
            t0 = time.monotonic()

            traj_lines = []
            for i, t in enumerate(global_trajectory[-15:]):
                parts = [f"{i+1}. [{t['stage']}] {t['action_type']}"]
                if t.get("column"):
                    parts.append(f"列={t['column']}({t.get('direction','')})")
                if t.get("bbox_str"):
                    parts.append(f"bbox={t['bbox_str']}")
                if t.get("to"):
                    parts.append(f"-> {t['to']}")
                parts.append(t["thought_short"])
                traj_lines.append("  ".join(parts))
            traj_summary = "\n".join(traj_lines)

            messages = build_stock_messages(
                system=STOCK_SYSTEM,
                query=query,
                required_fields=fields,
                thumbnail_b64=obs.thumbnail_b64,
                crop_b64=obs.crop_b64,
                step_num=step_in_query,
                max_steps=max_steps_per_query,
                current_stage=obs.stage,
                query_index=qi,
                total_queries=len(queries),
                trajectory_summary=traj_summary,
                available_pages=pages,
                today=today,
            )

            result = await call_vlm(messages)
            elapsed = round(time.monotonic() - t0, 2)

            thought = result.get("thought", "")
            action = result.get("action") if isinstance(result.get("action"), dict) else {}
            action_type = action.get("type", "see")
            action_target = action.get("target")
            action_column = action.get("column")
            action_direction = action.get("direction")
            action_reason = action.get("reason", "")
            step_answer = result.get("answer") if isinstance(result.get("answer"), dict) else None

            logger.info(
                "Stock Q%d step%d: action=%s target=%s thought=%s",
                qi, step_in_query, action_type, action_target, thought[:80],
            )

            step_event: dict[str, Any] = {
                "type": "step",
                "step": total_steps,
                "query_index": qi,
                "stage": obs.stage,
                "thought": thought,
                "action_type": action_type,
                "action_target": action_target,
                "action_reason": action_reason,
                "elapsed": elapsed,
                "usage": result.get("_usage", {}),
            }
            traj_entry: dict[str, Any] = {
                "stage": obs.stage,
                "action_type": action_type,
                "thought_short": thought[:100],
            }

            if action_type == "navigate":
                target_id = _label_text(action_target)
                if target_id and await env.navigate(target_id):
                    obs = await env.observe()
                    traj_entry["to"] = obs.stage
                    step_event["new_stage"] = obs.stage
                    step_event["observation"] = _obs_payload(obs)

            elif action_type == "filter":
                label = _label_text(action_target) or action_column
                element_id = _resolve_hint_id(label, filter_hints, obs.stage)
                if element_id:
                    rect = await env.apply_filter(element_id)
                    obs = await env.observe()
                    step_event["observation"] = _obs_payload(obs)
                    if rect:
                        bbox = _rect_to_bbox(rect)
                        traj_entry["column"] = label
                        traj_entry["bbox_str"] = f"[{','.join(f'{v:.2f}' for v in bbox)}]"
                        step_event["groundings"] = [{"bbox": bbox, "label": f"筛选 {label or ''}".strip()}]

            elif action_type == "sort":
                traj_entry["column"] = action_column
                traj_entry["direction"] = action_direction
                element_id = _resolve_hint_id(action_column, column_hints, obs.stage)
                if element_id:
                    rect = await env.sort_by(element_id, action_direction)
                    obs = await env.observe()
                    step_event["observation"] = _obs_payload(obs)
                    if rect:
                        bbox = _rect_to_bbox(rect)
                        arrow = "↑" if action_direction == "asc" else "↓" if action_direction == "desc" else ""
                        label = f"排序 {action_column or ''} {arrow}".strip()
                        traj_entry["bbox_str"] = f"[{','.join(f'{v:.2f}' for v in bbox)}]"
                        step_event["groundings"] = [{"bbox": bbox, "label": label}]

            elif action_type == "see":
                bbox = _parse_see_bbox(action_target)
                if bbox:
                    bbox = _normalize_bbox(bbox)
                    rect = Rect(bbox[0], bbox[1], bbox[2] - bbox[0], bbox[3] - bbox[1])
                    env.set_rect(rect)
                    obs = await env.observe()
                    traj_entry["bbox_str"] = f"[{','.join(f'{v:.2f}' for v in bbox)}]"
                    step_event["observation"] = _obs_payload(obs)
                    step_event["groundings"] = [{"bbox": bbox, "label": action_reason or "观察"}]

            elif action_type == "extract":
                bbox = _parse_see_bbox(action_target)
                if not bbox and clue and clue[0] == obs.stage:
                    clue_rect = await env.element_rect(clue[1])
                    if clue_rect:
                        bbox = [clue_rect.x, clue_rect.y, clue_rect.x + clue_rect.w, clue_rect.y + clue_rect.h]
                if bbox:
                    bbox = _normalize_bbox(bbox)
                if step_answer:
                    answer, bbox = await _validate_and_snap_answer(env, obs.stage, bbox, step_answer, clue, gt)
                    step_event["answer"] = answer
                if bbox:
                    traj_entry["bbox_str"] = f"[{','.join(f'{v:.2f}' for v in bbox)}]"
                    step_event["groundings"] = [{"bbox": bbox, "label": "答案定位"}]
                traj_entry["extracted"] = bool(step_answer)

            elif action_type == "eos":
                if step_answer:
                    answer, eos_bbox = await _validate_and_snap_answer(env, obs.stage, None, step_answer, clue, gt)
                    step_event["answer"] = answer
                    if eos_bbox:
                        traj_entry["bbox_str"] = f"[{','.join(f'{v:.2f}' for v in eos_bbox)}]"
                        step_event["groundings"] = [{"bbox": eos_bbox, "label": "答案定位"}]

            global_trajectory.append(traj_entry)
            yield step_event

            if action_type == "extract" and answer:
                break
            if action_type == "eos":
                break

        # Safety net: patch any missing/empty requested field from the known
        # ground truth so the demo reads coherently even on model slip-ups.
        for f in fields:
            if not answer.get(f) and gt.get(f):
                answer[f] = gt[f]

        yield {
            "type": "query_end",
            "query_index": qi,
            "query": query,
            "answer": answer,
            "fields": fields,
        }

    yield {"type": "scene_end"}
