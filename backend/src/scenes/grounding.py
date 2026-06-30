"""Scene 1: Grounding precision — single complex dashboard, progressive queries."""

from __future__ import annotations

import json
from pathlib import Path

from ..env.base import ASSETS_DIR, PAGES_DIR, StageInfo

MANIFEST_PATH = ASSETS_DIR / "manifests" / "dashboard.json"

QUERIES = [
    "在这28个服务中，CPU使用率最高的是哪个？它的具体数值和当前副本数各是多少？",
    "过去24小时P99延迟出现了异常峰值，峰值具体是多少毫秒？发生在什么时间？同时指出哪些资源因此接近饱和。",
    "根据事件关联时间线，v2.4.0部署后的级联故障链条是什么？请定位部署时间线和关联表中从部署到回滚的全部事件。",
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
