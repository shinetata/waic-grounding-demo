"""FastAPI app for the 股市探索 (market-explore) demo.

Owns one shared Playwright `Browser` process for the app's lifetime; each
WebSocket connection gets its own isolated `BrowserContext`/`Page` (see
`env.browser_env.BrowserEnv`), created on connect and closed on
disconnect/error so no Chromium processes/contexts leak across runs.
"""

from __future__ import annotations

import logging
import os
import traceback
from contextlib import asynccontextmanager
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from playwright.async_api import async_playwright

from .agent.loop import run_stock
from .env.browser_env import BrowserEnv
from .scenes.stock import (
    COLUMN_HINTS,
    FILTER_HINTS,
    QUERY_FIELDS,
    QUERY_GROUND_TRUTH,
    QUERY_CLUES,
    TODAY_DATE,
    load_stock_scene,
)

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("demo")

BACKEND_DIR = Path(__file__).resolve().parent.parent
SITE_DIR = BACKEND_DIR / "site"
PORT = int(os.getenv("PORT", "8010"))
HEADED = os.getenv("BROWSER_HEADED", "").strip() in ("1", "true", "True")

_playwright_ctx = None
_browser = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _playwright_ctx, _browser
    _playwright_ctx = await async_playwright().start()
    # Use the regular Chromium build (already installed for the sibling
    # ../backend demo) rather than the separate "headless shell" binary that
    # newer Playwright defaults to for headless=True — avoids requiring an
    # extra browser download in network-restricted environments.
    _browser = await _playwright_ctx.chromium.launch(headless=not HEADED, channel="chromium")
    logger.info("Playwright chromium launched (headless=%s)", not HEADED)
    try:
        yield
    finally:
        if _browser is not None:
            await _browser.close()
        if _playwright_ctx is not None:
            await _playwright_ctx.stop()
        logger.info("Playwright chromium closed")


app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/site", StaticFiles(directory=str(SITE_DIR)), name="site")


@app.get("/api/health")
async def health():
    return {"status": "ok", "browser": _browser is not None}


@app.get("/api/scenes/stock")
async def stock_info():
    pages, queries = load_stock_scene()
    return {"pages": pages, "queries": queries}


@app.websocket("/ws/run")
async def ws_run(ws: WebSocket):
    await ws.accept()
    env: BrowserEnv | None = None
    try:
        pages, queries = load_stock_scene()
        page_ids = [p["id"] for p in pages]
        base_url = f"http://127.0.0.1:{PORT}/site"

        env = BrowserEnv(base_url=base_url, page_ids=page_ids, entry_page=page_ids[0])
        await env.attach(_browser)

        gen = run_stock(
            env,
            queries,
            pages=pages,
            required_fields=QUERY_FIELDS,
            ground_truth=QUERY_GROUND_TRUTH,
            query_clues=QUERY_CLUES,
            column_hints=COLUMN_HINTS,
            filter_hints=FILTER_HINTS,
            today=TODAY_DATE,
        )

        async for event in gen:
            await ws.send_json(event)

    except WebSocketDisconnect:
        logger.info("WebSocket client disconnected")
    except Exception as e:
        logger.error("WebSocket handler error: %s\n%s", e, traceback.format_exc())
        try:
            await ws.send_json({"type": "error", "message": str(e)})
        except Exception:
            pass
    finally:
        if env is not None:
            await env.close()
