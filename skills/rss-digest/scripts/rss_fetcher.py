#!/usr/bin/env python3
"""
RSS 拉取模块
负责 RSS feed 抓取、日期筛选、去重
"""

import datetime
import hashlib
import html
import logging
import re
import sys
import urllib.request
from typing import List, Tuple
from urllib.parse import urlparse

try:
    import feedparser
except ImportError:
    print("错误: 缺少依赖库 feedparser", file=sys.stderr)
    print("请运行: pip install feedparser", file=sys.stderr)
    sys.exit(1)

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

# 无效摘要模式（HN 等站点的 RSS description 没有实际内容）
_USELESS_SUMMARY_PATTERNS = re.compile(
    r'^(comments?\.?\.?\.?|discuss|link|none|\s*)$', re.IGNORECASE
)


def fetch_rss_feed(url: str, max_articles: int = 50) -> List[dict]:
    """获取 RSS feed 内容"""
    try:
        print(f"    正在拉取: {url}", file=sys.stderr)

        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }

        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=10) as response:
            rss_content = response.read().decode('utf-8', errors='ignore')

        feed = feedparser.parse(rss_content)
        articles = []

        if hasattr(feed, 'entries') and len(feed.entries) > 0:
            print(f"    Entries count: {len(feed.entries)}", file=sys.stderr)
        else:
            print(f"    警告: 该 RSS 源没有文章", file=sys.stderr)
            if hasattr(feed, 'bozo') and feed.bozo:
                print(f"    解析错误: {feed.bozo_exception}", file=sys.stderr)
            return []

        for entry in feed.entries[:max_articles]:
            # 解析发布时间
            published = None
            if hasattr(entry, 'published_parsed') and entry.published_parsed:
                try:
                    published = datetime.datetime(*entry.published_parsed[:6])
                except Exception:
                    pass
            elif hasattr(entry, 'updated_parsed') and entry.updated_parsed:
                try:
                    published = datetime.datetime(*entry.updated_parsed[:6])
                except Exception:
                    pass

            if not published:
                published = datetime.datetime.now()

            # 提取内容
            content = ""
            if hasattr(entry, 'content') and entry.content:
                if isinstance(entry.content, list) and len(entry.content) > 0:
                    content = entry.content[0].value
                else:
                    content = str(entry.content)
            elif hasattr(entry, 'summary'):
                content = entry.summary
            elif hasattr(entry, 'description'):
                content = entry.description

            # 清理 HTML 标签和实体
            content_clean = re.sub(r'<[^>]+>', '', content)
            content_clean = html.unescape(content_clean)
            content_clean = ' '.join(content_clean.split())

            # 过滤无效摘要（如 HN 的 "Comments..."）
            summary = content_clean[:500] if content_clean else ''
            if _USELESS_SUMMARY_PATTERNS.match(summary.strip()):
                summary = ''

            article = {
                'title': entry.get('title', '无标题'),
                'link': entry.get('link', ''),
                'published': published,
                'summary': summary,
                'author': entry.get('author', ''),
            }
            articles.append(article)

        print(f"    成功获取 {len(articles)} 篇文章", file=sys.stderr)
        return articles

    except Exception as e:
        print(f"    错误: 获取失败 - {e}", file=sys.stderr)
        return []


def deduplicate_articles(articles: List[dict]) -> List[dict]:
    """去重文章（基于 URL）"""
    seen = set()
    unique_articles = []
    for article in articles:
        url = article['link']
        if not url:
            continue
        parsed = urlparse(url)
        normalized_url = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"

        # 直接用 normalized_url 去重，不再使用 MD5
        if normalized_url not in seen:
            seen.add(normalized_url)
            unique_articles.append(article)
    return unique_articles


def filter_articles_by_date(
    articles: List[dict],
    start_date: datetime.datetime,
    end_date: datetime.datetime
) -> List[dict]:
    """按日期范围筛选文章"""
    filtered = []
    for article in articles:
        if article['published'] and start_date <= article['published'] <= end_date:
            filtered.append(article)
    return filtered


def rebuild_articles_by_source(articles: List[dict]) -> dict:
    """从文章列表重建按源分组的字典"""
    articles_by_source = {}
    for article in articles:
        source_name = article.get('source_name', '未知')
        source_category = article.get('source_category', '未分类')
        if source_name not in articles_by_source:
            articles_by_source[source_name] = ([], source_category)
        articles_by_source[source_name][0].append(article)
    return articles_by_source
