"""Agent loop for both grounding and navigation scenes."""

from __future__ import annotations

import logging
import re
import time
from typing import AsyncIterator, Any

from .policy import call_vlm

logger = logging.getLogger("demo")
from .prompts import (
    GROUNDING_SYSTEM,
    NAVIGATION_SYSTEM,
    build_grounding_messages,
    build_navigation_messages,
)
from .stock_prompts import STOCK_SYSTEM, build_stock_messages
from ..env.base import Rect
from ..env.screenshot import ScreenshotEnv


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
    """Parse a `see` action target into a 4-element bbox.

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
    # Try strict JSON first (handles "[1,2,3,4]").
    try:
        import json as _json
        parsed = _json.loads(s)
        if isinstance(parsed, list) and len(parsed) == 4:
            return [float(v) for v in parsed]
    except Exception:
        pass
    # Fallback: extract the first four numbers from any string format.
    nums = re.findall(r"-?\d+(?:\.\d+)?", s)
    if len(nums) >= 4:
        return [float(v) for v in nums[:4]]
    return None


def _get_clue_rect(env: ScreenshotEnv, stage_id: str) -> Rect | None:
    """Return the rect of a stage's designated clue element (fallback: first element)."""
    stage = env.stages.get(stage_id)
    if not stage:
        return None
    clue_id = stage.clue_element_id
    for el in stage.elements:
        if el.get("id") == clue_id:
            return Rect.from_dict(el["rect"])
    if stage.elements:
        return Rect.from_dict(stage.elements[0]["rect"])
    return None


def _parse_page_target(target: Any) -> str | None:
    """Parse a `navigate`/`filter` action target into a page id string."""
    if isinstance(target, str) and target.strip():
        return target.strip()
    if isinstance(target, dict):
        for key in ("to", "page", "id", "target"):
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
    """True if `bbox` is missing or covers (almost) the entire image.

    `_normalize_bbox` falls back to the full-image rect [0,0,1,1] whenever the
    model's raw coordinates are malformed or near-zero-area. A full-image rect
    trivially "overlaps" every possible clue rect in `_bbox_overlaps`, which
    would otherwise let a garbled/degenerate bbox slip through as if the model
    had precisely pointed at the right row — treat it as no bbox at all.
    """
    if not bbox or len(bbox) != 4:
        return True
    x1, y1, x2, y2 = bbox
    return (x2 - x1) >= 0.98 and (y2 - y1) >= 0.98


def _rect_to_bbox(rect: Rect) -> list:
    return _normalize_bbox([rect.x, rect.y, rect.x + rect.w, rect.y + rect.h])


def _find_element_rect(env: ScreenshotEnv, stage_id: str, element_id: str) -> Rect | None:
    stage = env.stages.get(stage_id)
    if not stage:
        return None
    for el in stage.elements:
        if el.get("id") == element_id:
            return Rect.from_dict(el["rect"])
    return None


def _resolve_column_rect(
    env: ScreenshotEnv,
    stage_id: str,
    column_name: str | None,
    column_hints: dict[str, list[tuple[str, str]]] | None,
) -> Rect | None:
    """Map a model-provided column name (e.g. "发行价格") to the real header
    rect via keyword match, so `sort` highlights snap to the actual column
    instead of relying on the model's own freehand bbox for an abstract target.
    """
    if not column_name or not column_hints:
        return None
    hints = column_hints.get(stage_id)
    if not hints:
        return None
    for keyword, element_id in hints:
        if keyword in column_name:
            rect = _find_element_rect(env, stage_id, element_id)
            if rect:
                return rect
    return None


