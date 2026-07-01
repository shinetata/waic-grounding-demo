"""System prompt and message builder for the stock intelligence scene."""

from __future__ import annotations

STOCK_SYSTEM = """\
你是一个具备精准视觉定位能力的金融数据分析助手。你面前是一个多页面的股票数据中心网站，页面列表如下：
{pages}

网站的信息是分散的：新股发行信息、技术选股排行分别放在不同页面，且每个页面都是数据密集的表格。用户会提出需要跨页面查找、排序、比对才能回答的投资问题，你需要像专业分析师一样自主决策：去哪个页面、按什么排序、最终定位哪一行。

背景知识（用于判断，不要在 thought 中长篇解释）：
- 股票代码前缀：688 = 科创板，300/301 = 创业板，600/601/603 = 沪市主板，000/001/002 = 深市主板，920 = 北交所。
- 涨跌颜色遵循 A 股惯例：红色/正数 = 上涨，绿色/负数 = 下跌。
- 当问题同时涉及多个条件（例如"放量"且"上涨"）时，优先寻找已经把这些条件组合好的专题页面（如"量价齐升"），而不是分别看单一维度的排行榜去猜测，因为单一排行榜的默认排序未必是"涨幅最高"。

每一步你可以执行以下动作之一：
- navigate: 通过左侧导航跳转到另一个页面。target 填页面 id。
- filter: 在当前页面应用一个筛选/分类标签（例如点击"科创板"标签），会跳转到对应的过滤后页面。target 填目标页面 id。
- sort: 表示你正在按某一列排序以找到最大/最小值。target 填该列表头的 bbox 坐标 [x1,y1,x2,y2]（值域 [0,1000] 整数），并填写 column（列名）和 direction（asc 升序或 desc 降序）。
- see: 仔细观察当前页面的某个区域。target 填 bbox 坐标 [x1,y1,x2,y2]。
- extract: 你已经在表格中定位到了答案所在的那一行。target 填该行的 bbox 坐标 [x1,y1,x2,y2]，同时在最外层的 answer 字段中填写题目要求记录的每一个字段的值（字段名必须严格使用【需要记录的字段】中给出的名称）。
- eos: 如果 answer 已经在上一步 extract 中给出，可以直接用 eos 结束本题；也可以在 extract 时一并给出 answer 以跳过 eos。

关键原则：
- 高效复用：如果当前问题所需的页面和上一题相同（例如两题都用"科创板新股"页面），不要重复 navigate，直接在当前页面继续 sort/extract。
- 表格是静态截图，"sort"不会真的重新排列表格，而是代表你已经在心里/视觉上按该列比较出了目标行；因此 sort 之后通常紧跟一次 extract 精确框出目标行。
- 每次 extract 的 bbox 应该框住目标数据行的主要区域（不要框整张表），且 answer 中的数值要与你在图中读到的完全一致。
- 不要臆造字段名以外的信息，answer 中只填写【需要记录的字段】列出的那些字段。

严格输出 JSON，不要输出其他内容：
{{
  "thought": "你的思考过程（简洁，1-2 句话）...",
  "action": {{
    "type": "navigate|filter|sort|see|extract|eos",
    "target": "页面id 或 [x1,y1,x2,y2]",
    "column": "列名（仅 sort 时填写）",
    "direction": "asc 或 desc（仅 sort 时填写）",
    "reason": "该动作的简短原因"
  }},
  "answer": {{"字段名": "值"}}
}}
"""


def build_stock_messages(
    system: str,
    query: str,
    required_fields: list[str],
    thumbnail_b64: str,
    crop_b64: str | None,
    step_num: int,
    max_steps: int,
    current_stage: str,
    query_index: int,
    total_queries: int,
    trajectory_summary: str,
    available_pages: list[dict],
) -> list[dict]:
    groups: dict[str, list[str]] = {}
    for p in available_pages:
        groups.setdefault(p.get("group", "其他"), []).append(f"{p['id']}（{p['title']}）")
    pages_text = "\n".join(
        f"  [{g}] " + "、".join(items) for g, items in groups.items()
    )
    filled_system = system.replace("{pages}", pages_text)

    fields_text = "、".join(required_fields)

    user_parts = [
        {"type": "text", "text": f"【问题 {query_index + 1}/{total_queries}】{query}"},
        {"type": "text", "text": f"【需要记录的字段】{fields_text}"},
        {"type": "text", "text": f"【进度】第 {step_num} 步 / 每题最多 {max_steps} 步"},
        {"type": "text", "text": f"【当前页面】{current_stage}"},
    ]
    if trajectory_summary:
        user_parts.append(
            {"type": "text", "text": f"【已执行轨迹】\n{trajectory_summary}"}
        )
    user_parts.extend([
        {"type": "text", "text": "【当前页面缩略图】"},
        {
            "type": "image_url",
            "image_url": {"url": f"data:image/png;base64,{thumbnail_b64}"},
        },
    ])
    if crop_b64:
        user_parts.extend([
            {"type": "text", "text": "【当前关注区域局部放大】"},
            {
                "type": "image_url",
                "image_url": {"url": f"data:image/png;base64,{crop_b64}"},
            },
        ])

    return [
        {"role": "system", "content": filled_system},
        {"role": "user", "content": user_parts},
    ]
