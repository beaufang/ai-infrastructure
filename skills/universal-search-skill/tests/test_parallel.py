import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from universal_search.config import Settings
from universal_search.providers.parallel import ParallelProvider


class ParallelProviderTests(unittest.TestCase):
    @patch.dict(os.environ, {"PARALLEL_API_KEY": "test-key"}, clear=False)
    def test_normalizes_parallel_response(self):
        captured = {}

        def fake_transport(url, payload, headers, timeout):
            captured.update({"url": url, "payload": payload, "headers": headers})
            return {
                "search_id": "search_1",
                "session_id": "session_1",
                "results": [
                    {
                        "title": "Example",
                        "url": "https://example.com",
                        "publish_date": "2026-01-02",
                        "excerpts": ["first", "second"],
                    }
                ],
            }

        provider = ParallelProvider(Settings(), transport=fake_transport)
        response = provider.search("目标", ["example query"], "turbo", 5)

        self.assertEqual(response.provider, "parallel")
        self.assertEqual(response.results[0].content, "first\n\nsecond")
        self.assertEqual(captured["payload"]["mode"], "turbo")
        self.assertEqual(captured["headers"]["x-api-key"], "test-key")


if __name__ == "__main__":
    unittest.main()
