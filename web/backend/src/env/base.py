"""Shared types for the live-browser environment."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Rect:
    x: float
    y: float
    w: float
    h: float

    def to_dict(self) -> dict:
        return {"x": self.x, "y": self.y, "w": self.w, "h": self.h}

    @classmethod
    def from_dict(cls, d: dict) -> "Rect":
        return cls(x=d["x"], y=d["y"], w=d["w"], h=d["h"])

    def clamp(self) -> "Rect":
        x = max(0.0, min(self.x, 1.0))
        y = max(0.0, min(self.y, 1.0))
        w = max(0.04, min(self.w, 1.0 - x))
        h = max(0.04, min(self.h, 1.0 - y))
        return Rect(x, y, w, h)


FULL_RECT = Rect(0, 0, 1, 1)


@dataclass
class Observation:
    stage: str
    rect: Rect
    thumbnail_b64: str
    crop_b64: str | None
    zoom_level: float
