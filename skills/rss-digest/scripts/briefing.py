#!/usr/bin/env python3
"""
简报生成模块
负责每日简报生成和已有文章扫描
"""

import asyncio
import datetime
import json
import re
import sys
from pathlib import Path
from typing import List

try:
    import yaml
except ImportError:
    print("错误: 缺少依赖库 yaml", file=sys.stderr)
    print("请运行: pip install pyyaml", file=sys.stderr)
    sys.exit(1)


def scan_existing_articles(output_dir: Path) -> List[dict]:
    """扫描日期目录中已有的文章文件，提取元数据用于简报生成"""
    existing = []
    if not output_dir.exists():
        return existing

    # Import here to avoid circular dependency
    from ai_summarizer import ArticleSummary

    for f in output_dir.iterdir():
        if not f.name.endswith(('-RSS.md', '-X.md')):
            continue

        try:
            with open(f, 'r', encoding='utf-8') as fh:
                content = fh.read()

            # 解析 frontmatter
            if not content.startswith('---'):
                continue
            fm_end = content.find('---', 3)
            if fm_end == -1:
                continue

            fm = yaml.safe_load(content[3:fm_end]) or {}
            body = content[fm_end + 3:].strip()

            # 提取标题（从 H1）
            title = ''
            h1_match = re.match(r'^#\s+(.+)', body)
            if h1_match:
                title = h1_match.group(1).strip()

            source_name = fm.get('rss_feed', '') or fm.get('x_user', '') or '未知'
            is_tweet = 'x_user' in fm
            tags = fm.get('tags', []) or []

            summary = ArticleSummary(
                chinese_title=title,
                core_viewpoint=fm.get('description', title) or title,
                key_points=[],
                conclusions=[],
                topics=tags,
                reading_time=fm.get('reading_time', 5)
            )

            existing.append({
                'title': title,
                'source_name': source_name,
                'source_type': 'twitter' if is_tweet else 'rss',
                'link': fm.get('link', ''),
                '_wikilink': f.name[:-3],
                'ai_summary': summary,
            })

        except Exception:
            continue

    return existing


def generate_briefing_file(
    articles: List[dict],
    output_dir: Path,
    briefing,
    briefing_date: datetime.datetime
) -> None:
    """生成每日简报文件"""
    date_str = briefing_date.strftime('%Y-%m-%d')
    date_folder = briefing_date.strftime('%Y%m%d')
    filename = f"简报-{date_folder}.md"
    filepath = output_dir / filename

    total_articles = len(articles)
    rss_count = sum(1 for a in articles if a.get('source_type') != 'twitter')
    x_count = total_articles - rss_count
    ai_count = sum(1 for a in articles if 'ai_summary' in a)

    # Frontmatter
    fm_lines = ["---"]
    fm_lines.append(f"created: {date_str}")
    fm_lines.append(f"updated: {date_str}")
    fm_lines.append("type: briefing")
    fm_lines.append(f"published: {date_str}")
    fm_lines.append(f"total_articles: {total_articles}")
    fm_lines.append(f"rss_articles: {rss_count}")
    fm_lines.append(f"x_bookmarks: {x_count}")
    fm_lines.append(f"ai_summarized: {ai_count}")
    fm_lines.append(f"highlights_count: {len(briefing.highlights)}")
    fm_lines.append("---")
    fm_lines.append("")

    # 正文
    display_date = briefing_date.strftime('%Y年%m月%d日')
    body_lines = [f"# 每日简报 - {display_date}", ""]

    # 今日要闻
    body_lines.append("## 今日要闻")
    body_lines.append("")
    for highlight in briefing.highlights:
        body_lines.append(f"- {highlight}")
    body_lines.append("")

    # 值得深读
    body_lines.append("## 值得深读")
    body_lines.append("")
    for rec in briefing.recommended:
        time_info = f"（{rec.reading_time} 分钟）" if rec.reading_time else ""
        wikilink = f"[[{rec.filename}]]" if rec.filename else f"**{rec.title}**"
        body_lines.append(f"- {wikilink}{time_info}: {rec.reason}")
    body_lines.append("")

    # 主题概览
    body_lines.append("## 主题概览")
    body_lines.append("")
    for topic, count in sorted(briefing.topics.items(), key=lambda x: x[1], reverse=True):
        body_lines.append(f"- **{topic}**: {count} 篇")
    body_lines.append("")

    # 写入文件
    content = '\n'.join(fm_lines + body_lines)
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)

    print(f"  已生成简报: {filepath}", file=sys.stderr)


async def run_briefing_only_mode(config: dict, start_date: datetime.datetime, end_date: datetime.datetime, folder_arg: str = None):
    """仅生成简报模式：扫描已有文章文件，生成每日简报"""
    ai_config = config.get('ai_summary', {})
    ai_enabled = ai_config.get('enabled', False)
    briefing_config = ai_config.get('briefing', {})
    output_config = config.get('output', {})

    if not ai_enabled or not briefing_config.get('enabled', False):
        print("错误: 简报功能未启用（需在配置中启用 ai_summary.enabled 和 ai_summary.briefing.enabled）", file=sys.stderr)
        sys.exit(1)

    # 确定目标目录
    if folder_arg:
        target_dir = Path(folder_arg)
    else:
        base_dir = Path(output_config.get('directory', 'project/rss'))
        date_folder = end_date.strftime('%Y%m%d')
        target_dir = base_dir / date_folder

    if not target_dir.exists():
        print(f"错误: 目录不存在: {target_dir}", file=sys.stderr)
        sys.exit(1)

    # 扫描已有文章
    existing_articles = scan_existing_articles(target_dir)
    if not existing_articles:
        print(f"未找到文章文件（{target_dir}）", file=sys.stderr)
        sys.exit(0)

    print(f"扫描到 {len(existing_articles)} 篇文章: {target_dir}", file=sys.stderr)

    # 初始化 AI
    from ai_summarizer import AISummarizer
    try:
        summarizer = AISummarizer(ai_config)
    except Exception as e:
        print(f"AI 初始化失败: {e}", file=sys.stderr)
        sys.exit(1)

    # 生成简报
    print(f"正在生成每日简报...", file=sys.stderr)
    try:
        briefing_result = await summarizer.generate_briefing(existing_articles)
        if briefing_result:
            # Import base_manager
            from base_manager import ensure_base_file

            generate_briefing_file(existing_articles, target_dir, briefing_result, end_date)
            # 更新 Obsidian Base
            base_dir = target_dir.parent if target_dir.name.isdigit() else target_dir
            base_config = output_config.get('base', {})
            ensure_base_file(
                base_dir,
                base_config.get('name', '01_RSS'),
                base_config.get('briefing_name', '00_RSS_SUMMARY')
            )
        else:
            print("简报生成失败", file=sys.stderr)
            sys.exit(1)
    except Exception as e:
        print(f"简报生成出错: {e}", file=sys.stderr)
        sys.exit(1)
