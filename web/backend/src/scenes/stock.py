"""股市探索 (market-explore) scene — real interactive browser, cross-page Q&A.

Only 2 pages now (down from the old static-screenshot demo's 5): the old
`ipo-overview`/`ipo-star` pair merged into one real, filterable
`ipo-subscribe` table, and the old `rank-rising`/`rank-volume`/`rank-vol-price`
trio merged into one real, combinably-filterable `market-ranking` table.
Both are real running HTML+JS pages served from `site/` — sorting/filtering
genuinely reorders/hides DOM rows, it isn't a cosmetic overlay.
"""

from __future__ import annotations

PAGE_DEFS = [
    ("ipo-subscribe", "新股申购"),
    ("market-ranking", "行情排行"),
]

# Fixed "today" for this demo's mock universe — every page's "更新时间"/"申购日期"
# text is authored against this date, and it is also injected into the model's
# prompt (see stock_prompts.build_stock_messages) so eligibility questions like
# "今天仍可申购的" have an unambiguous anchor instead of relying on the model to
# OCR the small update-time text in the corner of the screenshot.
TODAY_DATE = "2026-07-01"

QUERIES = [
    "科创板新股里，今天（申购日当天）仍可申购的股票中，发行价格最低的是哪一只？记下它的简称、申购代码、发行价格和申购日期。",
    "科创板新股中，发行市盈率相对所属行业市盈率溢价最大（即发行市盈率超出行业市盈率的差值最大）的是哪一只？记下它的简称、发行市盈率、行业市盈率和申购日期。",
    "今天连续放量上涨的股票里，涨幅最高的是哪只？记下名称、涨跌幅和换手率。",
]

# Field labels the model should populate in its structured `answer` for each
# query — keeps the final AnswerCard layout stable regardless of model output order.
QUERY_FIELDS = [
    ["简称", "申购代码", "发行价格(元)", "申购日期"],
    ["简称", "发行市盈率(倍)", "行业市盈率(倍)", "申购日期"],
    ["名称", "涨跌幅", "换手率"],
]

# Ground-truth answers baked into the mock data — used only as a safety-net
# fallback if the model fails to produce a usable structured answer, never
# shown to the model itself.
#
# Q1 and Q2 are both deliberately designed so that a naive single-column sort
# over the *whole* table picks the wrong row: 汇能储能 has the lowest price in
# the entire table but its 申购日期 (2026-06-30) is already in the past, so it
# is not actually eligible for Q1 ("今天仍可申购"); 云铸科技 has the highest raw
# 发行市盈率 but only a modest premium over its own industry's PE, so it is not
# the answer to Q2 ("溢价最大"). The correct rows only surface once the model
# applies the eligibility filter (Q1) or computes the cross-column spread (Q2).
#
# Q3 requires combining both "连涨天数≥3天" and "放量天数≥3天" filter chips on
# `market-ranking` before sorting by 涨跌幅 — 格创动能 is the max within that
# combined-filtered set (see COLUMN_HINTS/FILTER_HINTS below for how those
# real clicks are resolved).
QUERY_GROUND_TRUTH = [
    {
        "简称": "曜辰半导", "代码": "688931", "申购代码": "787931",
        "发行价格(元)": "9.80", "申购日期": TODAY_DATE,
    },
    {
        "简称": "熠辉芯电", "代码": "688955",
        "发行市盈率(倍)": "60.20", "行业市盈率(倍)": "28.30", "申购日期": TODAY_DATE,
    },
    {
        "名称": "格创动能", "代码": "300856",
        "涨跌幅": "+19.98%", "换手率": "32.15%",
    },
]

# (stage_id, element_id) clue used as a fallback bbox anchor per query, and
# as the stage the agent is expected to land on to answer that query.
QUERY_CLUES = [
    ("ipo-subscribe", "row-yaochen"),
    ("ipo-subscribe", "row-yihui"),
    ("market-ranking", "row-gechuang"),
]

# Maps a column name keyword the model might say (in its `column` field for a
# `sort` action) to the real `<th id="...">` on that page — this is the
# element BrowserEnv actually clicks to perform a real sort, and whose live
# `bounding_box()` becomes the displayed highlight. No static manifest
# involved: the rect is always queried live, so it's automatically correct
# no matter how the table has already been sorted/filtered.
#
# Order matters: resolution matches keywords in list order and returns on
# the first hit, so more specific keywords (e.g. "行业市盈率") must be listed
# before the generic substring they contain ("市盈率").
COLUMN_HINTS: dict[str, list[tuple[str, str]]] = {
    "ipo-subscribe": [
        ("行业市盈率", "col-industry-pe"),
        ("行业", "col-industry-pe"),
        ("发行价", "col-price"),
        ("价格", "col-price"),
        ("市盈率", "col-pe"),
        ("申购日期", "col-date"),
        ("申购日", "col-date"),
    ],
    "market-ranking": [
        ("涨跌幅", "col-change"),
        ("涨幅", "col-change"),
        ("连涨天数", "col-streak-rising"),
        ("连涨", "col-streak-rising"),
        ("放量天数", "col-streak-volume"),
        ("放量", "col-streak-volume"),
        ("换手率", "col-turnover"),
    ],
}

# Same idea as COLUMN_HINTS but for `filter` actions — maps a tab/condition
# label the model might say to the real clickable chip/tab element id.
FILTER_HINTS: dict[str, list[tuple[str, str]]] = {
    "ipo-subscribe": [
        ("科创板", "tab-star"),
        ("创业板", "tab-gem"),
        ("沪市主板", "tab-sh-main"),
        ("深市主板", "tab-sz-main"),
        ("北交所", "tab-bse"),
        ("全部", "tab-all"),
    ],
    "market-ranking": [
        ("连续上涨", "filter-rising"),
        ("连涨", "filter-rising"),
        ("持续放量", "filter-volume"),
        ("放量", "filter-volume"),
    ],
}


def load_stock_scene() -> tuple[list[dict], list[str]]:
    pages = [{"id": pid, "title": title} for pid, title in PAGE_DEFS]
    return pages, QUERIES


def get_page_titles() -> dict[str, str]:
    return {pid: title for pid, title in PAGE_DEFS}
