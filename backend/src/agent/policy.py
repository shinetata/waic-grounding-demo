"""VLM policy — calls an OpenAI-compatible vision model."""

from __future__ import annotations

import json
import os
import re
from typing import Any

from openai import AsyncOpenAI


def _get_client() -> AsyncOpenAI:
    return AsyncOpenAI(
        api_key=os.getenv("OPENAI_API_KEY", ""),
        base_url=os.getenv("OPENAI_BASE_URL", "https://openrouter.ai/api/v1"),
    )


def _extract_json(text: str) -> dict:
    """Extract JSON from model output, handling markdown fences."""
    text = text.strip()
    m = re.search(r"```(?:json)?\s*\n?(.*?)\n?\s*```", text, re.DOTALL)
    if m:
        text = m.group(1).strip()
    if text.startswith("{"):
        return json.loads(text)
    m = re.search(r"\{.*\}", text, re.DOTALL)
    if m:
        return json.loads(m.group(0))
    return {"thought": text, "error": "json_parse_failed"}


async def call_vlm(
    messages: list[dict],
    model: str | None = None,
    temperature: float = 0.3,
    max_tokens: int = 1024,
) -> dict[str, Any]:
    client = _get_client()
    model = model or os.getenv("MODEL_NAME", "qwen/qwen3.5-vl-instruct")

    resp = await client.chat.completions.create(
        model=model,
        messages=messages,
        temperature=temperature,
        max_tokens=max_tokens,
    )

    raw = resp.choices[0].message.content or ""
    parsed = _extract_json(raw)
    parsed["_raw"] = raw
    parsed["_usage"] = {
        "prompt_tokens": resp.usage.prompt_tokens if resp.usage else 0,
        "completion_tokens": resp.usage.completion_tokens if resp.usage else 0,
    }
    return parsed
