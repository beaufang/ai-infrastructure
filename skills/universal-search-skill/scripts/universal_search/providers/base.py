from __future__ import annotations

from typing import Protocol

from ..models import SearchResponse


class SearchProvider(Protocol):
    name: str

    def search(
        self,
        objective: str,
        search_queries: list[str],
        mode: str,
        max_results: int,
    ) -> SearchResponse: ...
