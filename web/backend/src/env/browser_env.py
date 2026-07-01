"""Live Playwright-backed environment for the market-explore scene.

Unlike a screenshot-replay environment, every `step()`-style call here
performs a real DOM interaction (clicking a real `<a>` nav link, a real
sortable header, a real filter chip) against a real running webpage served
from `site/`. Screenshots and element bounding boxes are captured live,
every time, straight from the current DOM state — there is no pre-baked
manifest that can go stale when the page re-sorts or re-filters.
"""

from __future__ import annotations

import base64
import io
import math
from typing import Optional

from PIL import Image
from playwright.async_api import Browser, BrowserContext, Page

from .base import FULL_RECT, Observation, Rect

THUMB_WIDTH = 720
VIEWPORT = {"width": 1680, "height": 1200}
DEVICE_SCALE = 2


def _image_to_b64(img: Image.Image) -> str:
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode()


class BrowserEnv:
    """One instance per WebSocket connection; owns a dedicated browser context/page."""

    def __init__(self, base_url: str, page_ids: list[str], entry_page: str):
        self.base_url = base_url.rstrip("/")
        self.page_ids = page_ids
        self.entry_page = entry_page
        self.current_stage = entry_page
        self.current_rect: Rect = FULL_RECT

        self._context: Optional[BrowserContext] = None
        self.page: Optional[Page] = None

    async def attach(self, browser: Browser):
        """Attach to a shared Browser instance (owned by the app lifespan) and
        create a fresh, isolated context/page for this connection."""
        self._context = await browser.new_context(
            viewport=VIEWPORT,
            device_scale_factor=DEVICE_SCALE,
        )
        self.page = await self._context.new_page()

    async def close(self):
        if self._context is not None:
            await self._context.close()
            self._context = None
            self.page = None

    async def reset(self) -> Observation:
        self.current_stage = self.entry_page
        self.current_rect = FULL_RECT
        await self._goto(self.entry_page)
        return await self._observe()

    async def _goto(self, page_id: str):
        url = f"{self.base_url}/{page_id}.html"
        await self.page.goto(url, wait_until="load")
        await self._fit_viewport()

    async def _fit_viewport(self):
        """Resize the viewport to exactly the document's scroll size, so a
        `full_page` screenshot and `bounding_box()` coordinates always agree
        — no scroll-offset bookkeeping needed anywhere else."""
        size = await self.page.evaluate(
            "() => ({w: document.documentElement.scrollWidth, h: document.documentElement.scrollHeight})"
        )
        w = max(int(size["w"]), 1)
        h = max(int(size["h"]), 1)
        await self.page.set_viewport_size({"width": w, "height": h})

    def _doc_size(self) -> tuple[int, int]:
        vp = self.page.viewport_size or VIEWPORT
        return vp["width"], vp["height"]

    async def element_rect(self, element_id: str) -> Optional[Rect]:
        """Live query of a DOM element's current on-screen position, as a
        [0,1] fractional rect. Returns None if the element doesn't exist or
        is currently hidden (e.g. filtered out) — callers treat that the
        same as "no clue available", never a stale/wrong position."""
        if not element_id:
            return None
        try:
            box = await self.page.locator(f"#{element_id}").bounding_box()
        except Exception:
            return None
        if box is None:
            return None
        doc_w, doc_h = self._doc_size()
        if doc_w <= 0 or doc_h <= 0:
            return None
        return Rect(
            x=box["x"] / doc_w,
            y=box["y"] / doc_h,
            w=box["width"] / doc_w,
            h=box["height"] / doc_h,
        )

    async def _click(self, element_id: str) -> bool:
        try:
            await self.page.locator(f"#{element_id}").click(timeout=2000)
        except Exception:
            return False
        return True

    async def _read_sort_dir(self, header_id: str) -> Optional[str]:
        try:
            return await self.page.locator(f"#{header_id}").get_attribute("data-dir")
        except Exception:
            return None

    async def navigate(self, page_id: str) -> bool:
        """Real click on the real sidebar `<a>` link — a genuine page load,
        not a swap to a pre-rendered image."""
        if page_id not in self.page_ids:
            return False
        ok = await self._click(f"nav-{page_id}")
        if ok:
            await self.page.wait_for_load_state("load")
        else:
            await self._goto(page_id)
        await self._fit_viewport()
        self.current_stage = page_id
        self.current_rect = FULL_RECT
        return True

    async def sort_by(self, header_id: str, direction: Optional[str]) -> Optional[Rect]:
        """Real click on a real sortable `<th>`. The header's own JS toggles
        asc/desc on each click; if the caller asked for a specific direction
        and the first click landed on the other one, click again to flip it."""
        if not await self._click(header_id):
            return None
        await self._fit_viewport()
        if direction in ("asc", "desc"):
            current = await self._read_sort_dir(header_id)
            if current != direction:
                await self._click(header_id)
                await self._fit_viewport()
        return await self.element_rect(header_id)

    async def apply_filter(self, filter_id: str) -> Optional[Rect]:
        """Real click on a real filter tab/chip — genuinely hides/shows rows
        client-side via the page's own JS."""
        if not await self._click(filter_id):
            return None
        await self._fit_viewport()
        return await self.element_rect(filter_id)

    def set_rect(self, rect: Rect):
        self.current_rect = rect.clamp()

    def zoom_out(self):
        self.current_rect = FULL_RECT

    async def _observe(self) -> Observation:
        png_bytes = await self.page.screenshot(full_page=True)
        img = Image.open(io.BytesIO(png_bytes)).convert("RGB")
        # Send the full-resolution live screenshot as-is rather than
        # downscaling to a small "thumbnail" — these are dense financial
        # tables where legibility is the whole point, and the frontend's
        # `object-fit: contain` only ever needs to *shrink* a larger source
        # image (always crisp) instead of stretching up a small one (blurry
        # on any display wider than ~720px, especially HiDPI screens).
        thumbnail_b64 = base64.b64encode(png_bytes).decode()

        crop_b64 = None
        rect = self.current_rect
        if rect and (rect.w < 0.98 or rect.h < 0.98):
            px = max(0, min(int(rect.x * img.width), img.width - 1))
            py = max(0, min(int(rect.y * img.height), img.height - 1))
            pw = max(20, min(int(rect.w * img.width), img.width - px))
            ph = max(20, min(int(rect.h * img.height), img.height - py))
            crop_img = img.crop((px, py, px + pw, py + ph))
            if crop_img.width < THUMB_WIDTH:
                scale = min(THUMB_WIDTH / crop_img.width, 4.0)
                crop_img = crop_img.resize(
                    (int(crop_img.width * scale), int(crop_img.height * scale)),
                    Image.LANCZOS,
                )
            crop_b64 = _image_to_b64(crop_img)

        area = max(rect.w * rect.h, 0.001) if rect else 1.0
        zoom = round(1.0 / math.sqrt(area), 2)

        return Observation(
            stage=self.current_stage,
            rect=rect,
            thumbnail_b64=thumbnail_b64,
            crop_b64=crop_b64,
            zoom_level=zoom,
        )

    async def observe(self) -> Observation:
        return await self._observe()
