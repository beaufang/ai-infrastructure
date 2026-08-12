import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from universal_search.config import Settings
from universal_search.models import SearchResponse, SearchResult
from universal_search.routing import Router


class FakeProvider:
    def __init__(self, name, should_fail=False):
        self.name = name
        self.should_fail = should_fail
        self.calls = 0

    def search(self, objective, search_queries, mode, max_results):
        self.calls += 1
        if self.should_fail:
            raise RuntimeError(f"{self.name} failed")
        return SearchResponse(
            objective=objective,
            search_queries=search_queries,
            provider=self.name,
            engine="parallel",
            mode=mode,
            results=[SearchResult(title="ok", url=f"https://{self.name}.example")],
        )


class RoutingTests(unittest.TestCase):
    @patch.dict(
        os.environ,
        {"PARALLEL_API_KEY": "p", "OPENROUTER_API_KEY": "o"},
        clear=False,
    )
    def test_auto_falls_back_to_openrouter(self):
        settings = Settings()
        parallel = FakeProvider("parallel", should_fail=True)
        openrouter = FakeProvider("openrouter")
        router = Router(settings, parallel, openrouter)

        response = router.search("目标", ["query"], "turbo", 5, "auto", True)
        self.assertEqual(parallel.calls, 1)
        self.assertEqual(openrouter.calls, 1)
        self.assertEqual(response.provider, "openrouter")
        self.assertTrue(response.fallback_used)


if __name__ == "__main__":
    unittest.main()
