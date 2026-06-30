"""Scene 2: Cognitive navigation — 6-page SaaS admin, security audit task."""

from __future__ import annotations

import json
from pathlib import Path

from ..env.base import ASSETS_DIR, PAGES_DIR, StageInfo

TASK = "作为安全审计员，逐个审计 NexaCloud 管理后台的全部 6 个页面（overview / users / permissions / api-keys / analytics / logs）。对每个页面：先 see 框出与安全相关的关键区域，再决定 navigate 到下一页或 skip 跳过确实无关的页面。一个页面只要被访问过或主动跳过，即视为已覆盖；当全部 6 个页面都已覆盖后，立即 eos 输出最终审计结论，不要重复访问已经覆盖的页面。"

PAGE_DEFS = [
    ("overview",    "总览面板",    "alerts-card"),
    ("users",       "用户管理",    "user-mfa-disabled"),
    ("permissions", "权限设置",    "perm-guest-admin-write"),
    ("api-keys",    "API 密钥管理", "apikey-no-expiry"),
    ("analytics",   "使用量分析",  "analytics-anomaly"),
    ("logs",        "审计日志",    "log-suspicious-1"),
]


def load_navigation_scene() -> tuple[list[StageInfo], str]:
    stages: list[StageInfo] = []
    for page_id, title, clue_id in PAGE_DEFS:
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
            clue_element_id=clue_id,
        ))

    return stages, TASK