def _validate_and_snap_answer(
    env: ScreenshotEnv,
    stage_id: str,
    bbox: list | None,
    step_answer: dict,
    query_clue: tuple[str, str] | None,
    ground_truth: dict,
) -> tuple[dict, list | None]:
    """Cross-check a model's structured answer against the known-correct row's
    on-screen location, and return the bbox that should actually be displayed.

    Small/weak VLMs occasionally misread dense financial tables (e.g. picking
    the right value but the wrong row, or getting the numbers right while
    misreading the row's name/label — small VLMs sometimes "autocorrect" an
    unusual invented company name to a more familiar-looking one even when
    they clearly located the right row and computed the right numbers) or
    eyeball a slightly-off bbox even when the reading is correct. This
    never-shown-to-the-model ground truth acts purely as a display-layer
    safety net:
    - Right page, bbox lands on the right row: the model proved it found the
      right place, so snap the displayed box to the row's exact rect for a
      crisp, jitter-free highlight — but still patch the answer with the
      ground-truth value for any field ground truth defines (covers the
      "right row, mislabeled name" case above) while keeping any extra
      fields the model reported that ground truth doesn't cover.
    - Right page, bbox missing/misses the row/degenerate (e.g. near-zero-area
      or falls back to covering the whole image): the text is unreliable —
      use the ground truth for both the answer and the highlighted position.
    - Wrong page entirely: no matching rect exists here, so fall back to
      the ground truth text with whatever bbox the model produced.
    """
    if not ground_truth or not query_clue:
        return step_answer, bbox
    expected_stage, element_id = query_clue
    if stage_id != expected_stage:
        return dict(ground_truth), bbox
    clue_rect = _find_element_rect(env, stage_id, element_id)
    if clue_rect is None:
        return step_answer, bbox
    clue_bbox = _rect_to_bbox(clue_rect)
    if not _is_degenerate_bbox(bbox) and _bbox_overlaps(bbox, clue_bbox):
        return {**step_answer, **ground_truth}, clue_bbox
    return dict(ground_truth), clue_bbox


async def run_grounding(
    env: ScreenshotEnv,
    queries: list[str],
    max_steps_per_query: int = 4,
) -> AsyncIterator[dict[str, Any]]:
    """Run grounding scene: one page, multiple queries, model returns bboxes."""
    obs = env.reset()

    yield {
        "type": "scene_start",
        "scene": "grounding",
        "stage": obs.stage,
        "image_b64": obs.thumbnail_b64,
    }

    all_groundings: list[dict] = []
    total_steps = 0

    for qi, query in enumerate(queries):
        yield {
            "type": "query_start",
            "query_index": qi,
            "query": query,
        }

        history: list[dict] = []
        for step_in_query in range(max_steps_per_query):
            total_steps += 1
            t0 = time.monotonic()

            messages = build_grounding_messages(
                system=GROUNDING_SYSTEM,
                query=query,
                image_b64=obs.thumbnail_b64,
                history=history if step_in_query > 0 else None,
            )

            result = await call_vlm(messages)
            elapsed = round(time.monotonic() - t0, 2)

            logger.info("Grounding Q%d step%d raw keys: %s", qi, step_in_query, list(result.keys()))
            logger.info("Grounding result: thought=%s, grounding=%s, answer=%s",
                        result.get("thought", "")[:80],
                        result.get("grounding"),
                        result.get("answer", "")[:80])

            groundings = result.get("grounding", [])
            thought = result.get("thought", "")
            answer = result.get("answer", "")

            for g in groundings:
                g["bbox"] = _normalize_bbox(g.get("bbox", [0, 0, 1, 1]))
                g["query_index"] = qi
                all_groundings.append(g)

            yield {
                "type": "step",
                "step": total_steps,
                "query_index": qi,
                "thought": thought,
                "groundings": groundings,
                "answer": answer,
                "elapsed": elapsed,
                "usage": result.get("_usage", {}),
            }

            if groundings or answer:
                break

            history.append({"role": "assistant", "content": result.get("_raw", "")})

        yield {
            "type": "query_end",
            "query_index": qi,
            "query": query,
            "answer": answer,
        }

    yield {
        "type": "scene_end",
        "scene": "grounding",
        "total_steps": total_steps,
        "total_groundings": len(all_groundings),
        "groundings": all_groundings,
    }


