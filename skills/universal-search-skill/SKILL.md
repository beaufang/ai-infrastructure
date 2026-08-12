---
name: universal-search
description: 为 AI Agent 提供统一的互联网搜索能力。默认优先直连 Parallel Search API，失败或未配置时回退到 OpenRouter Web Search；支持中英文联合检索，适合搜索国外网站、技术文档、新闻、公开资料和需要时效性的事实。
---

# Universal Search Skill

## 目标

当任务需要互联网公开信息时，使用本 Skill，而不是依赖模型记忆猜测。

第一版只维护两个 Provider：

1. **Parallel Direct**：直接调用 Parallel 官方 Search API，默认优先。
2. **OpenRouter**：使用 OpenRouter 的 `openrouter:web_search` Server Tool，默认搜索引擎为 Parallel；当 Parallel Direct 不可用时作为回退，也可由用户显式指定。

不要把 MCP 当作搜索引擎；本 Skill 自己负责调用搜索 Provider。

## 什么时候使用

以下情况应考虑搜索：

- 用户明确要求“搜索、查一下、联网、最新、今天、最近、国外资料”等。
- 问题依赖近期变化：软件版本、API、价格、规则、产品、新闻、公司动态等。
- 需要核实模型不确定的事实。
- 需要查找国外网站、官方文档、GitHub、论文或公开资料。

如果问题是稳定常识、纯写作、纯翻译或不需要外部事实，不必搜索。

## 查询规划：强制中英文双语搜索

**每一次搜索都必须同时使用中文和英文检索词，不需要判断是否“有必要”。这是本 Skill 的固定规则。**

执行搜索前，Agent 必须生成至少两条 `search_queries`：

1. 至少 **1 条中文检索词**。
2. 至少 **1 条英文检索词**。

规则：

- 即使用户用中文提问，也必须生成对应英文查询。
- 即使用户用英文提问，也必须生成对应中文查询。
- 专有名词、产品名、库名、API 名保持原文，不机械翻译。
- 中文查询可以保留英文专有名词，但英文查询应是不含汉字的独立查询。
- 推荐每种语言各 1 条；复杂问题可各增加 1 条，但避免大量同义改写。
- 搜索结果统一按 URL 去重后再综合使用。

示例：用户问“帮我查一下 LangGraph 最近的 durable execution 有什么变化”。

必须至少使用：

- 中文：`LangGraph durable execution 最新变化 持久化`
- 英文：`LangGraph durable execution latest changes`

### 强制校验

CLI 会校验 `--search-query`：

- 缺中文查询：报错。
- 缺英文查询：报错。
- 只有一条中英混合查询：仍然报错，因为必须有独立的中文和英文检索词。

因此 Agent 不应省略 `--search-query`。

### 搜索模式

CLI 默认 `--mode auto`。由于本 Skill 强制每次包含中文查询，`auto` 会稳定解析为 `basic`，以获得多语言支持。

- 默认双语搜索：`basic`。
- 复杂、多跳、对结果质量要求更高时：显式使用 `--mode advanced`。
- `turbo` 仍保留给用户手动覆盖，但它不适合作为本 Skill 默认双语模式。

## Provider 路由

默认使用：

```text
provider = auto
```

`auto` 的行为：

1. 如果存在 `PARALLEL_API_KEY`，先调用 Parallel Direct。
2. Parallel Direct 出现网络错误、API 错误、响应无法解析或结果为空时：
   - 如果存在 `OPENROUTER_API_KEY`，回退 OpenRouter。
3. 如果没有 `PARALLEL_API_KEY`，但存在 `OPENROUTER_API_KEY`，直接使用 OpenRouter。
4. 两个 Key 都没有时，明确报错，不要伪造搜索结果。

第一版**不做主观“搜索质量评分”**。结果不理想时，Agent 应先改写查询词再次搜索；必要时可以显式切换 Provider 或 OpenRouter engine。

## 命令

从 Skill 根目录执行：

```bash
python3 scripts/search.py "<搜索目标>" \
  --search-query "<英文检索词>" \
  --search-query "<中文检索词>"
```

常用参数：

```text
--provider auto|parallel|openrouter
--mode auto|turbo|basic|advanced
--search-query <可重复>
--max-results <数量>
--format json|markdown
--engine <OpenRouter 搜索引擎，默认 parallel>
--config <config.toml 路径>
--no-fallback
```

### 示例 1：默认自动路由，中英文联合搜索

```bash
python3 scripts/search.py "研究 OpenAI Responses API 最近的工具调用变化" \
  --search-query "OpenAI Responses API tools updates" \
  --search-query "OpenAI Responses API 工具调用"
```

### 示例 2：只直连 Parallel

```bash
python3 scripts/search.py "查找 uv Python package manager 最新文档" \
  --provider parallel \
  --search-query "uv Python package manager 最新文档" \
  --search-query "uv Python package manager latest docs"
```

### 示例 3：强制 OpenRouter，并让 OpenRouter 使用 Parallel

```bash
python3 scripts/search.py "查找 MCP authorization 最新规范" \
  --provider openrouter \
  --engine parallel \
  --search-query "MCP authorization 最新规范" \
  --search-query "MCP authorization latest specification"
```

### 示例 4：复杂搜索

```bash
python3 scripts/search.py "比较最近三个月两个项目的关键架构变化" \
  --mode advanced \
  --search-query "项目 A 项目 B 最近三个月 架构变化" \
  --search-query "project A project B architecture changes last three months"
```

## 输出与引用

默认输出 JSON。每个结果统一为：

```json
{
  "title": "...",
  "url": "https://...",
  "content": "与查询相关的摘录",
  "published_date": "...",
  "source": "parallel"
}
```

回答用户时：

- 优先依据搜索结果中的原始来源 URL。
- 对时效性强或关键事实，尽量用两个独立来源交叉验证。
- 不要把搜索摘要当作绝对真相；如有冲突，说明冲突。
- 如果没有可靠结果，明确说没有找到，不要补写不存在的事实。

## 环境变量

```bash
export PARALLEL_API_KEY="..."
export OPENROUTER_API_KEY="..."
```

可选：

```bash
export UNIVERSAL_SEARCH_CONFIG="/path/to/config.toml"
export OPENROUTER_MODEL="~openai/gpt-latest"
```

配置文件不是必需的；环境变量即可运行。
