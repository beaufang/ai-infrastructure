#!/usr/bin/env python3
"""
AI 总结引擎
支持 OpenAI 兼容接口（包括 OpenAI 官方、DeepSeek、月之暗面等）
"""

import asyncio
import json
import logging
import os
import sys
from pathlib import Path
from typing import Dict, List, Optional

try:
    from pydantic import BaseModel, Field
except ImportError:
    print("错误: 缺少依赖库 pydantic", file=sys.stderr)
    print("请运行: pip install pydantic", file=sys.stderr)
    sys.exit(1)

from prompts import ARTICLE_SYSTEM_PROMPT, ARTICLE_USER_TEMPLATE, BRIEFING_SYSTEM_PROMPT, BRIEFING_USER_TEMPLATE

logger = logging.getLogger(__name__)


class ArticleSummary(BaseModel):
    """文章总结结构化模型"""
    chinese_title: str = Field(description="文章的中文标题（10-30字）")
    core_viewpoint: str = Field(description="核心观点（1-2句话）")
    key_points: List[str] = Field(description="关键要点（5-15个）")
    practical_knowledge: List[str] = Field(default_factory=list,
        description="实操知识（代码片段、操作步骤、命令、提示词模板、工具用法、技术细节）")
    conclusions: List[str] = Field(default_factory=list, description="主要结论")
    topics: List[str] = Field(default_factory=list, description="标签/主题")
    reading_time: int = Field(default=5, description="预估阅读时间（分钟）")


class RecommendedArticle(BaseModel):
    """简报推荐文章"""
    title: str = Field(description="文章中文标题")
    reason: str = Field(description="推荐理由")
    reading_time: int = Field(default=5, description="阅读时间（分钟）")
    filename: str = Field(default="", description="文章文件名（不含.md后缀），用于双链引用")


class DailyBriefing(BaseModel):
    """每日简报结构化模型"""
    highlights: List[str] = Field(description="今日要闻（3-5条）")
    recommended: List[RecommendedArticle] = Field(description="值得深读的文章推荐")
    topics: Dict[str, int] = Field(description="主题统计")


