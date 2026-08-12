#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Allow running directly from the Skill directory without installation.
SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from universal_search.config import load_settings
from universal_search.render import render_json, render_markdown
from universal_search.routing import Router
from universal_search.utils import resolve_mode, validate_bilingual_queries


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Universal Search Skill: Parallel Direct + OpenRouter fallback",
    )
    parser.add_argument("objective", help="自然语言搜索目标，可使用中文")
    parser.add_argument(
        "--search-query",
        action="append",
        dest="search_queries",
        help="简洁检索词，可重复。强制至少分别提供一条中文查询和一条英文查询。",
    )
    parser.add_argument(
        "--provider",
        choices=["auto", "parallel", "openrouter"],
        help="覆盖默认 Provider",
    )
    parser.add_argument(
        "--mode",
        choices=["auto", "turbo", "basic", "advanced"],
        help="auto: 双语查询固定解析为 basic；也可显式指定 turbo/basic/advanced",
    )
    parser.add_argument("--max-results", type=int, help="最终最多保留多少条结果")
    parser.add_argument("--max-chars-total", type=int, help="Parallel Direct 总摘录字符预算")
    parser.add_argument("--engine", help="OpenRouter Web Search engine，默认 parallel")
    parser.add_argument("--openrouter-model", help="OpenRouter 模型 slug")
    parser.add_argument(
        "--format",
        choices=["json", "markdown"],
        default="json",
        dest="output_format",
    )
    parser.add_argument("--config", help="config.toml 路径")
    parser.add_argument(
        "--no-fallback",
        action="store_true",
        help="provider=auto 时禁止 Parallel -> OpenRouter fallback",
    )
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    try:
        settings = load_settings(args.config)

        provider = args.provider or settings.provider
        requested_mode = args.mode or settings.mode
        max_results = args.max_results or settings.max_results
        if max_results < 1:
            raise ValueError("--max-results must be >= 1")

        if args.max_chars_total is not None:
            if args.max_chars_total < 1:
                raise ValueError("--max-chars-total must be >= 1")
            settings.max_chars_total = args.max_chars_total

        search_queries = [q.strip() for q in (args.search_queries or []) if q.strip()]
        validate_bilingual_queries(search_queries)

        mode = resolve_mode(requested_mode, search_queries)
        allow_fallback = settings.fallback and not args.no_fallback

        router = Router.build(
            settings,
            openrouter_engine=args.engine,
            openrouter_model=args.openrouter_model,
        )
        response = router.search(
            objective=args.objective.strip(),
            search_queries=search_queries,
            mode=mode,
            max_results=max_results,
            provider=provider,
            allow_fallback=allow_fallback,
        )

        if args.output_format == "markdown":
            print(render_markdown(response), end="")
        else:
            print(render_json(response))
        return 0

    except Exception as exc:
        print(f"universal-search error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
