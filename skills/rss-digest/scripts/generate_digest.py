#!/usr/bin/env python3
"""
RSS 订阅简报生成器
从配置的 RSS 源拉取最新内容，生成智能简报

主入口：CLI 参数解析和工作流程编排
"""

import argparse
import asyncio
import datetime
import logging
import sys
from pathlib import Path

try:
    import yaml
except ImportError:
    print("错误: 缺少依赖库 yaml", file=sys.stderr)
    print("请运行: pip install pyyaml", file=sys.stderr)
    sys.exit(1)

# 导入功能模块
from rss_fetcher import fetch_rss_feed, filter_articles_by_date, deduplicate_articles, rebuild_articles_by_source
from article_writer import generate_article_files
from briefing import run_briefing_only_mode, scan_existing_articles, generate_briefing_file
from base_manager import ensure_base_file
from re_summary import run_re_summary
from topic_dedup import deduplicate_articles_by_topic

# 导入 AI 和书签模块
try:
    from ai_summarizer import AISummarizer
    from content_fetcher import ArticleContentFetcher
except ImportError:
    AISummarizer = None
    ArticleContentFetcher = None


logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)


def load_config(config_path: str) -> dict:
    """加载配置文件"""
    with open(config_path, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)


def parse_date_range(args) -> tuple:
    """解析日期范围参数"""
    today = datetime.datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)

    if hasattr(args, 'start_date') and hasattr(args, 'end_date') and args.start_date and args.end_date:
        start_date = datetime.datetime.strptime(args.start_date, '%Y-%m-%d')
        end_date = datetime.datetime.strptime(args.end_date, '%Y-%m-%d').replace(
            hour=23, minute=59, second=59
        )
    elif hasattr(args, 'date') and args.date:
        target_date = datetime.datetime.strptime(args.date, '%Y-%m-%d')
        start_date = target_date.replace(hour=0, minute=0, second=0)
        end_date = target_date.replace(hour=23, minute=59, second=59)
    elif hasattr(args, 'days') and args.days:
        start_date = today - datetime.timedelta(days=args.days)
        end_date = today.replace(hour=23, minute=59, second=59)
    else:
        yesterday = today - datetime.timedelta(days=1)
        start_date = yesterday
        end_date = today.replace(hour=23, minute=59, second=59)

    return start_date, end_date


def scan_existing_links(base_dir: Path) -> set:
    """扫描输出目录（含子文件夹）中已有文件的 link，用于去重"""
    existing = set()
    if not base_dir.exists():
        return existing
    for pattern in ('*-RSS.md', '*-X.md'):
        for f in base_dir.rglob(pattern):
            try:
                with open(f, 'r', encoding='utf-8') as fh:
                    in_fm = False
                    for line in fh:
                        line = line.strip()
                        if line == '---':
                            if in_fm:
                                break
                            in_fm = True
                            continue
                        if in_fm and line.startswith('link:'):
                            link = line.split(':', 1)[1].strip().strip('"').strip("'")
                            if link:
                                existing.add(link)
                            break
            except Exception:
                continue
    return existing


async def process_articles_with_ai(
    articles: list,
    summarizer,
    fetcher,
    ai_config: dict
) -> list:
    """使用 AI 处理文章（内容抓取 + 总结生成）"""
    if not summarizer or not fetcher:
        return articles

    print("\n正在使用 AI 增强文章内容...", file=sys.stderr)

    # 第一步：批量获取完整内容
    print("  步骤 1/2: 抓取完整内容", file=sys.stderr)
    max_concurrent = ai_config.get('max_concurrent', 5)
    enriched_articles = await fetcher.batch_fetch(articles, max_concurrent=max_concurrent)

    # 第二步：批量生成 AI 总结
    print("  步骤 2/2: 生成 AI 总结", file=sys.stderr)
    summaries = await summarizer.summarize_batch(enriched_articles)

    # 合并总结到文章
    for article, summary in zip(enriched_articles, summaries):
        if summary:
            article['ai_summary'] = summary
        else:
            article['ai_summary'] = summarizer._rule_based_summary(article)

    return enriched_articles


def show_usage():
    """输出详细使用指南"""
    print("""RSS 订阅简报生成器 - 使用指南
==============================

运行模式：
  完整模式    拉取 RSS → AI 摘要 → 生成简报
  简报模式    --briefing-only   基于已有文章生成简报
  重新摘要    --re-summary      对指定文章重新生成 AI 摘要
  指定源拉取  --source NAME     仅拉取指定 RSS 源

日期参数（互斥，优先级从上到下）：
  --start-date + --end-date    指定日期范围
  --date YYYY-MM-DD            单个日期
  --days N                     最近 N 天
  （不传）                      默认昨天到今天

示例：
  # 完整模式
  python generate_digest.py --date 2026-04-27
  python generate_digest.py --days 3
  python generate_digest.py --source "宝玉的分享" --date 2026-04-27
  python generate_digest.py --source "宝玉的分享" --source "Hacker News" --days 1

  # 仅生成简报
  python generate_digest.py --briefing-only
  python generate_digest.py --briefing-only --date 2026-04-27
  python generate_digest.py --briefing-only --folder project/rss/20260427

  # 重新摘要
  python generate_digest.py --re-summary "文章标题关键词"
  python generate_digest.py --re-summary "文章标题" --prompt "提取实操步骤"

  # 查询配置
  python generate_digest.py --list-sources
  python generate_digest.py --show-config
""")


