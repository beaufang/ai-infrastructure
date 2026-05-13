#!/usr/bin/env python3
"""
文章文件写入模块
负责生成独立的 Markdown 文件，包含安全的 frontmatter 生成
"""

import datetime
import json
import re
import sys
from pathlib import Path
from typing import Dict, List

try:
    import yaml
except ImportError:
    print("错误: 缺少依赖库 yaml", file=sys.stderr)
    print("请运行: pip install pyyaml", file=sys.stderr)
    sys.exit(1)


def _sanitize_filename(title: str, max_len: int = 80) -> str:
    """将标题转为合法文件名"""
    # 去除非法字符
    name = re.sub(r'[\\/:*?"<>|]', '', title)
    # 去除首尾空白和点号
    name = name.strip().strip('.')
    # 合并空白
    name = ' '.join(name.split())

    # 对中文文本，直接截断而不是按空格分割
    if len(name) > max_len:
        # 检查是否包含中文
        has_chinese = bool(re.search(r'[一-鿿]', name))
        if has_chinese:
            # 中文直接截断
            name = name[:max_len]
        else:
            # 英文按空格分割避免截断单词
            name = name[:max_len].rsplit(' ', 1)[0]

    return name or 'Untitled'


def _build_frontmatter(article: dict, config: dict, today_str: str) -> Dict:
    """构建 frontmatter 字典"""
    ai_summary = article.get('ai_summary')
    source_name = article.get('source_name', '未知')
    source_category = article.get('source_category', '未分类')
    link = article.get('link', '')
    published = article.get('published')
    is_tweet = article.get('source_type') == 'twitter'
    original_title = article.get('title', '无标题')

    # 确定中文标题
    if ai_summary and hasattr(ai_summary, 'chinese_title') and ai_summary.chinese_title:
        display_title = ai_summary.chinese_title
    else:
        display_title = original_title

    # Frontmatter 字段
    fm = {
        'created': today_str,
        'updated': today_str,
        'source': 'twitter' if is_tweet else 'rss',
        'tags': [],
        'keywords': [],
        'status': 'wait',
        'type': 'clip',
        'description': '',
        'link': link,
        'feed': source_name,
        'category': source_category,
        'published': published.strftime('%Y-%m-%d') if published else today_str,
    }

    # AI 提取的标签和描述
    if ai_summary:
        if ai_summary.topics:
            fm['tags'] = [t.replace(' ', '-') for t in ai_summary.topics]
        if ai_summary.core_viewpoint:
            fm['description'] = ai_summary.core_viewpoint
        # 添加 reading_time 字段
        if ai_summary.reading_time:
            fm['reading_time'] = ai_summary.reading_time

    # 别名（原文标题）
    alias = []
    if original_title != display_title:
        alias = [original_title]
    if alias:
        fm['alias'] = alias

    # 作者
    author = article.get('author', '')
    if author:
        fm['author'] = author

    # Twitter 特有字段
    if is_tweet:
        fm['x_user'] = source_name
        fm['x_category'] = source_category
        tweet_id = article.get('tweet_id', '')
        if tweet_id:
            fm['tweet_id'] = tweet_id
        likes = article.get('likes', 0)
        if likes:
            fm['likes'] = likes

    # RSS 特有字段
    else:
        fm['rss_feed'] = source_name
        fm['rss_category'] = source_category

    # 重复文章标记
    if article.get('duplicate_of'):
        fm['duplicate_of'] = article['duplicate_of']

    return fm


def generate_article_files(
    articles: List[dict],
    output_dir: Path,
    config: dict
) -> int:
    """为每篇文章生成独立的 Markdown 文件"""
    today_str = datetime.datetime.now().strftime('%Y-%m-%d')
    generated = 0
    used_names: Dict[str, int] = {}

    for article in articles:
        original_title = article.get('title', '无标题')
        ai_summary = article.get('ai_summary')
        display_title = original_title

        # 确定中文标题
        if ai_summary and hasattr(ai_summary, 'chinese_title') and ai_summary.chinese_title:
            display_title = ai_summary.chinese_title

        # 文件名
        filename_base = _sanitize_filename(display_title)
        suffix = '-X' if article.get('source_type') == 'twitter' else '-RSS'
        filename = f"{filename_base}{suffix}.md"

        # 处理重名
        if filename in used_names:
            used_names[filename] += 1
            filename = f"{filename_base}{suffix}-{used_names[filename]}.md"
        else:
            used_names[filename] = 0

        # 构建 frontmatter 字典
        fm_dict = _build_frontmatter(article, config, today_str)

        # 生成 YAML frontmatter（使用 yaml.dump 确保安全）
        fm_lines = ["---"]
        fm_lines.append(yaml.dump(fm_dict, allow_unicode=True, default_flow_style=False).strip())
        fm_lines.append("---")
        fm_lines.append("")

        # 正文
        body_lines = [f"# {display_title}", ""]

        if ai_summary:
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
        elif article.get('summary'):
            body_lines.append("## 摘要")
            body_lines.append("")
            body_lines.append(f"> {article['summary'][:500]}")

        # 引用行
        body_lines.append("")
        published = article.get('published')
        published_display = published.strftime('%Y-%m-%d %H:%M') if published else '未知'
        source_name = article.get('source_name', '未知')
        link = article.get('link', '')
        is_tweet = article.get('source_type') == 'twitter'

        if is_tweet:
            body_lines.append(f"> 推文: [{link}]({link}) | 用户: {source_name} | 发布: {published_display}")
        else:
            body_lines.append(f"> 原文: [{link}]({link}) | 来源: {source_name} | 发布: {published_display}")
        body_lines.append("")

        # 写入文件
        content = '\n'.join(fm_lines + body_lines)
        filepath = output_dir / filename
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)

        article['_wikilink'] = filename[:-3]  # 去掉 .md 后缀
        generated += 1

    return generated
