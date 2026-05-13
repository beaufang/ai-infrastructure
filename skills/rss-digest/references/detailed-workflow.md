# RSS Digest 详细工作流程

## 运行模式

### 完整模式（默认）

拉取 RSS → AI 摘要 → 生成简报

```bash
python .claude/skills/rss-digest/scripts/generate_digest.py --date 2026-04-27
```

### 指定源拉取

仅拉取用户指定的 RSS 源，支持多个 `--source`

```bash
python .claude/skills/rss-digest/scripts/generate_digest.py --source "宝玉的分享" --date 2026-04-27

python .claude/skills/rss-digest/scripts/generate_digest.py \
  --source "宝玉的分享" --source "Hacker News" --days 1
```

当用户说"拉取 XXX 的博客"时：
1. 运行 `--list-sources` 获取所有源
2. 根据用户描述匹配源的 name、category 或 remark 字段
3. **展示匹配结果后停下来等待用户确认**（不能跳过）
4. 用户确认后执行

### 仅生成简报模式

基于已有文章生成简报，不拉取 RSS

```bash
# 默认今天的文件夹
python .claude/skills/rss-digest/scripts/generate_digest.py --briefing-only

# 指定日期
python .claude/skills/rss-digest/scripts/generate_digest.py --briefing-only --date 2026-04-27

# 指定文件夹
python .claude/skills/rss-digest/scripts/generate_digest.py --briefing-only --folder project/rss/20260427
```

### 重新摘要模式

对指定文章重新生成 AI 摘要，支持自定义提示词

```bash
# 重新摘要（用文件名关键词查找）
python .claude/skills/rss-digest/scripts/generate_digest.py --re-summary "宝藏网站收录400+精选GPT Image 2提示词-X"

# 重新摘要 + 自定义提示词
python .claude/skills/rss-digest/scripts/generate_digest.py \
  --re-summary "宝藏网站收录400+精选GPT Image 2提示词-X" \
  --prompt "提取提示词"
```

## 日期参数

参数互斥，优先级从上到下：

| 参数 | 说明 | 示例 |
|------|------|------|
| `--start-date` + `--end-date` | 指定日期范围 | `--start-date 2026-04-01 --end-date 2026-04-07` |
| `--date` | 单个日期（当天 00:00-23:59） | `--date 2026-04-27` |
| `--days` | 最近 N 天 | `--days 7` |
| 不传 | 默认昨天到今天 | - |

## 输出结构

```
project/rss/
├── {YYYYMMDD}/                 # 按抓取起始日期归入子文件夹
│   ├── 文章标题-RSS.md        # RSS 文章
│   └── 简报-{YYYYMMDD}.md     # 每日简报（如启用）
├── 01_RSS.base                # 文章管理 Base
└── 00_RSS_SUMMARY.base        # 简报管理 Base
```

## 查询配置

```bash
# 查看可用 RSS 源（含 name、category、remark）
python .claude/skills/rss-digest/scripts/generate_digest.py --list-sources

# 查看完整配置（API 密钥已脱敏）
python .claude/skills/rss-digest/scripts/generate_digest.py --show-config

# 查看详细使用指南
python .claude/skills/rss-digest/scripts/generate_digest.py --usage
```

## 配置文件

固定路径：`.claude/skills/rss-digest/rss-config.yaml`

**重要**：不要直接读取此文件（包含 API 密钥等敏感信息），使用脚本查询：
- `--list-sources`：查看可用 RSS 源
- `--show-config`：查看完整脱敏配置
- `--usage`：查看详细使用指南

配置模板：`config-template.yaml`

## 相关 Skill

X/Twitter 书签拉取已拆分为独立 skill `x-bookmarks`，使用：
```bash
python .claude/skills/x-bookmarks/scripts/fetch_bookmarks.py --date 2026-05-01
```
