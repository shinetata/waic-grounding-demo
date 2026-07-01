"""Scene 3: Stock intelligence — multi-page financial data center, cross-page Q&A."""

from __future__ import annotations

import json
from pathlib import Path

from ..env.base import ASSETS_DIR, PAGES_DIR, StageInfo

# Each page mirrors a real financial data-center layout: a persistent left
# nav tree grouped by section, a dense sortable table, and a top index
# ticker. The model must pick the right page, sort/scan it, and extract a
# structured answer — exactly the "find the needle across scattered lists"
# workflow real users go through.
PAGE_DEFS = [
    ("ipo-overview",   "新股申购总览", "新股上市", "row-ov-huineng"),
    ("ipo-star",       "科创板新股",   "新股上市", "row-huinengchuneng"),
    ("rank-rising",    "连续上涨",     "技术选股", "row-gechuang"),
    ("rank-volume",    "持续放量",     "技术选股", "row-gechuang"),
    ("rank-vol-price", "量价齐升",     "技术选股", "row-gechuang"),
]

NAV_GROUPS = [
    {"group": "新股上市", "pages": ["ipo-overview", "ipo-star"]},
    {"group": "技术选股", "pages": ["rank-rising", "rank-volume", "rank-vol-price"]},
]

QUERIES = [
    "最近能打新的科创板新股里，发行价最低的是哪只？记下它的申购代码、申购上限和上市日期。",
    "最近的科创板新股里，发行市盈率最高的是哪只？记下它的简称、发行价和申购日期。",
    "今天连续放量上涨的股票里，涨幅最高的是哪只？记下名称、涨跌幅和换手率。",
]

# Field labels the model should populate in its structured `answer` for each
# query — keeps the final AnswerCard layout stable regardless of model output order.
QUERY_FIELDS = [
    ["简称", "申购代码", "申购上限(万股)", "上市日期"],
    ["简称", "发行价格(元)", "申购日期"],
    ["名称", "涨跌幅", "换手率"],
]

# Ground-truth answers baked into the mock data — used only as a safety-net
# fallback if the model fails to produce a usable structured answer, never
# shown to the model itself.
QUERY_GROUND_TRUTH = [
    {
        "简称": "汇能储能", "代码": "688742", "申购代码": "787742",
        "申购上限(万股)": "1.40", "上市日期": "2026-07-16",
    },
    {
        "简称": "云铸科技", "代码": "688206",
        "发行价格(元)": "45.20", "申购日期": "2026-06-22",
    },
    {
        "名称": "格创动能", "代码": "300856",
        "涨跌幅": "+19.98%", "换手率": "32.15%",
    },
]

# (stage_id, element_id) clue used as a fallback bbox anchor per query, and
# as the stage the agent is expected to land on to answer that query.
QUERY_CLUES = [
    ("ipo-star", "row-huinengchuneng"),
    ("ipo-star", "row-yunzhu"),
    ("rank-vol-price", "row-gechuang"),
]

# "sort" is a narrative action on this static-screenshot env — there is no
# single correct bbox for "the column I'm reasoning about" the way there is
# for a data value, so asking the model to freehand one produces visibly
# imprecise boxes. Since the exact header rects are already in the manifests,
# snap the sort highlight to the real column header via keyword match instead
# of trusting the model's own coordinates for this specific action.
COLUMN_HINTS: dict[str, list[tuple[str, str]]] = {
    "ipo-star": [
        ("发行价", "col-price"),
        ("价格", "col-price"),
        ("市盈率", "col-pe"),
        ("申购日期", "col-date"),
    ],
    "rank-rising": [
        ("涨跌幅", "col-change"),
        ("涨幅", "col-change"),
        ("连涨", "col-streak"),
        ("连续上涨", "col-streak"),
    ],
    "rank-volume": [
        ("涨跌幅", "col-change"),
        ("涨幅", "col-change"),
        ("放量", "col-streak"),
    ],
    "rank-vol-price": [
        ("涨跌幅", "col-change"),
        ("涨幅", "col-change"),
    ],
}


def load_stock_scene() -> tuple[list[StageInfo], list[str]]:
    stages: list[StageInfo] = []
    for page_id, title, group, clue_id in PAGE_DEFS:
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
            group=group,
        ))

    return stages, QUERIES


def get_page_titles() -> dict[str, str]:
    return {pid: title for pid, title, _group, _clue in PAGE_DEFS}
