---
name: rss-digest
description: RSS 订阅简报生成器。处理 RSS 订阅、生成简报、检查更新、拉取指定博客、重新摘要文章。当用户要求处理 RSS、生成 RSS 简报、检查更新、获取订阅内容、生成简报、拉取指定博客、生成今日简报、重新生成简报、摘要文章、重新摘要、从 RSS 源获取内容、拉取博客时使用，即使未明确提及 rss-digest。
---

# RSS 订阅简报生成器

从配置的 RSS 源拉取最新内容，生成 Markdown 简报文档。

## 核心功能

- **RSS 拉取**：从多个 RSS 源自动获取最新文章
- **AI 摘要**：自动生成中文总结（可选，需 OpenAI 兼容 API）
- **主题去重**：AI 识别重复报道，避免同一事件多篇文章
- **每日简报**：自动生成今日要闻、值得深读、主题概览
- **指定源**：支持只拉取特定博客/源

## 快速命令

```bash
# 完整模式（昨天）
python .claude/skills/rss-digest/scripts/generate_digest.py

# 指定日期
python .claude/skills/rss-digest/scripts/generate_digest.py --date 2026-04-27

# 最近 N 天
python .claude/skills/rss-digest/scripts/generate_digest.py --days 3

# 仅生成简报（基于已有文章）
python .claude/skills/rss-digest/scripts/generate_digest.py --briefing-only

# 重新摘要指定文章
python .claude/skills/rss-digest/scripts/generate_digest.py --re-summary "文章标题"

# 查询配置
python .claude/skills/rss-digest/scripts/generate_digest.py --list-sources
python .claude/skills/rss-digest/scripts/generate_digest.py --show-config
python .claude/skills/rss-digest/scripts/generate_digest.py --usage
```

## 典型场景

**生成昨天的简报**
```bash
python .claude/skills/rss-digest/scripts/generate_digest.py --date 2026-04-26
```

**拉取指定博客**
```bash
# 先查看可用源
python .claude/skills/rss-digest/scripts/generate_digest.py --list-sources

# 拉取指定源（会展示匹配结果等待确认）
python .claude/skills/rss-digest/scripts/generate_digest.py --source "宝玉的分享"
```

**重新摘要文章**
```bash
python .claude/skills/rss-digest/scripts/generate_digest.py \
  --re-summary "文章标题" --prompt "提取实操步骤"
```

## 输出结构

```
project/rss/
├── 20260427/                   # 按日期归入子文件夹
│   ├── 文章标题-RSS.md
│   └── 简报-20260427.md
├── 01_RSS.base                 # 文章管理（Obsidian Base）
└── 00_RSS_SUMMARY.base         # 简报管理
```

## 文章字段

每篇文章包含：
- **Frontmatter**：created、updated、source、tags、status、type、description、reading_time、link、published、author
- **正文**：# 标题、## 关键要点、## 实操要点（如有）、## 主要结论（如有）
- **引用**：原文链接、来源、发布时间

## 配置

固定路径：`.claude/skills/rss-digest/rss-config.yaml`

```yaml
sources:
  - name: "源名称"
    url: "https://..."
    category: "分类"
    remark: "备注"

ai_summary:
  enabled: false
  api_key: ""
  model: "gpt-4o-mini"
  briefing:
    enabled: true
  topic_dedup:
    enabled: true
```

复制模板：
```bash
cp .claude/skills/rss-digest/config-template.yaml .claude/skills/rss-digest/rss-config.yaml
```

## 依赖

**基础模式**（RSS）：
```bash
pip install feedparser pyyaml
```

**AI 模式**：
```bash
pip install openai pydantic trafilatura
```

## 相关 Skill

- **x-bookmarks**：X/Twitter 书签拉取（独立 skill）

## 详细文档

- [详细工作流程](references/detailed-workflow.md)
- [错误处理](references/error-handling.md)
- [配置详解](references/configuration.md)
