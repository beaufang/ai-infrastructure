#!/usr/bin/env python3
"""
重新摘要模块
负责对指定文章重新生成 AI 摘要
"""

import asyncio
import datetime
import json
import re
import sys
from pathlib import Path

try:
    import yaml
except ImportError:
    print("错误: 缺少依赖库 yaml", file=sys.stderr)
    print("请运行: pip install pyyaml", file=sys.stderr)
    sys.exit(1)


def find_article_file(name_pattern: str, config: dict) -> Path:
    """在输出目录中查找匹配的文章文件（支持文件名关键词模糊匹配）"""
    output_config = config.get('output', {})
    base_dir = Path(output_config.get('directory', 'project/rss'))

    # 去掉 .md 后缀（如果用户带了）
    name_pattern = name_pattern.removesuffix('.md')

    candidates = []
    for pattern in ('*-RSS.md', '*-X.md'):
        for f in base_dir.rglob(pattern):
            # 匹配策略：文件名（不含 .md）包含关键词，或关键词包含文件名
            stem = f.stem
            if name_pattern in stem or stem in name_pattern:
                candidates.append(f)

    if not candidates:
        return None
    if len(candidates) == 1:
        return candidates[0]

    # 多个匹配时打印列表让用户选择
    print(f"找到 {len(candidates)} 个匹配文件：", file=sys.stderr)
    for i, f in enumerate(candidates, 1):
        print(f"  {i}. {f}", file=sys.stderr)
    return candidates[0]


async def run_re_summary(config: dict, name_pattern: str, custom_prompt: str = ''):
    """重新摘要指定文章：查找文件 → 抓取原文 → AI 摘要 → 更新文件"""
    ai_config = config.get('ai_summary', {})
    ai_enabled = ai_config.get('enabled', False)

    if not ai_enabled:
        print("错误: AI 总结未启用（需在配置中启用 ai_summary.enabled 并安装 openai 库）", file=sys.stderr)
        sys.exit(1)

    # Import modules
    from ai_summarizer import AISummarizer
    from content_fetcher import ArticleContentFetcher

    # 查找文件
    filepath = find_article_file(name_pattern, config)
    if not filepath:
        print(f"未找到匹配的文章: {name_pattern}", file=sys.stderr)
        sys.exit(1)

    print(f"找到文章: {filepath}", file=sys.stderr)

    # 读取 frontmatter
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    if not content.startswith('---'):
        print("错误: 文件格式不正确（缺少 frontmatter）", file=sys.stderr)
        sys.exit(1)

    fm_end = content.find('---', 3)
    if fm_end == -1:
        print("错误: frontmatter 格式不正确", file=sys.stderr)
        sys.exit(1)

    fm = yaml.safe_load(content[3:fm_end]) or {}
    link = fm.get('link', '')
    original_title = fm.get('alias', [fm.get('description', '')])
    if isinstance(original_title, list):
        original_title = original_title[0] if original_title else ''

    if not link:
        print("错误: 文章缺少 link 字段，无法重新抓取原文", file=sys.stderr)
        sys.exit(1)

    # 抓取原文
    print(f"正在抓取原文: {link}", file=sys.stderr)
    fetcher = ArticleContentFetcher(ai_config)

    article = {
        'title': original_title or link,
        'link': link,
        'summary': '',
        'source_name': fm.get('rss_feed', '') or fm.get('x_user', '') or '未知',
        'source_category': fm.get('rss_category', '') or fm.get('x_category', '') or '未分类',
    }

    fetched = await fetcher.fetch_content(article)
    article_content = fetched.get('content', '')

    if not article_content or len(article_content) < 50:
        print("错误: 无法获取文章原文内容", file=sys.stderr)
        sys.exit(1)

    print(f"获取到原文 ({len(article_content)} 字)", file=sys.stderr)

    # AI 摘要
    summarizer = AISummarizer(ai_config)
    summary_input = {
        'title': original_title or link,
        'link': link,
        'content': article_content,
    }

    if custom_prompt:
        print(f"使用自定义提示词: {custom_prompt}", file=sys.stderr)

    print("正在生成 AI 摘要...", file=sys.stderr)
    ai_summary = await summarizer.summarize_article(summary_input, custom_prompt=custom_prompt)

    if not ai_summary:
        print("AI 摘要生成失败", file=sys.stderr)
        sys.exit(1)

    # 重建文件内容（保留原 frontmatter，更新正文）
    is_tweet = 'x_user' in fm
    source_name = fm.get('rss_feed', '') or fm.get('x_user', '') or '未知'
    source_category = fm.get('rss_category', '') or fm.get('x_category', '') or '未分类'
    published = fm.get('published', '')
    today_str = datetime.date.today().strftime('%Y-%m-%d')

    # 更新 frontmatter
    fm['updated'] = today_str
    if ai_summary.topics:
        fm['tags'] = [t.replace(' ', '-') for t in ai_summary.topics]
    if ai_summary.core_viewpoint:
        fm['description'] = ai_summary.core_viewpoint
    if ai_summary.reading_time:
        fm['reading_time'] = ai_summary.reading_time

    fm_lines = ["---"]
    for key, val in fm.items():
        if isinstance(val, str):
            fm_lines.append(f'{key}: "{val}"')
        elif isinstance(val, list):
            fm_lines.append(f'{key}: {json.dumps(val, ensure_ascii=False)}')
        elif isinstance(val, bool):
            fm_lines.append(f'{key}: {"true" if val else "false"}')
        elif val is None:
            fm_lines.append(f'{key}: ""')
        else:
            fm_lines.append(f'{key}: {val}')
    fm_lines.append("---")
    fm_lines.append("")

    # 正文
    display_title = ai_summary.chinese_title if ai_summary.chinese_title else original_title
    body_lines = [f"# {display_title}", ""]

    body_lines.append("## 关键要点")
    body_lines.append("")
    for point in ai_summary.key_points:
        body_lines.append(f"- {point}")

    if ai_summary.practical_knowledge:
        body_lines.append("")
        body_lines.append("## 实操要点")
        body_lines.append("")
        for item in ai_summary.practical_knowledge:
            body_lines.append(f"- {item}")

    if ai_summary.conclusions:
        body_lines.append("")
        body_lines.append("## 主要结论")
        body_lines.append("")
        for conclusion in ai_summary.conclusions:
            body_lines.append(f"- {conclusion}")

    # 引用行
    body_lines.append("")
    published_display = published if published else '未知'
    if is_tweet:
        body_lines.append(f"> 推文: [{link}]({link}) | 用户: {source_name} | 发布: {published_display}")
    else:
        body_lines.append(f"> 原文: [{link}]({link}) | 来源: {source_name} | 发布: {published_display}")
    body_lines.append("")

    # 写入
    new_content = '\n'.join(fm_lines + body_lines)
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(new_content)

    print(f"已更新摘要: {filepath}", file=sys.stderr)
    print(f"  标题: {display_title}")
    print(f"  要点: {len(ai_summary.key_points)} 个")
    if ai_summary.practical_knowledge:
        print(f"  实操: {len(ai_summary.practical_knowledge)} 个")
    print(f"  结论: {len(ai_summary.conclusions)} 个")
