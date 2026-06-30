"""System prompts and message builders for both demo scenes."""

from __future__ import annotations

GROUNDING_SYSTEM = """\
你是一个具备精准视觉定位能力的 AI 助手。你面前是一个复杂的监控面板截图。

用户会提出关于面板内容的问题。你需要：
1. 仔细观察截图，定位与问题相关的核心区域
2. 在 thought 字段中输出你的思考过程
3. 用精确的坐标框出答案所在位置
4. 在 answer 字段给出简洁答案

坐标格式：bbox 为 [x1, y1, x2, y2]，值域 [0, 1000] 整数。(x1,y1) 是左上角，(x2,y2) 是右下角。

定位规则：
- 每个问题最多输出 3 个 grounding 条目，优先选择最关键的区域。
- 每个 bbox 应当有足够的面积让观众能清晰看到内容，避免框过小的单个数字或单元格。
- 如果问题只涉及一个区域，只输出 1 个 grounding。
- 当问题涉及多个区域的关联时，输出多个 grounding 并在 thought 中说明关系。
- label 应简短，不超过 20 字。

严格输出 JSON，不要输出其他内容：
{
  "thought": "你的思考过程...",
  "grounding": [
    {"bbox": [x1, y1, x2, y2], "label": "简短区域描述"}
  ],
  "answer": "简洁答案"
}
"""

NAVIGATION_SYSTEM = """\
你是一个安全审计 AI。你面前是一个 SaaS 管理后台，共有以下页面：
{pages}

你的任务是高效地评估系统安全风险。

每一步你可以执行以下动作之一：
- see: 仔细观察当前页面的某个区域。提供 bbox 坐标 [x1,y1,x2,y2]，值域 [0,1000] 整数。
- navigate: 跳转到另一个页面。提供目标页面 id。
- skip: 跳过一个页面（须说明理由）。提供要跳过的页面 id。
- eos: 完成审计，输出最终结论。

关键原则：
- 高效推进：同一页面最多 see 2 次，获取足够信息后立即 navigate 或 skip。
- 不要重复：如果你在【已执行轨迹】中看到某个区域已经被检查过，不要再对它 see。
- 主动跳过：与安全审计无关的页面应果断 skip，跳过是能力而非遗漏。
- 精准定位：see 时框出安全相关的关键区域，不要框整个页面。
- 尽早结论：当你已收集到足够的安全发现，直接 eos 结束，不需要穷举所有页面。

严格输出 JSON，不要输出其他内容：
{
  "thought": "你的思考过程...",
  "action": {
    "type": "see|navigate|skip|eos",
    "target": "bbox [x1,y1,x2,y2] 或 页面id",
    "reason": "动作原因"
  },
  "finding": "如果发现了安全问题，在这里描述（可选）"
}
"""


def build_grounding_messages(
    system: str,
    query: str,
    image_b64: str,
    history: list[dict] | None = None,
) -> list[dict]:
    messages = [{"role": "system", "content": system}]
    if history:
        messages.extend(history)
    messages.append({
        "role": "user",
        "content": [
            {
                "type": "image_url",
                "image_url": {"url": f"data:image/png;base64,{image_b64}"},
            },
            {"type": "text", "text": query},
        ],
    })
    return messages


def build_navigation_messages(
    system: str,
    task: str,
    thumbnail_b64: str,
    crop_b64: str,
    step_num: int,
    max_steps: int,
    current_stage: str,
    trajectory_summary: str,
    available_pages: list[dict],
) -> list[dict]:
    pages_text = "\n".join(
        f"  - {p['id']}: {p['title']}" for p in available_pages
    )
    filled_system = system.replace("{pages}", pages_text)

    user_parts = [
        {"type": "text", "text": f"【任务】{task}"},
        {"type": "text", "text": f"【进度】第 {step_num} 步 / 共 {max_steps} 步"},
        {"type": "text", "text": f"【当前页面】{current_stage}"},
    ]
    if trajectory_summary:
        user_parts.append(
            {"type": "text", "text": f"【已执行轨迹】\n{trajectory_summary}"}
        )
    user_parts.extend([
        {"type": "text", "text": "【全局缩略图】（红框为当前视野）"},
        {
            "type": "image_url",
            "image_url": {"url": f"data:image/png;base64,{thumbnail_b64}"},
        },
        {"type": "text", "text": "【当前视野局部放大】"},
        {
            "type": "image_url",
            "image_url": {"url": f"data:image/png;base64,{crop_b64}"},
        },
    ])

    return [
        {"role": "system", "content": filled_system},
        {"role": "user", "content": user_parts},
    ]
