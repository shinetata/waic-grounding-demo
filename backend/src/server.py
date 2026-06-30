"""FastAPI server with WebSocket endpoints for demo scenes."""

from __future__ import annotations

import json
import logging
import os
import traceback
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

load_dotenv()

from .agent.loop import run_grounding, run_navigation
from .env.base import ASSETS_DIR, PAGES_DIR
from .env.screenshot import ScreenshotEnv
from .scenes.grounding import load_grounding_scene
from .scenes.navigation import load_navigation_scene

logger = logging.getLogger("demo")
logging.basicConfig(level=logging.INFO)

logger.info("ASSETS_DIR = %s (exists=%s)", ASSETS_DIR, ASSETS_DIR.exists())
logger.info("PAGES_DIR  = %s (exists=%s)", PAGES_DIR, PAGES_DIR.exists())

app = FastAPI(title="WAIC Grounding Demo")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

if PAGES_DIR.exists():
    app.mount("/assets/pages", StaticFiles(directory=str(PAGES_DIR)), name="pages")


@app.get("/api/scenes")
async def list_scenes():
    return {
        "scenes": [
            {
                "id": "grounding",
                "title": "一眼定位",
                "subtitle": "精准视觉定位能力展示",
                "description": "在复杂监控面板中，通过自然语言提问，模型精准框出答案位置",
            },
            {
                "id": "navigation",
                "title": "认知导航",
                "subtitle": "智能信息空间导航能力",
                "description": "在多页面管理后台中，模型自主选路、主动跳过无关内容",
            },
        ]
    }


@app.get("/api/scenes/grounding")
async def grounding_info():
    _, queries = load_grounding_scene()
    return {"scene": "grounding", "queries": queries}


@app.get("/api/scenes/navigation")
async def navigation_info():
    _, task = load_navigation_scene()
    return {"scene": "navigation", "task": task}


@app.get("/api/config")
async def get_config():
    return {
        "model": os.getenv("MODEL_NAME", "qwen/qwen3.5-vl-instruct"),
        "base_url": os.getenv("OPENAI_BASE_URL", ""),
    }


FALLBACK_DIR = ASSETS_DIR / "fallbacks"


def _load_fallback(scene: str) -> list[dict] | None:
    path = FALLBACK_DIR / f"{scene}.json"
    if path.exists():
        return json.loads(path.read_text())
    return None


def _save_fallback(scene: str, events: list[dict]):
    FALLBACK_DIR.mkdir(parents=True, exist_ok=True)
    path = FALLBACK_DIR / f"{scene}.json"
    clean = []
    for e in events:
        c = {k: v for k, v in e.items() if not k.endswith("_b64")}
        if "observation" in c:
            c["observation"] = {
                k: v for k, v in c["observation"].items() if not k.endswith("_b64")
            }
        clean.append(c)
    path.write_text(json.dumps(clean, ensure_ascii=False, indent=2))


@app.websocket("/ws/run")
async def ws_run(ws: WebSocket, scene: str = "grounding"):
    await ws.accept()
    try:
        events: list[dict] = []

        if scene == "grounding":
            stages, queries = load_grounding_scene()
            env = ScreenshotEnv(stages)
            gen = run_grounding(env, queries)
        elif scene == "navigation":
            stages, task = load_navigation_scene()
            env = ScreenshotEnv(stages)
            gen = run_navigation(env, task)
        else:
            await ws.send_json({"type": "error", "message": f"Unknown scene: {scene}"})
            return

        async for event in gen:
            events.append(event)
            sendable = _strip_large_b64(event)
            await ws.send_json(sendable)

        _save_fallback(scene, events)

    except WebSocketDisconnect:
        logger.info("WebSocket client disconnected")
    except Exception as e:
        logger.error("WebSocket handler error: %s\n%s", e, traceback.format_exc())
        try:
            await ws.send_json({"type": "error", "message": str(e)})
        except Exception:
            pass


@app.get("/api/fallback/{scene}")
async def get_fallback(scene: str):
    data = _load_fallback(scene)
    if data is None:
        return {"error": "No fallback available", "events": []}
    return {"events": data}


def _strip_large_b64(event: dict) -> dict:
    """Remove large base64 image data from WS events — frontend uses static URLs."""
    out = {}
    for k, v in event.items():
        if k.endswith("_b64"):
            continue
        elif k == "observation" and isinstance(v, dict):
            out[k] = {ok: ov for ok, ov in v.items() if not ok.endswith("_b64")}
        else:
            out[k] = v
    return out
