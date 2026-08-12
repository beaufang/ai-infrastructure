from __future__ import annotations

import re
from urllib.parse import urlsplit, urlunsplit

from .models import SearchResult

_HAN_RE = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff]")
_LATIN_RE = re.compile(r"[A-Za-z]")


def contains_han(text: str) -> bool:
    return bool(_HAN_RE.search(text))


def contains_latin(text: str) -> bool:
    return bool(_LATIN_RE.search(text))


def validate_bilingual_queries(search_queries: list[str]) -> None:
    """Require at least one Chinese-oriented query and one English-oriented query.

    A Chinese query contains Han characters. An English query must contain Latin letters
    and no Han characters, so a single mixed-language query cannot satisfy both sides.
    """
    has_chinese = any(contains_han(q) for q in search_queries)
    has_english = any(contains_latin(q) and not contains_han(q) for q in search_queries)

    if not has_chinese or not has_english:
        missing = []
        if not has_chinese:
            missing.append("中文检索词")
        if not has_english:
            missing.append("英文检索词")
        raise ValueError(
            "双语搜索是强制规则：每次必须分别提供至少一条中文检索词和一条英文检索词。"
            f"当前缺少：{'、'.join(missing)}。请使用可重复的 --search-query 补齐。"
        )


def resolve_mode(requested_mode: str, search_queries: list[str]) -> str:
    mode = requested_mode.lower().strip()
    if mode in {"turbo", "basic", "advanced"}:
        return mode
    if mode != "auto":
        raise ValueError(f"Unsupported mode: {requested_mode}")
    return "basic" if any(contains_han(q) for q in search_queries) else "turbo"


def normalize_url(url: str) -> str:
    url = url.strip()
    if not url:
        return ""
    parts = urlsplit(url)
    scheme = parts.scheme.lower()
    netloc = parts.netloc.lower()
    path = parts.path.rstrip("/") or "/"
    # Drop fragments only. Keep query parameters because they can identify distinct resources.
    return urlunsplit((scheme, netloc, path, parts.query, ""))


def dedupe_results(results: list[SearchResult], limit: int) -> list[SearchResult]:
    seen: set[str] = set()
    output: list[SearchResult] = []

    for item in results:
        key = normalize_url(item.url) or f"title:{item.title.strip().lower()}"
        if key in seen:
            continue
        seen.add(key)
        output.append(item)
        if len(output) >= limit:
            break

    return output
