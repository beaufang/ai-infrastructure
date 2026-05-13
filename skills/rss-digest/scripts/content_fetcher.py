#!/usr/bin/env python3
"""
文章内容抓取模块
智能获取文章内容（RSS 或完整网页）
"""

import asyncio
import logging
import re
import sys
import urllib.request
from typing import Dict, List, Optional

try:
    import trafilatura
except ImportError:
    trafilatura = None
    print("警告: trafilatura 未安装，将跳过完整文章抓取", file=sys.stderr)
    print("安装命令: pip install trafilatura", file=sys.stderr)


logger = logging.getLogger(__name__)


class ArticleContentFetcher:
    """智能文章内容获取器"""

    def __init__(self, config: dict):
        """初始化内容获取器

        Args:
            config: 配置字典，包含：
                - content_strategy: 内容获取策略（'rss_only', 'fetch_full', 'auto'）
                - fetch_full_min_length: 自动抓取的阈值（字数）
        """
        self.strategy = config.get('content_strategy', 'auto')
        self.min_length = config.get('fetch_full_min_length', 500)

    async def fetch_content(self, article: Dict) -> Dict:
        """获取文章内容（智能混合策略）"""
        # X/Twitter 书签不可通过网页抓取（需要 JavaScript），直接使用推文原文
        if article.get('source_type') == 'twitter':
            return self._use_rss_content(article)

        rss_content = article.get('summary', '')

        if self.strategy == 'rss_only':
            return self._use_rss_content(article)

        elif self.strategy == 'fetch_full':
            full_content = await self._fetch_full_article(article.get('link', ''))
            if full_content:
                return {**article, **full_content}
            else:
                return self._use_rss_content(article)

        elif self.strategy == 'auto':
            if len(rss_content) < self.min_length:
                print(f"    RSS 内容不足（{len(rss_content)}字），尝试抓取完整文章...", file=sys.stderr)
                full_content = await self._fetch_full_article(article.get('link', ''))
                if full_content:
                    return {**article, **full_content}

            return self._use_rss_content(article)

        return self._use_rss_content(article)

    async def _fetch_full_article(self, url: str) -> Optional[Dict]:
        """抓取完整文章内容：urllib 下载（带请求头） + trafilatura 解析，失败后二次降级"""
        if not url:
            return None

        try:
            loop = asyncio.get_event_loop()
            html_content = await loop.run_in_executor(None, self._download_with_headers, url)
            if not html_content:
                return None

            # 方案 1: trafilatura 解析（精确提取正文）
            content = await loop.run_in_executor(None, self._extract_with_trafilatura, html_content)
            if content and len(content) >= 200:
                return self._build_content_result(content, html_content)

            # 方案 2: 基础 HTML 清理（二次降级）
            print(f"    trafilatura 解析结果不足，尝试基础 HTML 清理...", file=sys.stderr)
            content = self._basic_html_to_text(html_content)
            if content and len(content) >= 200:
                return self._build_content_result(content, html_content)

            print(f"    所有抓取方案失败: 内容过短", file=sys.stderr)
            return None

        except Exception as e:
            logger.warning(f"抓取完整文章失败 {url}: {e}")
            print(f"    抓取失败: {e}", file=sys.stderr)
            return None

    def _download_with_headers(self, url: str) -> Optional[str]:
        """带 User-Agent 的 HTTP 下载"""
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36'
        }
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=15) as resp:
            return resp.read().decode('utf-8', errors='ignore')

    def _extract_with_trafilatura(self, html: str) -> Optional[str]:
        """用 trafilatura 从 HTML 提取正文"""
        if not trafilatura:
            return None
        content = trafilatura.extract(html, include_comments=False, include_tables=True, no_fallback=False)
        return ' '.join(content.split()) if content else None

    def _basic_html_to_text(self, html: str) -> Optional[str]:
        """基础 HTML → 纯文本（二次降级）"""
        import html as html_module
        # 移除 script/style/nav/header/footer
        html = re.sub(r'<(script|style|nav|header|footer)[^>]*>.*?</\1>', '', html, flags=re.DOTALL | re.IGNORECASE)
        # 移除所有 HTML 标签
        text = re.sub(r'<[^>]+>', ' ', html)
        # 清理空白
        text = re.sub(r'\s+', ' ', text).strip()
        # 解码 HTML 实体
        text = html_module.unescape(text)
        return text if len(text) >= 200 else None

    def _build_content_result(self, content: str, html_content: str) -> Dict:
        """构建内容结果字典"""
        images = self._extract_images(html_content)
        return {
            'content': content,
            'source': 'full',
            'word_count': len(content.split()),
            'images': images[:3]
        }

    def _use_rss_content(self, article: Dict) -> Dict:
        """使用 RSS 内容"""
        content = article.get('summary', '')
        if not content:
            content = article.get('title', '')

        return {
            **article,
            'content': content,
            'source': 'rss',
            'word_count': len(content.split()),
            'images': []
        }

    def _extract_images(self, html_content: str) -> List[str]:
        """从 HTML 中提取图片 URL"""
        try:
            img_pattern = r'<img[^>]+src=["\']([^"\']+)["\']'
            images = re.findall(img_pattern, html_content)

            valid_images = []
            for img in images:
                if img.endswith(('.jpg', '.jpeg', '.png', '.gif', '.webp')):
                    valid_images.append(img)

            return valid_images[:5]

        except Exception as e:
            logger.warning(f"提取图片失败: {e}")
            return []

    async def batch_fetch(self, articles: List[Dict], max_concurrent: int = 5) -> List[Dict]:
        """并发批量获取文章内容

        Args:
            articles: 文章列表
            max_concurrent: 最大并发数

        Returns:
            增强后的文章列表
        """
        semaphore = asyncio.Semaphore(max_concurrent)

        async def process_with_limit(article):
            async with semaphore:
                return await self.fetch_content(article)

        try:
            results = await asyncio.gather(
                *[process_with_limit(a) for a in articles],
                return_exceptions=True
            )

            output = []
            for article, result in zip(articles, results):
                if isinstance(result, Exception):
                    logger.error(f"获取内容失败: {result}")
                    output.append(self._use_rss_content(article))
                else:
                    output.append(result)
            return output

        except Exception as e:
            logger.error(f"批量获取失败: {e}")
            return [self._use_rss_content(a) for a in articles]


# 测试代码
if __name__ == '__main__':
    config = {
        'content_strategy': 'auto',
        'fetch_full_min_length': 500
    }

    test_article = {
        'title': '测试文章',
        'link': 'https://www.ruanyifeng.com/blog/2026/04/weekly-issue-394.html',
        'summary': '这是一篇简短的摘要'
    }

    async def test():
        fetcher = ArticleContentFetcher(config)
        result = await fetcher.fetch_content(test_article)
        if result:
            print(f"内容来源: {result['source']}")
            print(f"字数: {result['word_count']}")
            print(f"内容预览: {result['content'][:100]}...")
        else:
            print("获取失败")

    asyncio.run(test())
