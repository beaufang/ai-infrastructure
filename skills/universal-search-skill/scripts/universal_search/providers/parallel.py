from __future__ import annotations

from typing import Any, Callable

from ..config import Settings
from ..http import post_json
from ..models import SearchResponse, SearchResult
from ..utils import dedupe_results

PostJSON = Callable[[str, dict[str, Any], dict[str, str], float], dict[str, Any]]


class ParallelProvider:
    name = "parallel"

    def __init__(self, settings: Settings, transport: PostJSON = post_json):
        self.settings = settings
        self.transport = transport

    def search(
        self,
        objective: str,
        search_queries: list[str],
        mode: str,
        max_results: int,
    ) -> SearchResponse:
        api_key = self.settings.parallel_api_key
        if not api_key:
            raise RuntimeError(f"Missing {self.settings.parallel_api_key_env}")

        payload: dict[str, Any] = {
            "objective": objective,
            "search_queries": search_queries,
            "mode": mode,
            "max_chars_total": self.settings.max_chars_total,
        }

        data = self.transport(
            self.settings.parallel_base_url,
            payload,
            {"x-api-key": api_key},
            self.settings.timeout_seconds,
        )

        raw_results = data.get("results")
        if not isinstance(raw_results, list):
            raise RuntimeError("Parallel response does not contain a results list")

        results: list[SearchResult] = []
        for item in raw_results:
            if not isinstance(item, dict):
                continue
            url = str(item.get("url") or "").strip()
            title = str(item.get("title") or url or "Untitled").strip()
            excerpts = item.get("excerpts")
            if isinstance(excerpts, list):
                content = "\n\n".join(str(x).strip() for x in excerpts if str(x).strip())
            else:
                content = str(excerpts or "").strip()
            if not url and not content:
                continue
            published = item.get("publish_date")
            results.append(
                SearchResult(
                    title=title,
                    url=url,
                    content=content,
                    published_date=str(published) if published else None,
                    source="parallel",
                )
            )

        results = dedupe_results(results, max_results)
        if not results:
            raise RuntimeError("Parallel returned no usable search results")

        metadata = {
            "search_id": data.get("search_id"),
            "session_id": data.get("session_id"),
            "warnings": data.get("warnings"),
            "usage": data.get("usage"),
        }

        return SearchResponse(
            objective=objective,
            search_queries=search_queries,
            provider="parallel",
            engine="parallel",
            mode=mode,
            results=results,
            metadata=metadata,
        )