class AISummarizer:
    """AI 智能总结引擎（OpenAI 兼容接口）"""

    def __init__(self, config: dict):
        self.config = config
        self.api_key = config.get('api_key', '')

        if not self.api_key:
            raise ValueError("配置文件中 ai_summary.api_key 未设置")

        self.model = config.get('model', 'gpt-4o-mini')
        self.base_url = config.get('base_url', '')
        self.max_tokens = config.get('max_tokens', 3000)

        self.client = self._init_client()

    def _init_client(self):
        """初始化 OpenAI 兼容 API 客户端"""
        try:
            import openai
            if self.base_url:
                return openai.OpenAI(api_key=self.api_key, base_url=self.base_url)
            else:
                return openai.OpenAI(api_key=self.api_key)
        except ImportError:
            raise ValueError("使用 AI 总结需要安装 openai 库：pip install openai")

    async def summarize_article(self, article: dict, custom_prompt: str = '') -> Optional[ArticleSummary]:
        """生成单篇文章的结构化总结

        Args:
            article: 文章字典，包含 title、content、link 等字段

        Returns:
            ArticleSummary 对象，如果失败返回 None
        """
        try:
            content = article.get('content', '')[:16000]
            title = article.get('title', '无标题')
            url = article.get('link', '')

            user_prompt = ARTICLE_USER_TEMPLATE.format(
                title=title,
                content=content,
                url=url
            )

            if custom_prompt:
                user_prompt += f"\n\n**额外要求**：{custom_prompt}"

            # 在线程池中运行同步 SDK 调用，避免阻塞事件循环
            loop = asyncio.get_running_loop()
            summary = await loop.run_in_executor(
                None, self._call_api, user_prompt
            )

            return summary

        except Exception as e:
            logger.error(f"AI 总结失败: {e}")
            return None

    def _call_api(self, user_prompt: str) -> ArticleSummary:
        """同步调用 OpenAI 兼容 API（在线程池中执行）"""
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": ARTICLE_SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt}
                ],
                max_tokens=self.max_tokens,
                response_format={"type": "json_object"}
            )

            content = response.choices[0].message.content
            summary_data = json.loads(content)
            return ArticleSummary(**summary_data)

        except Exception as e:
            logger.error(f"API 调用失败: {e}")
            raise

    async def summarize_batch(self, articles: List[dict]) -> List[Optional[ArticleSummary]]:
        """并发批量生成文章总结

        Args:
            articles: 文章列表

        Returns:
            总结列表
        """
        max_concurrent = self.config.get('max_concurrent', 5)
        semaphore = asyncio.Semaphore(max_concurrent)

        async def process_with_limit(article):
            async with semaphore:
                return await self.summarize_article(article)

        results = await asyncio.gather(
            *[process_with_limit(a) for a in articles],
            return_exceptions=True
        )

        summaries = []
        for result in results:
            if isinstance(result, Exception):
                logger.error(f"AI 总结失败: {result}")
                summaries.append(None)
            else:
                summaries.append(result)
        return summaries

    def _rule_based_summary(self, article: dict) -> ArticleSummary:
        """规则提取降级方案"""
        content = article.get('content', '')
        title = article.get('title', '无标题')

        sentences = [s.strip() for s in content.split('。') if s.strip()]

        word_count = len(content)
        reading_time = max(1, word_count // 400)

        return ArticleSummary(
            chinese_title=title[:30] if len(title) > 30 else title,
            core_viewpoint=title,
            key_points=sentences[:3] if sentences else ["无要点"],
            conclusions=[],
            topics=[],
            reading_time=reading_time
        )

    async def generate_briefing(self, articles: List[dict]) -> Optional[DailyBriefing]:
        """基于所有文章摘要生成每日简报"""
        if not articles:
            return None

        try:
            articles_summary = self._build_articles_summary(articles)

            user_prompt = BRIEFING_USER_TEMPLATE.format(
                total_articles=len(articles),
                articles_summary=articles_summary
            )

            loop = asyncio.get_running_loop()
            briefing = await loop.run_in_executor(
                None, self._call_briefing_api, user_prompt
            )

            return briefing

        except Exception as e:
            logger.error(f"简报生成失败: {e}")
            return None

    def _build_articles_summary(self, articles: List[dict]) -> str:
        """将文章列表压缩为 AI 输入文本"""
        summaries = []
        for i, article in enumerate(articles[:50], 1):
            ai_summary = article.get('ai_summary')
            wikilink = article.get('_wikilink', '')
            filename_tag = f"\n   文件名: {wikilink}" if wikilink else ""

            if ai_summary and hasattr(ai_summary, 'chinese_title'):
                summaries.append(
                    f"{i}. {ai_summary.chinese_title}\n"
                    f"   核心观点: {ai_summary.core_viewpoint}\n"
                    f"   主题: {', '.join(ai_summary.topics)}\n"
                    f"   来源: {article.get('source_name', '未知')}"
                    f"{filename_tag}"
                )
            else:
                summaries.append(
                    f"{i}. {article.get('title', '无标题')}\n"
                    f"   来源: {article.get('source_name', '未知')}"
                    f"{filename_tag}"
                )

        return '\n\n'.join(summaries)

    def _call_briefing_api(self, user_prompt: str) -> DailyBriefing:
        """同步调用简报 API"""
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": BRIEFING_SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt}
            ],
            max_tokens=3000,
            response_format={"type": "json_object"}
        )

        content = response.choices[0].message.content

        if not content or not content.strip():
            raise ValueError("API 返回空内容")

        try:
            briefing_data = json.loads(content)
            return DailyBriefing(**briefing_data)
        except json.JSONDecodeError as e:
            logger.error(f"JSON 解析失败: {e}")
            logger.error(f"API 原始返回: {content[:500]}")
            raise
        except Exception as e:
            logger.error(f"简报数据解析失败: {e}")
            logger.error(f"原始返回: {content[:500]}")
            raise


# 测试代码
if __name__ == '__main__':
    config = {
        'api_key_env': 'OPENAI_API_KEY',
        'model': 'gpt-4o-mini',
    }

    test_article = {
        'title': '测试文章',
        'link': 'https://example.com/test',
        'content': '这是一篇关于人工智能的文章。AI 技术正在快速发展。它已经应用到很多领域。未来会有更多应用场景。'
    }

    async def test():
        try:
            summarizer = AISummarizer(config)
            summary = await summarizer.summarize_article(test_article)
            if summary:
                print("核心观点:", summary.core_viewpoint)
                print("关键要点:", summary.key_points)
                print("标签:", summary.topics)
            else:
                print("总结失败")
        except Exception as e:
            print(f"测试失败: {e}")
            print("提示：请确保设置了正确的 API key")

    asyncio.run(test())
