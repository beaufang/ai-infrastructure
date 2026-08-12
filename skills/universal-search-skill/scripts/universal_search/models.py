from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class SearchResult:
    title: str
    url: str
    content: str = ""
    published_date: str | None = None
    source: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class SearchResponse:
    objective: str
    search_queries: list[str]
    provider: str
    engine: str
    mode: str
    results: list[SearchResult] = field(default_factory=list)
    fallback_used: bool = False
    answer: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "objective": self.objective,
            "search_queries": self.search_queries,
            "provider": self.provider,
            "engine": self.engine,
            "mode": self.mode,
            "fallback_used": self.fallback_used,
            "answer": self.answer,
            "results": [r.to_dict() for r in self.results],
            "metadata": self.metadata,
        }
