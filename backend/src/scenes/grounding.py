"""Scene 1: Grounding precision — single complex dashboard, progressive queries."""

from __future__ import annotations

import json
from pathlib import Path

from ..env.base import ASSETS_DIR, PAGES_DIR, StageInfo

MANIFEST_PATH = ASSETS_DIR / "manifests" / "dashboard.json"

QUERIES = [
    "在这个监控面板中，哪个服务的CPU使用率最高？它的具体数值是多少？",
    "过去24小时P99延迟有没有异常峰值？具体在什么时间、峰值是多少？",
    "这个延迟峰值和哪次部署操作有关？请同时定位延迟面板和部署时间线中的相关事件。",
]


def load_grounding_scene() -> tuple[list[StageInfo], list[str]]:
    if MANIFEST_PATH.exists():
        manifest = json.loads(MANIFEST_PATH.read_text())
        elements = manifest.get("elements", [])
    else:
        elements = []

    stage = StageInfo(
        id="dashboard",
        title="CloudOps 监控面板",
        image_path=PAGES_DIR / "dashboard.png",
        elements=elements,
    )
    return [stage], QUERIES
