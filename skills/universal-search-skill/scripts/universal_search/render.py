from __future__ import annotations

import json

from .models import SearchResponse


def render_json(response: SearchResponse) -> str:
    return json.dumps(response.to_dict(), ensure_ascii=False, indent=2)


def render_markdown(response: SearchResponse) -> str:
    lines = [
        f"# 搜索结果：{response.objective}",
        "",
        f"- Provider: `{response.provider}`",
        f"- Engine: `{response.engine}`",
        f"- Mode: `{response.mode}`",
        f"- Fallback: `{str(response.fallback_used).lower()}`",
        "- Queries: " + ", ".join(f"`{q}`" for q in response.search_queries),
        "",
    ]

    if response.answer:
        lines.extend(["## OpenRouter 摘要", "", response.answer.strip(), ""])

    lines.extend(["## Sources", ""])
    for idx, item in enumerate(response.results, start=1):
        lines.append(f"### {idx}. {item.title}")
        lines.append("")
        if item.url:
            lines.append(item.url)
            lines.append("")
        if item.published_date:
            lines.append(f"发布日期：{item.published_date}")
            lines.append("")
        if item.content:
            lines.append(item.content.strip())
            lines.append("")

    return "\n".join(lines).rstrip() + "\n"
