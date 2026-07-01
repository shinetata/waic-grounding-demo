"""Environment interface and shared types."""

from __future__ import annotations

import base64
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from PIL import Image
import io

def _find_assets_dir() -> Path:
    """Locate assets directory — works both from source and installed package."""
    # Try relative to source file first
    candidate = Path(__file__).resolve().parent.parent.parent / "assets"
    if (candidate / "pages").exists():
        return candidate
    # Fallback: relative to CWD (when run via `uv run uvicorn`)
    candidate = Path.cwd() / "assets"
    if (candidate / "pages").exists():
        return candidate
    # Last resort: env var
    import os
    env_path = os.getenv("ASSETS_DIR")
    if env_path:
        return Path(env_path)
    return Path.cwd() / "assets"

ASSETS_DIR = _find_assets_dir()
PAGES_DIR = ASSETS_DIR / "pages"

THUMB_WIDTH = 720


@dataclass
class Rect:
    x: float
    y: float
    w: float
    h: float

    def to_dict(self) -> dict:
        return {"x": self.x, "y": self.y, "w": self.w, "h": self.h}

    @classmethod
    def from_dict(cls, d: dict) -> Rect:
        return cls(x=d["x"], y=d["y"], w=d["w"], h=d["h"])

    def clamp(self) -> Rect:
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
    crop_b64: str
    zoom_level: float


@dataclass
class StageInfo:
    id: str
    title: str
    image_path: Path
    elements: list[dict] = field(default_factory=list)
    clue_element_id: str | None = None
    group: str | None = None


def image_to_b64(img: Image.Image, fmt: str = "PNG") -> str:
    buf = io.BytesIO()
    img.save(buf, format=fmt)
    return base64.b64encode(buf.getvalue()).decode()


def load_image(path: Path) -> Image.Image:
    return Image.open(path).convert("RGB")


def make_thumbnail(img: Image.Image, rect: Optional[Rect] = None) -> Image.Image:
    ratio = THUMB_WIDTH / img.width
    thumb = img.resize((THUMB_WIDTH, int(img.height * ratio)), Image.LANCZOS)
    return thumb


def crop_region(img: Image.Image, rect: Rect, min_width: int = 720) -> Image.Image:
    px = int(rect.x * img.width)
    py = int(rect.y * img.height)
    pw = int(rect.w * img.width)
    ph = int(rect.h * img.height)
    px = max(0, min(px, img.width - 1))
    py = max(0, min(py, img.height - 1))
    pw = max(20, min(pw, img.width - px))
    ph = max(20, min(ph, img.height - py))
    if px + pw > img.width:
        px = max(0, img.width - pw)
    if py + ph > img.height:
        py = max(0, img.height - ph)

    cropped = img.crop((px, py, px + pw, py + ph))
    if cropped.width < min_width:
        scale = min(min_width / cropped.width, 4.0)
        cropped = cropped.resize(
            (int(cropped.width * scale), int(cropped.height * scale)),
            Image.LANCZOS,
        )
    return cropped
