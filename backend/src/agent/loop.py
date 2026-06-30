"""Agent loop for both grounding and navigation scenes."""

from __future__ import annotations

import logging
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
    max_steps: int = 20,
) -> AsyncIterator[dict[str, Any]]:
    """Run navigation scene: multi-page environment, model navigates."""
    obs = env.reset()
    pages = env.get_stage_titles()

    yield {
        "type": "scene_start",
        "scene": "navigation",
        "pages": pages,
        "current_stage": obs.stage,
    }

    trajectory: list[dict] = []
    findings: list[dict] = []
    visited: set[str] = {obs.stage}
    skipped: list[dict] = []
    see_count_per_stage: dict[str, int] = {}
    max_see_per_stage = 2

    for step_num in range(1, max_steps + 1):
        t0 = time.monotonic()

        traj_lines = []
        for i, t in enumerate(trajectory[-10:]):
            parts = [f"{i+1}. [{t['stage']}] {t['action_type']}"]
            if t.get("bbox_str"):
                parts.append(f"bbox={t['bbox_str']}")
            if t.get("finding_short"):
                parts.append(f"发现: {t['finding_short']}")
            else:
                parts.append(t["thought_short"])
            traj_lines.append("  ".join(parts))
        traj_summary = "\n".join(traj_lines)

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
                remaining = [p["id"] for p in pages if p["id"] not in visited and not any(s["id"] == p["id"] for s in skipped)]
                action_target = remaining[0] if remaining else None
                if not action_target:
                    action_type = "eos"

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
            findings.append({"step": step_num, "stage": obs.stage, "finding": finding})
            step_event["finding"] = finding

        if action_type == "eos":
            step_event["conclusion"] = thought
            trajectory.append(traj_entry)
            yield step_event
            break

        if action_type == "skip":
            target_id = action_target if isinstance(action_target, str) else ""
            skipped.append({"id": target_id, "reason": action_reason})
            step_event["skipped_page"] = target_id
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
            bbox = None
            if isinstance(action_target, list) and len(action_target) == 4:
                bbox = action_target
            elif isinstance(action_target, str):
                try:
                    import json as _json
                    bbox = _json.loads(action_target)
                except Exception:
                    pass
            if bbox:
                bbox = _normalize_bbox(bbox)
                traj_entry["bbox_str"] = f"[{','.join(f'{v:.2f}' for v in bbox)}]"
                action_dict = {"type": "see", "target": {"bbox": bbox}}
                obs = env.step(action_dict)
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
