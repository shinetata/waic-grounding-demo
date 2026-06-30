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

    Accepts a JSON array, a JSON string, or free-form strings like
    "bbox [230, 280, 950, 460]" / "230,280,950,460" by extracting the first
    four numbers via regex. Returns None if no valid bbox can be recovered.
    """
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
