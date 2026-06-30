"""Scene 2: Cognitive navigation — 6-page SaaS admin, security audit task."""

from __future__ import annotations

import json
from pathlib import Path

from ..env.base import ASSETS_DIR, PAGES_DIR, StageInfo

TASK = "作为安全审计员，全面评估这个 NexaCloud SaaS 管理后台的安全风险。找出所有高危问题并给出审计结论。"

PAGE_DEFS = [
    ("overview",    "总览面板"),
    ("users",       "用户管理"),
    ("permissions", "权限设置"),
    ("api-keys",    "API 密钥管理"),
    ("analytics",   "使用量分析"),
    ("logs",        "审计日志"),
]


def load_navigation_scene() -> tuple[list[StageInfo], str]:
    stages: list[StageInfo] = []
    for page_id, title in PAGE_DEFS:
        manifest_path = ASSETS_DIR / "manifests" / f"{page_id}.json"
        elements = []
        if manifest_path.exists():
            manifest = json.loads(manifest_path.read_text())
            elements = manifest.get("elements", [])

        stages.append(StageInfo(
            id=page_id,
            title=title,
            image_path=PAGES_DIR / f"{page_id}.png",
            elements=elements,
        ))

    return stages, TASK
