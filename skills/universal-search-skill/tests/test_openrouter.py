import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from universal_search.config import Settings
from universal_search.providers.openrouter import OpenRouterProvider


class OpenRouterProviderTests(unittest.TestCase):
    @patch.dict(os.environ, {"OPENROUTER_API_KEY": "test-key"}, clear=False)
    def test_collects_url_citations_and_forces_parallel_engine(self):
        captured = {}

        def fake_transport(url, payload, headers, timeout):
            captured.update({"payload": payload, "headers": headers})
            return {
                "model": "~openai/gpt-latest",
                "choices": [
                    {
                        "message": {
                            "content": "summary",
                            "annotations": [
                                {
                                    "type": "url_citation",
                                    "url_citation": {
                                        "url": "https://example.com/a",
                                        "title": "Example A",
                                        "content": "Relevant excerpt",
                                    },
                                }
                            ],
                        }
                    }
                ],
                "usage": {"server_tool_use": {"web_search_requests": 1}},
            }

        provider = OpenRouterProvider(Settings(), engine="parallel", transport=fake_transport)
        response = provider.search("目标", ["query"], "turbo", 5)

        tool = captured["payload"]["tools"][0]
        self.assertEqual(tool["type"], "openrouter:web_search")
        self.assertEqual(tool["parameters"]["engine"], "parallel")
        self.assertEqual(tool["parameters"]["mode"], "turbo")
        self.assertEqual(tool["parameters"]["max_uses"], 1)
        self.assertEqual(response.results[0].url, "https://example.com/a")
        self.assertEqual(response.answer, "summary")


if __name__ == "__main__":
    unittest.main()