def show_list_sources(config: dict):
    """输出可用 RSS 源列表"""
    sources = config.get('sources', [])
    print("可用 RSS 源：")
    for i, source in enumerate(sources, 1):
        line = f"  {i}. {source['name']} ({source.get('category', '未分类')}) - {source['url']}"
        if source.get('remark'):
            line += f" - 备注: {source['remark']}"
        print(line)


def mask_api_key(config: dict) -> dict:
    """脱敏配置中的 API 密钥"""
    import copy
    masked = copy.deepcopy(config)
    ai = masked.get('ai_summary', {})
    if 'api_key' in ai and ai['api_key']:
        key = ai['api_key']
        if len(key) > 6:
            ai['api_key'] = key[:3] + '****' + key[-4:]
        else:
            ai['api_key'] = '****'
    return masked


def main():
    parser = argparse.ArgumentParser(
        description='RSS 订阅简报生成器',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='使用 --usage 查看详细使用指南和示例'
    )
    # 查询参数（early return）
    parser.add_argument('--usage', action='store_true',
                        help='显示详细使用指南和示例')
    parser.add_argument('--list-sources', action='store_true',
                        help='列出所有可用的 RSS 源')
    parser.add_argument('--show-config', action='store_true',
                        help='显示完整配置（API 密钥已脱敏）')

    # 日期参数
    parser.add_argument('--start-date', help='开始日期 (YYYY-MM-DD)')
    parser.add_argument('--end-date', help='结束日期 (YYYY-MM-DD)')
    parser.add_argument('--date', help='单个日期 (YYYY-MM-DD)')
    parser.add_argument('--days', type=int, help='最近 N 天')

    # 模式参数
    parser.add_argument('--briefing-only', action='store_true',
                        help='仅生成简报（基于已有文章，不拉取 RSS）')
    parser.add_argument('--folder', help='指定文章所在文件夹（相对于项目根目录）')
    parser.add_argument('--re-summary', help='重新摘要指定文章（文件名或关键词）')
    parser.add_argument('--prompt', help='自定义摘要提示词（配合 --re-summary 使用）')
    parser.add_argument('--source', action='append',
                        help='指定 RSS 源名称（精确匹配，可多次使用）')

    args = parser.parse_args()

    # --usage: 输出详细使用指南后退出
    if args.usage:
        show_usage()
        return

    # 加载配置（固定路径: skill 目录下的 rss-config.yaml）
    config_path = Path(__file__).resolve().parents[1] / 'rss-config.yaml'
    try:
        config = load_config(str(config_path))
    except FileNotFoundError:
        print(f"错误: 配置文件不存在: {config_path}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"错误: 无法加载配置文件: {e}", file=sys.stderr)
        sys.exit(1)

    # --list-sources: 输出源列表后退出
    if args.list_sources:
        show_list_sources(config)
        return

    # --show-config: 输出脱敏配置后退出
    if args.show_config:
        print(yaml.dump(mask_api_key(config), allow_unicode=True, default_flow_style=False))
        return

    # 解析日期范围
    start_date, end_date = parse_date_range(args)

    # 简报专用模式：跳过 RSS 拉取，直接基于已有文章生成简报
    if args.briefing_only:
        asyncio.run(run_briefing_only_mode(config, start_date, end_date, args.folder))
        return

    # 重新摘要模式：对指定文章重新生成 AI 摘要
    if args.re_summary:
        asyncio.run(run_re_summary(config, args.re_summary, args.prompt))
        return

    # 获取配置
    all_sources = config.get('sources', [])

    # --source: 过滤指定源
    if args.source:
        sources = [s for s in all_sources if s['name'] in args.source]
        not_found = [n for n in args.source if n not in {s['name'] for s in sources}]
        if not_found:
            print(f"错误: 未找到源: {', '.join(not_found)}", file=sys.stderr)
            print(f"可用源: {', '.join(s['name'] for s in all_sources)}", file=sys.stderr)
            sys.exit(1)
        print(f"指定拉取 {len(sources)} 个源: {', '.join(s['name'] for s in sources)}", file=sys.stderr)
    else:
        sources = all_sources

    content_config = config.get('content', {})
    dedup_config = config.get('dedup', {})
    ai_config = config.get('ai_summary', {})

    max_articles = content_config.get('max_articles_per_source', 50)
    dedup_enabled = dedup_config.get('enabled', True)

    # 初始化 AI 模块
    summarizer = None
    fetcher = None
    ai_enabled = ai_config.get('enabled', False)

    if ai_enabled:
        try:
            summarizer = AISummarizer(ai_config)
            fetcher = ArticleContentFetcher(ai_config)
            print("AI 总结已启用", file=sys.stderr)
        except Exception as e:
            print(f"AI 初始化失败: {e}", file=sys.stderr)
            print("  将使用传统模式", file=sys.stderr)
            ai_enabled = False

    # 获取所有文章
    all_articles = []

    print(f"\n正在获取 {len(sources)} 个 RSS 源...", file=sys.stderr)

    for source in sources:
        source_name = source['name']
        source_url = source['url']
        source_category = source.get('category', '未分类')

        print(f"\n[{source_name}]", file=sys.stderr)
        articles = fetch_rss_feed(source_url, max_articles)

        if not articles:
            print(f"  跳过（没有文章）", file=sys.stderr)
            continue

        # 按日期筛选
        filtered = filter_articles_by_date(articles, start_date, end_date)
        print(f"  筛选后: {len(filtered)} 篇", file=sys.stderr)

        if filtered:
            for article in filtered:
                article['source_name'] = source_name
                article['source_category'] = source_category
            all_articles.extend(filtered)

    # 去重（在 AI 处理之前，避免浪费 API 调用）
    if dedup_enabled and all_articles:
        print(f"\n去重前: {len(all_articles)} 篇文章", file=sys.stderr)
        all_articles = deduplicate_articles(all_articles)
        print(f"去重后: {len(all_articles)} 篇文章", file=sys.stderr)

    # 本地文件去重（避免重复生成已有文章）
    total_before_local_dedup = len(all_articles)
    output_config = config.get('output', {})
    base_dir = Path(output_config.get('directory', 'project/rss'))
    date_folder = end_date.strftime('%Y%m%d')
    output_dir = base_dir / date_folder
    if dedup_enabled and all_articles:
        existing_links = scan_existing_links(base_dir)
        before = len(all_articles)
        all_articles = [
            a for a in all_articles
            if a.get('link', '') not in existing_links
        ]
        skipped = before - len(all_articles)
        if skipped:
            print(f"  跳过 {skipped} 篇已存在文章", file=sys.stderr)

    # AI 处理（仅处理去重后的文章）
    if ai_enabled and all_articles and summarizer and fetcher:
        all_articles = asyncio.run(process_articles_with_ai(
            all_articles,
            summarizer,
            fetcher,
            ai_config
        ))

        # 主题聚类去重
        all_articles = asyncio.run(deduplicate_articles_by_topic(all_articles, summarizer, ai_config))

    # 按源重新分组（仅用于统计）
    articles_by_source = rebuild_articles_by_source(all_articles)

    # 生成文章文件
    generated = 0
    if all_articles:
        output_dir.mkdir(parents=True, exist_ok=True)

        print(f"\n正在生成文章文件...", file=sys.stderr)
        generated = generate_article_files(all_articles, output_dir, config)
    else:
        if total_before_local_dedup > 0:
            print(f"\n所有文章均已存在（{total_before_local_dedup} 篇），无新文章需要生成", file=sys.stderr)
        else:
            print("\n未找到符合条件的文章", file=sys.stderr)

    # 生成每日简报
    briefing_config = ai_config.get('briefing', {})
    briefing_enabled = briefing_config.get('enabled', False)

    if briefing_enabled and ai_enabled and summarizer:
        output_dir.mkdir(parents=True, exist_ok=True)

        # 合并已有文章 + 新文章
        existing_articles = scan_existing_articles(output_dir)
        briefing_articles = existing_articles + all_articles

        if briefing_articles:
            print(f"\n正在生成每日简报（共 {len(briefing_articles)} 篇文章）...", file=sys.stderr)
            try:
                async def run_briefing_generation():
                    return await summarizer.generate_briefing(briefing_articles)

                briefing_result = asyncio.run(run_briefing_generation())

                if briefing_result:
                    briefing_date = end_date.replace(hour=0, minute=0, second=0, microsecond=0)
                    generate_briefing_file(briefing_articles, output_dir, briefing_result, briefing_date)
                else:
                    print("  简报生成失败", file=sys.stderr)

            except Exception as e:
                print(f"  简报生成出错: {e}", file=sys.stderr)

    # 自动创建 Obsidian Base（放在 base_dir 根目录）
    if output_dir.exists():
        base_config = output_config.get('base', {})
        ensure_base_file(
            base_dir,
            base_config.get('name', '01_RSS'),
            base_config.get('briefing_name', '00_RSS_SUMMARY')
        )

    # 统计输出
    ai_count = sum(1 for a in all_articles if 'ai_summary' in a)
    print(f"\n完成！", file=sys.stderr)
    print(f"  - 处理了 {len(sources)} 个 RSS 源", file=sys.stderr)
    if all_articles:
        print(f"  - 找到了 {len(all_articles)} 篇文章", file=sys.stderr)
        print(f"  - 生成了 {generated} 个文件", file=sys.stderr)
        print(f"  - AI 总结: {ai_count} 篇", file=sys.stderr)
    print(f"  - 日期范围: {start_date.strftime('%Y-%m-%d')} 至 {end_date.strftime('%Y-%m-%d')}", file=sys.stderr)


if __name__ == '__main__':
    main()
