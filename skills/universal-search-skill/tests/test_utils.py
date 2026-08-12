import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from universal_search.models import SearchResult
from universal_search.utils import dedupe_results, resolve_mode, validate_bilingual_queries


class ModeSelectionTests(unittest.TestCase):
    def test_auto_english_uses_turbo(self):
        self.assertEqual(resolve_mode("auto", ["OpenAI API latest docs"]), "turbo")

    def test_auto_chinese_uses_basic(self):
        self.assertEqual(
            resolve_mode("auto", ["OpenAI API latest docs", "OpenAI API 最新文档"]),
            "basic",
        )

    def test_explicit_mode_wins(self):
        self.assertEqual(resolve_mode("advanced", ["中文查询"]), "advanced")


class BilingualQueryTests(unittest.TestCase):
    def test_accepts_separate_chinese_and_english_queries(self):
        validate_bilingual_queries([
            "OpenAI Responses API 最新文档",
            "OpenAI Responses API latest docs",
        ])

    def test_rejects_only_english_queries(self):
        with self.assertRaises(ValueError):
            validate_bilingual_queries(["OpenAI Responses API latest docs"])

    def test_rejects_only_chinese_or_mixed_query(self):
        with self.assertRaises(ValueError):
            validate_bilingual_queries(["OpenAI Responses API 最新文档"])


class DedupeTests(unittest.TestCase):
    def test_dedupes_fragments(self):
        results = [
            SearchResult(title="A", url="https://example.com/page#one"),
            SearchResult(title="A2", url="https://example.com/page#two"),
        ]
        deduped = dedupe_results(results, 10)
        self.assertEqual(len(deduped), 1)


if __name__ == "__main__":
    unittest.main()
