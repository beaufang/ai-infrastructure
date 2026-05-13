#!/usr/bin/env python3
"""
主题聚类去重模块
使用 AI 识别重复/相似文章并标记
"""

import asyncio
import json
import logging
import sys
from typing import List, Dict

logger = logging.getLogger(__name__)


async def deduplicate_articles_by_topic(articles: List[dict], summarizer, ai_config: dict) -> List[dict]:
    """使用 AI 进行主题聚类去重

    Args:
        articles: 文章列表（需已包含 ai_summary）
        summarizer: AISummarizer 实例
        ai_config: AI 配置字典

    Returns:
        原文章列表，重复文章会添加 duplicate_of 字段
    """
    dedup_config = ai_config.get('topic_dedup', {})
    if not dedup_config.get('enabled', False):
        return articles

    if not articles:
        return articles

    print(f"\n正在进行主题聚类去重...", file=sys.stderr)

    # 只对有 AI 摘要的文章做去重
    articles_with_summary = [a for a in articles if a.get('ai_summary')]
    if len(articles_with_summary) < 2:
        return articles

    # 构建去重输入
    dedup_input = _build_dedup_input(articles_with_summary)

    # 调用 AI 进行聚类
    try:
        from prompts import TOPIC_DEDUP_SYSTEM_PROMPT, TOPIC_DEDUP_USER_TEMPLATE
        from openai import OpenAI

        client = summarizer.client
        model = summarizer.model

        user_prompt = TOPIC_DEDUP_USER_TEMPLATE.format(
            article_count=len(articles_with_summary),
            articles_info=dedup_input
        )

        loop = asyncio.get_running_loop()
        result = await loop.run_in_executor(
            None, _call_dedup_api, client, model, user_prompt
        )

        if result and 'groups' in result:
            # 应用去重结果
            duplicate_count = _apply_dedup_results(articles_with_summary, result['groups'])
            if duplicate_count > 0:
                print(f"  检测到 {len(result['groups'])} 个重复组，标记 {duplicate_count} 篇文章为重复", file=sys.stderr)
            else:
                print(f"  未发现重复文章", file=sys.stderr)
        else:
            print(f"  去重失败：AI 返回结果格式异常", file=sys.stderr)

    except Exception as e:
        logger.warning(f"主题聚类去重失败: {e}")
        print(f"  去重失败: {e}", file=sys.stderr)

    return articles


def _build_dedup_input(articles: List[dict]) -> str:
    """构建去重输入文本"""
    lines = []
    for i, article in enumerate(articles):
        ai_summary = article.get('ai_summary')
        if not ai_summary:
            continue

        lines.append(f"{i + 1}. 【{ai_summary.chinese_title or article.get('title', '无标题')}】")
        lines.append(f"   核心观点: {ai_summary.core_viewpoint}")
        if ai_summary.topics:
            lines.append(f"   主题: {', '.join(ai_summary.topics)}")
        lines.append("")

    return '\n'.join(lines)


def _call_dedup_api(client, model: str, user_prompt: str) -> dict:
    """调用去重 API"""
    from prompts import TOPIC_DEDUP_SYSTEM_PROMPT

    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": TOPIC_DEDUP_SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt}
        ],
        max_tokens=3000,
        response_format={"type": "json_object"}
    )

    content = response.choices[0].message.content
    return json.loads(content)


def _apply_dedup_results(articles: List[dict], groups: List[dict]) -> int:
    """应用去重结果，标记重复文章"""
    duplicate_count = 0

    for group in groups:
        main_index = group.get('main_index', 0)
        duplicate_indices = group.get('duplicate_indices', [])
        reason = group.get('reason', '')

        if not (0 <= main_index < len(articles)):
            continue

        main_article = articles[main_index]
        main_wikilink = main_article.get('_wikilink', '')

        if not main_wikilink:
            continue

        for dup_index in duplicate_indices:
            if not (0 <= dup_index < len(articles)):
                continue

            dup_article = articles[dup_index]
            dup_article['duplicate_of'] = main_wikilink
            duplicate_count += 1

    return duplicate_count
