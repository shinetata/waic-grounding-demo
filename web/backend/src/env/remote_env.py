"""Remote environment: the frontend iframe is the AI's viewport.

Instead of owning a Playwright browser, this env sends commands over
WebSocket and awaits the frontend's response (screenshot / element rect).
The interface mirrors ``BrowserEnv`` so ``loop.py`` needs no changes.
"""

from __future__ import annotations

import asyncio
import base64
import io
import logging
import math
from typing import Optional

from fastapi import WebSocketDisconnect
from PIL import Image

from .base import FULL_RECT, Observation, Rect

logger = logging.getLogger("demo")

THUMB_WIDTH = 720


def _image_to_b64(img: Image.Image) -> str:
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode()


class RemoteEnv:
    """One instance per WS connection. Delegates all page interaction to the
    frontend iframe via command/response messages over the same WebSocket."""

    def __init__(
        self,
        ws,
        response_queue: asyncio.Queue,
        page_ids: list[str],
        entry_page: str,
    ):
        self.ws = ws
        self.queue = response_queue
        self.page_ids = page_ids
        self.entry_page = entry_page
        self.current_stage = entry_page
        self.current_rect: Rect = FULL_RECT
        self._doc_w: int = 1680
        self._doc_h: int = 1200

    async def close(self):
        pass

    async def _await_response(self, timeout: float = 30.0) -> dict:
        """Block until the frontend responds, or raise on disconnect.

        A ``None`` in the queue is the sentinel receiver pushes when the WS
        connection has closed — raising ``WebSocketDisconnect`` here propagates
        cleanly out of the loop instead of hanging the whole handler.
        """
        try:
            msg = await asyncio.wait_for(self.queue.get(), timeout=timeout)
        except asyncio.TimeoutError as e:
            raise WebSocketDisconnect(code=1011) from e
        if msg is None:
            raise WebSocketDisconnect(code=1000)
        return msg

    async def reset(self) -> Observation:
        self.current_stage = self.entry_page
        self.current_rect = FULL_RECT
        await self.ws.send_json({"type": "observe"})
        msg = await self._await_response()
        self._update_doc_size(msg)
        return self._build_observation(msg)

    async def navigate(self, page_id: str) -> bool:
        if page_id not in self.page_ids:
            return False
        await self.ws.send_json({
            "type": "execute",
            "action": "navigate",
            "page_id": page_id,
        })
        msg = await self._await_response()
        self._update_doc_size(msg)
        self.current_stage = page_id
        self.current_rect = FULL_RECT
        return True

    async def sort_by(
        self, header_id: str, direction: Optional[str]
    ) -> Optional[Rect]:
        await self.ws.send_json({
            "type": "execute",
            "action": "sort",
            "element_id": header_id,
            "direction": direction,
        })
        msg = await self._await_response()
        self._update_doc_size(msg)
        return self._extract_rect(msg)

    async def apply_filter(self, filter_id: str) -> Optional[Rect]:
        await self.ws.send_json({
            "type": "execute",
            "action": "filter",
            "element_id": filter_id,
        })
        msg = await self._await_response()
        self._update_doc_size(msg)
        return self._extract_rect(msg)

    async def element_rect(self, element_id: str) -> Optional[Rect]:
        if not element_id:
            return None
        await self.ws.send_json({
            "type": "query_rect",
            "element_id": element_id,
        })
        msg = await self._await_response()
        r = msg.get("rect")
        if r:
            return Rect.from_dict(r)
        return None

    def set_rect(self, rect: Rect):
        self.current_rect = rect.clamp()

    def zoom_out(self):
        self.current_rect = FULL_RECT

    async def observe(self) -> Observation:
        await self.ws.send_json({"type": "observe"})
        msg = await self._await_response()
        self._update_doc_size(msg)
        return self._build_observation(msg)

    # ------------------------------------------------------------------

    def _update_doc_size(self, msg: dict):
        self._doc_w = msg.get("doc_width", self._doc_w)
        self._doc_h = msg.get("doc_height", self._doc_h)

    def _extract_rect(self, msg: dict) -> Optional[Rect]:
        r = msg.get("element_rect")
        if r:
            return Rect.from_dict(r)
        return None

    def _build_observation(self, msg: dict) -> Observation:
        thumbnail_b64 = msg.get("image_b64", "")

        crop_b64 = None
        rect = self.current_rect
        if rect and (rect.w < 0.98 or rect.h < 0.98) and thumbnail_b64:
            try:
                png_bytes = base64.b64decode(thumbnail_b64)
                img = Image.open(io.BytesIO(png_bytes)).convert("RGB")
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
            except Exception:
                logger.warning("Failed to crop screenshot", exc_info=True)

        area = max(rect.w * rect.h, 0.001) if rect else 1.0
        zoom = round(1.0 / math.sqrt(area), 2)

        return Observation(
            stage=self.current_stage,
            rect=rect,
            thumbnail_b64=thumbnail_b64,
            crop_b64=crop_b64,
            zoom_level=zoom,
        )
