from __future__ import annotations

from typing import Any, Callable

from ..config import Settings
from ..http import post_json
from ..models import SearchResponse, SearchResult
from ..utils import dedupe_results

PostJSON = Callable[[str, dict[str, Any], dict[str, str], float], dict[str, Any]]


def _collect_url_citations(node: Any) -> list[dict[str, Any]]:
    """Recursively collect OpenRouter url_citation annotations.

    The recursive traversal intentionally tolerates small response-shape changes.
    """
    found: list[dict[str, Any]] = []

    if isinstance(node, dict):
        if node.get("type") == "url_citation":
            citation = node.get("url_citation")
            if isinstance(citation, dict):
                found.append(citation)
            else:
                found.append(node)
        for value in node.values():
            found.extend(_collect_url_citations(value))
    elif isinstance(node, list):
        for value in node:
            found.extend(_collect_url_citations(value))

    return found


def _extract_message(data: dict[str, Any]) -> dict[str, Any]:
    choices = data.get("choices")
    if not isinstance(choices, list) or not choices:
        return {}
    first = choices[0]
    if not isinstance(first, dict):
        return {}
    message = first.get("message")
    return message if isinstance(message, dict) else {}


class OpenRouterProvider:
    name = "openrouter"

    def __init__(
        self,
        settings: Settings,
        engine: str | None = None,
        model: str | None = None,
        transport: PostJSON = post_json,
    ):
        self.settings = settings
        self.engine = engine or settings.openrouter_engine
        self.model = model or settings.openrouter_model
        self.transport = transport

    def search(
        self,
        objective: str,
        search_queries: list[str],
        mode: str,
        max_results: int,
    ) -> SearchResponse:
        api_key = self.settings.openrouter_api_key
        if not api_key:
            raise RuntimeError(f"Missing {self.settings.openrouter_api_key_env}")

        query_text = "\n".join(f"- {query}" for query in search_queries)
        user_prompt = (
            "必须执行一次网页搜索来完成这个检索任务。不要依赖模型记忆。\n"
            f"搜索目标：{objective}\n"
            f"建议检索词：\n{query_text}\n"
            "请使用 web search tool 搜索，并基于搜索结果给出极简总结；不要省略工具调用。"
        )

        parameters: dict[str, Any] = {
            "engine": self.engine,
            "max_results": max_results,
            "max_total_results": max_results,
            "max_uses": 1,
        }
        if self.engine == "parallel":
            parameters["mode"] = mode

        payload: dict[str, Any] = {
            "model": self.model,
            "messages": [
                {
                    "role": "system",
                    "content": "你是 Universal Search Skill 的搜索执行器。对本请求必须调用一次网页搜索工具。",
                },
                {"role": "user", "content": user_prompt},
            ],
            "tools": [
                {
                    "type": "openrouter:web_search",
                    "parameters": parameters,
                }
            ],
            "max_tool_calls": 1,
            "temperature": 0,
        }

        headers = {"Authorization": f"Bearer {api_key}"}
        if self.settings.openrouter_app_title:
            headers["X-OpenRouter-Title"] = self.settings.openrouter_app_title
        if self.settings.openrouter_http_referer:
            headers["HTTP-Referer"] = self.settings.openrouter_http_referer

        data = self.transport(
            self.settings.openrouter_base_url,
            payload,
            headers,
            self.settings.timeout_seconds,
        )

        message = _extract_message(data)
        answer = message.get("content") if isinstance(message.get("content"), str) else None
        citations = _collect_url_citations(message)

        results: list[SearchResult] = []
        for citation in citations:
            url = str(citation.get("url") or "").strip()
            title = str(citation.get("title") or url or "Untitled").strip()
            content = str(citation.get("content") or citation.get("snippet") or "").strip()
            if not url and not content:
                continue
            results.append(
                SearchResult(
                    title=title,
                    url=url,
                    content=content,
                    published_date=None,
                    source=f"openrouter:{self.engine}",
                )
            )

        results = dedupe_results(results, max_results)
        if not results:
            raise RuntimeError(
                "OpenRouter returned no url_citation results. "
                "The selected model may not have invoked the web search server tool."
            )

        usage = data.get("usage") if isinstance(data.get("usage"), dict) else {}
        metadata = {
            "model": data.get("model") or self.model,
            "usage": usage,
            "openrouter_engine": self.engine,
        }

        return SearchResponse(
            objective=objective,
            search_queries=search_queries,
            provider="openrouter",
            engine=self.engine,
            mode=mode,
            results=results,
            answer=answer,
            metadata=metadata,
        )
