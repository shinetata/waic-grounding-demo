"""FastAPI app for the 股市探索 (market-explore) demo.

No Playwright dependency: the frontend iframe is the AI's viewport.
Each WebSocket connection gets a ``RemoteEnv`` that sends action commands
to the frontend and receives screenshots / element rects in return.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import os
import traceback
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from .agent.loop import run_stock
from .env.remote_env import RemoteEnv
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

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/site", StaticFiles(directory=str(SITE_DIR)), name="site")


@app.get("/api/health")
async def health():
    return {"status": "ok"}


@app.get("/api/scenes/stock")
async def stock_info():
    pages, queries = load_stock_scene()
    return {"pages": pages, "queries": queries}


@app.websocket("/ws/run")
async def ws_run(ws: WebSocket):
    await ws.accept()
    env: RemoteEnv | None = None
    recv_task: asyncio.Task | None = None
    try:
        pages, queries = load_stock_scene()
        page_ids = [p["id"] for p in pages]

        response_queue: asyncio.Queue = asyncio.Queue()
        env = RemoteEnv(
            ws=ws,
            response_queue=response_queue,
            page_ids=page_ids,
            entry_page=page_ids[0],
        )

        async def receiver():
            """Read messages from the frontend and route them to the queue.

            When the WS is closed (client refresh / cancel), push a sentinel
            ``None`` so any coroutine awaiting ``queue.get()`` wakes up and
            can raise a disconnect instead of hanging forever.
            """
            try:
                while True:
                    msg = await ws.receive_json()
                    await response_queue.put(msg)
            except WebSocketDisconnect:
                pass
            except Exception:
                logger.info("Receiver task exited: %s", traceback.format_exc(limit=1))
            finally:
                await response_queue.put(None)

        recv_task = asyncio.create_task(receiver())

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
        if recv_task is not None:
            recv_task.cancel()
            with contextlib.suppress(asyncio.CancelledError, Exception):
                await recv_task
        if env is not None:
            await env.close()