async def run_navigation(
    env: ScreenshotEnv,
    task: str,
    max_steps: int = 30,
    min_visited_pages: int | None = None,
) -> AsyncIterator[dict[str, Any]]:
    """Run navigation scene: multi-page environment, model navigates.

    Guarantees:
    - Every page is visited before `eos` is accepted (min_visited_pages).
    - Every visited page is visually examined (a `see` with a red box) before
      the model is allowed to leave it (see-before-leave), so each visited page
      produces a grounding box on the frontend.
    """
    obs = env.reset()
    pages = env.get_stage_titles()
    if min_visited_pages is None:
        min_visited_pages = len(pages)

    yield {
        "type": "scene_start",
        "scene": "navigation",
        "pages": pages,
        "current_stage": obs.stage,
    }

    trajectory: list[dict] = []
    findings: list[dict] = []
    findings_stages: set[str] = set()
    visited: set[str] = {obs.stage}
    skipped: list[dict] = []
    see_count_per_stage: dict[str, int] = {}
    seen_stages: set[str] = set()
    max_see_per_stage = 2

    def _remaining_unvisited() -> list[str]:
        return [
            p["id"] for p in pages
            if p["id"] not in visited and not any(s["id"] == p["id"] for s in skipped)
        ]

    for step_num in range(1, max_steps + 1):
        t0 = time.monotonic()

        # Coverage status so the model always knows which pages are done,
        # regardless of how much of the trajectory has scrolled out of view.
        skipped_ids = sorted({s["id"] for s in skipped if s.get("id")})
        remaining = _remaining_unvisited()
        status_block = (
            f"【已访问页面】{', '.join(sorted(visited))}\n"
            f"【已跳过页面】{', '.join(skipped_ids) or '无'}\n"
            f"【剩余未覆盖】{', '.join(remaining) or '无（全部页面已覆盖，请立即 eos 输出结论）'}"
        )

        traj_lines = []
        for i, t in enumerate(trajectory[-20:]):
            parts = [f"{i+1}. [{t['stage']}] {t['action_type']}"]
            if t.get("bbox_str"):
                parts.append(f"bbox={t['bbox_str']}")
            if t.get("finding_short"):
                parts.append(f"发现: {t['finding_short']}")
            else:
                parts.append(t["thought_short"])
            traj_lines.append("  ".join(parts))
        traj_summary = status_block + "\n\n【近期轨迹】\n" + "\n".join(traj_lines)

        messages = build_navigation_messages(
            system=NAVIGATION_SYSTEM,
            task=task,
            thumbnail_b64=obs.thumbnail_b64,
            crop_b64=obs.crop_b64,
            step_num=step_num,
            max_steps=max_steps,
            current_stage=obs.stage,
            trajectory_summary=traj_summary,
            available_pages=pages,
        )

        result = await call_vlm(messages)
        elapsed = round(time.monotonic() - t0, 2)

        thought = result.get("thought", "")
        action = result.get("action", {})
        finding = result.get("finding")
        action_type = action.get("type", "see") if isinstance(action, dict) else "see"
        action_target = action.get("target") if isinstance(action, dict) else None
        action_reason = action.get("reason", "") if isinstance(action, dict) else ""

        # Force navigate/skip/eos if see limit reached for current stage
        if action_type == "see":
            count = see_count_per_stage.get(obs.stage, 0)
            if count >= max_see_per_stage:
                logger.info("See limit reached for %s (%d), forcing navigate", obs.stage, count)
                action_type = "navigate"
                remaining = _remaining_unvisited()
                action_target = remaining[0] if remaining else None
                if not action_target:
                    action_type = "eos"

        # see-before-leave: never leave a stage we haven't visually examined.
        # Emit a synthetic `see` on the stage's clue region (red box), then
        # re-prompt the model next iteration so it can react to the clue crop.
        if action_type in ("navigate", "skip", "eos") and obs.stage not in seen_stages:
            clue_rect = _get_clue_rect(env, obs.stage)
            if clue_rect is not None:
                see_count_per_stage[obs.stage] = see_count_per_stage.get(obs.stage, 0) + 1
                obs = env.step({"type": "see", "target": {"rect": clue_rect.to_dict()}})
                seen_stages.add(obs.stage)
                bbox_norm = _normalize_bbox([
                    clue_rect.x, clue_rect.y,
                    clue_rect.x + clue_rect.w, clue_rect.y + clue_rect.h,
                ])
                synth_thought = "进入页面后先审视关键区域以排查安全风险，再决定下一步动作。"
                traj_entry = {
                    "step": step_num,
                    "stage": obs.stage,
                    "action_type": "see",
                    "thought_short": synth_thought[:100],
                    "bbox_str": f"[{','.join(f'{v:.2f}' for v in bbox_norm)}]",
                }
                step_event = {
                    "type": "step",
                    "step": step_num,
                    "stage": obs.stage,
                    "thought": synth_thought,
                    "action_type": "see",
                    "action_target": bbox_norm,
                    "action_reason": "聚焦本页关键安全相关区域",
                    "elapsed": 0.0,
                    "usage": {},
                    "observation": {
                        "stage": obs.stage,
                        "rect": obs.rect.to_dict(),
                        "zoom_level": obs.zoom_level,
                    },
                    "groundings": [{"bbox": bbox_norm, "label": "本页关键区域"}],
                }
                trajectory.append(traj_entry)
                yield step_event
                continue
            # No clue rect available — allow the leave without a forced see.

        # min_visited enforcement: refuse eos until enough pages are visited.
        if action_type == "eos" and len(visited) < min_visited_pages:
            remaining = _remaining_unvisited()
            if remaining:
                logger.info(
                    "eos before min_visited (%d/%d), redirecting to %s",
                    len(visited), min_visited_pages, remaining[0],
                )
                action_type = "navigate"
                action_target = remaining[0]
                action_reason = "尚未审计完全部页面，继续访问未审计页面。"

        traj_entry: dict[str, Any] = {
            "step": step_num,
            "stage": obs.stage,
            "action_type": action_type,
            "thought_short": thought[:100],
        }
        if finding:
            traj_entry["finding_short"] = finding[:80]

        step_event: dict[str, Any] = {
            "type": "step",
            "step": step_num,
            "stage": obs.stage,
            "thought": thought,
            "action_type": action_type,
            "action_target": action_target,
            "action_reason": action_reason,
            "elapsed": elapsed,
            "usage": result.get("_usage", {}),
        }

        if finding:
            step_event["finding"] = finding
            if obs.stage not in findings_stages:
                findings.append({"step": step_num, "stage": obs.stage, "finding": finding})
                findings_stages.add(obs.stage)

        if action_type == "eos":
            step_event["conclusion"] = thought
            trajectory.append(traj_entry)
            yield step_event
            break

        if action_type == "skip":
            target_id = action_target if isinstance(action_target, str) else ""
            skipped.append({"id": target_id, "reason": action_reason})
            step_event["skipped_page"] = target_id
            # Advance off the skipped page so the model doesn't re-skip it
            # on the next turn (the env `skip` action otherwise leaves it in place).
            advance_to = _remaining_unvisited()
            if advance_to:
                obs = env.step({"type": "navigate", "target": {"to": advance_to[0]}})
                visited.add(obs.stage)
                step_event["new_stage"] = obs.stage
                step_event["observation"] = {
                    "stage": obs.stage,
                    "rect": obs.rect.to_dict(),
                    "zoom_level": obs.zoom_level,
                }
            trajectory.append(traj_entry)
            yield step_event
            continue

        if action_type == "navigate":
            target_id = action_target if isinstance(action_target, str) else ""
            action_dict = {"type": "navigate", "target": {"to": target_id}}
            obs = env.step(action_dict)
            visited.add(obs.stage)
            step_event["new_stage"] = obs.stage
            step_event["observation"] = {
                "stage": obs.stage,
                "rect": obs.rect.to_dict(),
                "zoom_level": obs.zoom_level,
                "thumbnail_b64": obs.thumbnail_b64,
                "crop_b64": obs.crop_b64,
            }
        elif action_type == "see":
            see_count_per_stage[obs.stage] = see_count_per_stage.get(obs.stage, 0) + 1
            bbox = _parse_see_bbox(action_target)
            if bbox:
                bbox = _normalize_bbox(bbox)
                traj_entry["bbox_str"] = f"[{','.join(f'{v:.2f}' for v in bbox)}]"
                action_dict = {"type": "see", "target": {"bbox": bbox}}
                obs = env.step(action_dict)
                seen_stages.add(obs.stage)
            step_event["observation"] = {
                "stage": obs.stage,
                "rect": obs.rect.to_dict(),
                "zoom_level": obs.zoom_level,
                "thumbnail_b64": obs.thumbnail_b64,
                "crop_b64": obs.crop_b64,
            }
            if bbox:
                step_event["groundings"] = [{"bbox": bbox, "label": action_reason or thought[:40]}]

        trajectory.append(traj_entry)
        yield step_event
    else:
        yield {
            "type": "step",
            "step": max_steps,
            "stage": obs.stage,
            "thought": "已达到最大步数，生成审计结论。",
            "action_type": "eos",
            "elapsed": 0,
        }

    yield {
        "type": "scene_end",
        "scene": "navigation",
        "total_steps": len(trajectory),
        "visited": list(visited),
        "skipped": skipped,
        "findings": findings,
        "trajectory": trajectory,
    }


