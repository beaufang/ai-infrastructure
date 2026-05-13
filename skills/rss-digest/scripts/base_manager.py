#!/usr/bin/env python3
"""
Obsidian Base 管理模块
负责创建和更新 Obsidian Base 文件
"""

import sys
from pathlib import Path

_BASE_CONTENT = """filters:
  and:
    - file.inFolder("{folder}")
    - file.ext == "md"
    - type != "briefing"
properties:
  feed:
    displayName: 来源
  category:
    displayName: 分类
  published:
    displayName: 发布日期
  tags:
    displayName: 标签
  status:
    displayName: 状态
  reading_time:
    displayName: 阅读时间（分钟）
views:
  - type: table
    name: 未读文章
    groupBy:
      property: status
      direction: DESC
    order:
      - file.name
      - feed
      - category
      - published
      - status
    sort:
      - property: published
        direction: DESC
  - type: table
    name: 按分类分组
    groupBy:
      property: category
      direction: ASC
    order:
      - file.name
      - feed
      - category
      - published
      - tags
      - status
    sort:
      - property: published
        direction: DESC
  - type: table
    name: 按源分组
    groupBy:
      property: feed
      direction: ASC
    order:
      - file.name
      - feed
      - category
      - published
      - tags
      - status
    sort:
      - property: published
        direction: DESC
  - type: table
    name: 全部文章
    order:
      - file.name
      - feed
      - category
      - published
      - tags
      - status
    sort:
      - property: published
        direction: DESC
"""

_BRIEFING_BASE_CONTENT = """filters:
  and:
    - file.inFolder("{folder}")
    - file.ext == "md"
    - type == "briefing"
properties:
  published:
    displayName: 发布日期
  total_articles:
    displayName: 文章数
  highlights_count:
    displayName: 要闻数
views:
  - type: table
    name: 每日简报
    order:
      - file.name
      - published
      - total_articles
      - highlights_count
    sort:
      - property: published
        direction: DESC
"""


def ensure_base_file(base_dir: Path, base_name: str, briefing_base_name: str):
    """创建或更新 Obsidian Base 文件（文章 + 简报两个 base）"""
    folder = str(base_dir).replace('\\', '/')

    for template, name in [
        (_BASE_CONTENT, base_name),
        (_BRIEFING_BASE_CONTENT, briefing_base_name),
    ]:
        base_path = base_dir / f"{name}.base"
        content = template.format(folder=folder)

        if base_path.exists():
            with open(base_path, 'r', encoding='utf-8') as f:
                existing = f.read()
            if existing.strip() == content.strip():
                continue
            with open(base_path, 'w', encoding='utf-8') as f:
                f.write(content)
            print(f"  已更新 Obsidian Base: {base_path}", file=sys.stderr)
        else:
            with open(base_path, 'w', encoding='utf-8') as f:
                f.write(content)
            print(f"  已创建 Obsidian Base: {base_path}", file=sys.stderr)
