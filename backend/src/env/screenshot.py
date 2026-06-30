"""Screenshot-based environment for grounding and navigation demos."""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Optional

from .base import (
    ASSETS_DIR, FULL_RECT, PAGES_DIR,
    Observation, Rect, StageInfo,
    crop_region, image_to_b64, load_image, make_thumbnail,
)


class ScreenshotEnv:
    """Manages multi-page screenshot environment with viewport tracking."""

    def __init__(self, stages: list[StageInfo]):
        self.stages = {s.id: s for s in stages}
        self.stage_order = [s.id for s in stages]
        self.current_stage: str = self.stage_order[0]
        self.current_rect: Rect = FULL_RECT
        self._images: dict[str, any] = {}

    def _get_image(self, stage_id: str):
        if stage_id not in self._images:
            info = self.stages[stage_id]
            self._images[stage_id] = load_image(info.image_path)
        return self._images[stage_id]

    def reset(self) -> Observation:
        self.current_stage = self.stage_order[0]
        self.current_rect = FULL_RECT
        return self._observe()

    def step(self, action: dict) -> Observation:
        atype = action.get("type", "see")
        target = action.get("target")

        if atype == "navigate" or atype == "click":
            dest = None
            if target and isinstance(target, dict):
                dest = target.get("to") or target.get("element_id")
            if dest and dest in self.stages:
                self.current_stage = dest
                self.current_rect = FULL_RECT
            elif dest:
                idx = self.stage_order.index(self.current_stage)
                if idx + 1 < len(self.stage_order):
                    self.current_stage = self.stage_order[idx + 1]
                    self.current_rect = FULL_RECT

        elif atype in ("see", "zoom_in", "scroll"):
            rect = self._resolve_rect(target)
            if rect:
                self.current_rect = rect.clamp()

        elif atype == "zoom_out" or atype == "snapshot":
            self.current_rect = FULL_RECT

        elif atype == "skip":
            pass

        elif atype == "none":
            pass

        return self._observe()

    def _resolve_rect(self, target: Optional[dict]) -> Optional[Rect]:
        if not target:
            return None
        if isinstance(target, dict):
            if "bbox" in target:
                b = target["bbox"]
                if isinstance(b, list) and len(b) == 4:
                    return Rect(b[0], b[1], b[2] - b[0], b[3] - b[1])
            if "rect" in target:
                return Rect.from_dict(target["rect"])
            if "element_id" in target:
                stage = self.stages.get(self.current_stage)
                if stage:
                    for el in stage.elements:
                        if el["id"] == target["element_id"]:
                            return Rect.from_dict(el["rect"])
        return None

    def _observe(self) -> Observation:
        img = self._get_image(self.current_stage)
        thumb = make_thumbnail(img)
        crop = crop_region(img, self.current_rect)

        area = self.current_rect.w * self.current_rect.h
        zoom = 1.0 / math.sqrt(max(area, 0.001))

        return Observation(
            stage=self.current_stage,
            rect=self.current_rect,
            thumbnail_b64=image_to_b64(thumb),
            crop_b64=image_to_b64(crop),
            zoom_level=round(zoom, 2),
        )

    def get_elements(self, stage_id: Optional[str] = None) -> list[dict]:
        sid = stage_id or self.current_stage
        stage = self.stages.get(sid)
        return stage.elements if stage else []

    def get_stage_titles(self) -> list[dict]:
        return [
            {"id": s.id, "title": s.title}
            for s in [self.stages[sid] for sid in self.stage_order]
        ]
