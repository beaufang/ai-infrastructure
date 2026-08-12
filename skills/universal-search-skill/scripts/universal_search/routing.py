from __future__ import annotations

from dataclasses import dataclass

from .config import Settings
from .models import SearchResponse
from .providers.openrouter import OpenRouterProvider
from .providers.parallel import ParallelProvider


class SearchUnavailable(RuntimeError):
    pass


@dataclass
class Router:
    settings: Settings
    parallel: ParallelProvider
    openrouter: OpenRouterProvider

    @classmethod
    def build(
        cls,
        settings: Settings,
        openrouter_engine: str | None = None,
        openrouter_model: str | None = None,
    ) -> "Router":
        return cls(
            settings=settings,
            parallel=ParallelProvider(settings),
            openrouter=OpenRouterProvider(
                settings,
                engine=openrouter_engine,
                model=openrouter_model,
            ),
        )

    def search(
        self,
        objective: str,
        search_queries: list[str],
        mode: str,
        max_results: int,
        provider: str,
        allow_fallback: bool,
    ) -> SearchResponse:
        provider = provider.lower().strip()

        if provider == "parallel":
            return self.parallel.search(objective, search_queries, mode, max_results)

        if provider == "openrouter":
            return self.openrouter.search(objective, search_queries, mode, max_results)

        if provider != "auto":
            raise ValueError(f"Unsupported provider: {provider}")

        errors: list[str] = []

        if self.settings.parallel_api_key:
            try:
                return self.parallel.search(objective, search_queries, mode, max_results)
            except Exception as exc:
                errors.append(f"parallel: {exc}")
                if not allow_fallback:
                    raise

        if self.settings.openrouter_api_key:
            try:
                response = self.openrouter.search(objective, search_queries, mode, max_results)
                response.fallback_used = bool(errors) or bool(self.settings.parallel_api_key)
                return response
            except Exception as exc:
                errors.append(f"openrouter: {exc}")

        if not self.settings.parallel_api_key and not self.settings.openrouter_api_key:
            raise SearchUnavailable(
                f"No search API key configured. Set {self.settings.parallel_api_key_env} "
                f"or {self.settings.openrouter_api_key_env}."
            )

        detail = "; ".join(errors) if errors else "No usable provider"
        raise SearchUnavailable(f"All available search providers failed: {detail}")
