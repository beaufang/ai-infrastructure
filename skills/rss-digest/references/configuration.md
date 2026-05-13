# 配置文件详解

配置文件固定路径：`.claude/skills/rss-digest/rss-config.yaml`

## RSS 源配置

```yaml
sources:
  - name: "阮一峰的网络日志"      # 源名称（用于 --source 精确匹配）
    url: "https://..."            # RSS feed URL
    category: "技术"              # 分类（可选）
    remark: "前端技术"            # 备注（可选，用于语义匹配）
```

## 输出配置

```yaml
output:
  directory: "project/rss"       # 输出目录（相对路径）
  base:
    name: "01_RSS"               # 文章 Base 文件名
    briefing_name: "00_RSS_SUMMARY"  # 简报 Base 文件名
```

## 内容配置

```yaml
content:
  max_articles_per_source: 50   # 每个源最多获取的文章数
```

## 去重配置

```yaml
dedup:
  enabled: true                  # 是否启用去重（基于 URL）
```

## AI 总结配置

```yaml
ai_summary:
  enabled: false                 # 是否启用 AI 总结

  # API 配置（OpenAI 兼容）
  api_key: ""                    # API 密钥
  model: "gpt-4o-mini"           # 模型名称
  base_url: ""                   # 自定义 API 地址（可选，用于 DeepSeek 等）

  # 内容获取策略
  content_strategy: "auto"       # 'rss_only' | 'fetch_full' | 'auto'
  fetch_full_min_length: 500     # RSS 内容 <500 字时自动抓取全文

  # 性能优化
  max_concurrent: 5              # 最大并发请求数

  # 每日简报配置
  briefing:
    enabled: true                # 是否生成简报

  # 主题聚类去重配置
  topic_dedup:
    enabled: true                # 是否启用 AI 驱动的主题聚类去重
```

## content_strategy 说明

| 值 | 行为 |
|----|----|
| `rss_only` | 仅使用 RSS 内容，不抓取完整网页 |
| `fetch_full` | 对所有文章抓取完整网页 |
| `auto` | 智能混合：RSS 内容 <500 字时自动抓取全文 |

## X 书签配置

X/Twitter 书签已拆分为独立 skill `x-bookmarks`，配置仍保留在此文件的 `twitter` 部分：

```yaml
twitter:
  enabled: true                 # 是否启用（需安装 opencli）
  bookmark_limit: 50            # 拉取书签数量
  fetch_articles: true          # 是否获取长文推文内容
```

## 复制配置模板

```bash
cp .claude/skills/rss-digest/config-template.yaml .claude/skills/rss-digest/rss-config.yaml
# 然后编辑 rss-config.yaml 填入你的配置
```