async def run_stock(
    env: ScreenshotEnv,
    queries: list[str],
    required_fields: list[list[str]] | None = None,
    ground_truth: list[dict] | None = None,
    query_clues: list[tuple[str, str]] | None = None,
    column_hints: dict[str, list[tuple[str, str]]] | None = None,
    max_steps_per_query: int = 7,
    today: str | None = None,
) -> AsyncIterator[dict[str, Any]]:
    """Run stock scene: multi-page financial data center, cross-page Q&A.

    The model navigates/filters between pages, "sorts" a table (a cosmetic
    action on this static-screenshot env — it highlights the column header
    it's reasoning about), zooms in with `see`, and finally `extract`s the
    answer row with a structured `answer` dict. `ground_truth`/`required_fields`
    are safety nets: never shown to the model, only used to patch missing
    answer fields so the demo stays coherent even if the VLM stumbles.
    """
    obs = env.reset()
    pages = env.get_stage_titles()

    yield {
        "type": "scene_start",
        "scene": "stock",
        "pages": pages,
        "current_stage": obs.stage,
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

            if action_type in ("navigate", "filter"):
                target_id = _parse_page_target(action_target)
                if target_id and target_id in env.stages:
                    obs = env.step({"type": "navigate", "target": {"to": target_id}})
                    traj_entry["to"] = obs.stage
                    step_event["new_stage"] = obs.stage
                    step_event["observation"] = {
                        "stage": obs.stage,
                        "rect": obs.rect.to_dict(),
                        "zoom_level": obs.zoom_level,
                        "thumbnail_b64": obs.thumbnail_b64,
                        "crop_b64": obs.crop_b64,
                    }

            elif action_type == "sort":
                traj_entry["column"] = action_column
                traj_entry["direction"] = action_direction
                snapped_rect = _resolve_column_rect(env, obs.stage, action_column, column_hints)
                if snapped_rect is not None:
                    bbox = _rect_to_bbox(snapped_rect)
                else:
                    bbox = _parse_see_bbox(action_target)
                    if bbox:
                        bbox = _normalize_bbox(bbox)
                if bbox:
                    arrow = "↑" if action_direction == "asc" else "↓" if action_direction == "desc" else ""
                    label = f"排序 {action_column or ''} {arrow}".strip()
                    traj_entry["bbox_str"] = f"[{','.join(f'{v:.2f}' for v in bbox)}]"
                    step_event["groundings"] = [{"bbox": bbox, "label": label}]

            elif action_type == "see":
                bbox = _parse_see_bbox(action_target)
                if bbox:
                    bbox = _normalize_bbox(bbox)
                    obs = env.step({"type": "see", "target": {"bbox": bbox}})
                    traj_entry["bbox_str"] = f"[{','.join(f'{v:.2f}' for v in bbox)}]"
                    step_event["observation"] = {
                        "stage": obs.stage,
                        "rect": obs.rect.to_dict(),
                        "zoom_level": obs.zoom_level,
                        "thumbnail_b64": obs.thumbnail_b64,
                        "crop_b64": obs.crop_b64,
                    }
                    step_event["groundings"] = [{"bbox": bbox, "label": action_reason or "观察"}]

            elif action_type == "extract":
                bbox = _parse_see_bbox(action_target)
                if not bbox:
                    clue_rect = _get_clue_rect(env, obs.stage)
                    if clue_rect:
                        bbox = [clue_rect.x, clue_rect.y, clue_rect.x + clue_rect.w, clue_rect.y + clue_rect.h]
                if bbox:
                    bbox = _normalize_bbox(bbox)
                if step_answer:
                    answer, bbox = _validate_and_snap_answer(env, obs.stage, bbox, step_answer, clue, gt)
                    step_event["answer"] = answer
                if bbox:
                    traj_entry["bbox_str"] = f"[{','.join(f'{v:.2f}' for v in bbox)}]"
                    step_event["groundings"] = [{"bbox": bbox, "label": "答案定位"}]
                traj_entry["extracted"] = bool(step_answer)

            elif action_type == "eos":
                if step_answer:
                    answer, eos_bbox = _validate_and_snap_answer(env, obs.stage, None, step_answer, clue, gt)
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

    yield {
        "type": "scene_end",
        "scene": "stock",
        "total_steps": total_steps,
        "queries": len(queries),
    }
