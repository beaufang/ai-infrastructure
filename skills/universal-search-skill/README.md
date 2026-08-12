# Universal Search Skill v0.1.1

一个轻量、面向 AI Agent 的统一 Web Search Skill。

当前 v0.1 聚焦两条路径：

- **Parallel Direct**：优先直连 Parallel 官方 Search API。
- **OpenRouter**：作为 fallback 或显式 Provider，使用 OpenRouter Web Search Server Tool；默认 `engine=parallel`。

设计目标不是做“搜索平台”，而是先做一个自己每天能稳定使用、以后容易开源扩展的小 Skill。

## 特点

- 中文 `SKILL.md`，适合中文 Agent 工作流。
- **强制双语搜索**：每次必须分别生成至少一条中文检索词和一条英文检索词。
- 默认 `provider=auto`：Parallel Direct → OpenRouter fallback。
- 默认 `mode=auto`：由于每次都包含中文查询，稳定使用 Parallel Basic；复杂任务可手动切 Advanced。
- OpenRouter 使用新的 `openrouter:web_search` Server Tool，不依赖已 deprecated 的 Web Search Plugin。
- Python 标准库实现，**零第三方依赖**。
- JSON / Markdown 两种输出格式。
- Provider 返回结果统一成同一个 schema。

## 要求

- Python 3.11+
- 至少配置一个 API Key：

```bash
export PARALLEL_API_KEY="..."
# 或
export OPENROUTER_API_KEY="..."
```

## 快速开始

```bash
cd universal-search-skill

python3 scripts/search.py "研究 LangGraph 最近的 durable execution 变化" \
  --search-query "LangGraph durable execution updates" \
  --search-query "LangGraph durable execution 持久化"
```

如果同时配置了两个 Key，默认先直连 Parallel；只有 API/网络失败或结果为空时才 fallback 到 OpenRouter。

## 为什么由 Agent 生成中英文查询，而不是脚本自动翻译？

双语是**固定规则**，不是 Agent 的可选判断。Agent 只负责根据上下文生成两种语言的高质量查询词；脚本负责强制校验。

每次调用至少需要：

- 1 条中文查询。
- 1 条不含汉字的英文查询。

如果缺少任意一种，CLI 会直接报错。只有一条中英混合查询也不算满足要求。

之所以不在脚本内再调用 LLM 翻译，是为了避免额外模型费用、额外延迟和新的 API 依赖。Coding Agent 本身已经具备查询改写能力。

示例：

```bash
python3 scripts/search.py "研究 LangGraph durable execution 的最新变化" \
  --search-query "LangGraph durable execution 最新变化 持久化" \
  --search-query "LangGraph durable execution latest changes"
```

## 模式选择

`--mode auto` 是本项目自己的轻量策略，不是 Provider 的 API 枚举值。由于双语查询是强制规则，每次都会包含汉字，因此默认解析为 `basic`。

也可以手动指定：

```bash
--mode turbo
--mode basic
--mode advanced
```

复杂研究任务建议 `advanced`；普通双语搜索使用 `basic`。`turbo` 仅作为显式覆盖保留，不是默认双语策略。

## Provider

### Parallel Direct

请求：

```text
POST https://api.parallel.ai/v1/search
x-api-key: $PARALLEL_API_KEY
```

程序会传入：

- `objective`
- `search_queries`
- `mode`
- `max_chars_total`

Parallel 的结果会被归一化为 `title / url / content / published_date / source`。

### OpenRouter

请求：

```text
POST https://openrouter.ai/api/v1/chat/completions
Authorization: Bearer $OPENROUTER_API_KEY
```

使用 Server Tool：

```json
{
  "type": "openrouter:web_search",
  "parameters": {
    "engine": "parallel",
    "mode": "basic",
    "max_uses": 1
  }
}
```

OpenRouter fallback 会限制为最多一次 Web Search，避免在单次 Skill 调用里出现不可控的多次搜索成本。搜索结果从 `url_citation` annotations 归一化输出。

OpenRouter 仍然需要一个模型来执行 Server Tool；默认模型为官方 latest alias：

```text
~openai/gpt-latest
```

可以通过配置文件或环境变量覆盖：

```bash
export OPENROUTER_MODEL="你希望使用的模型 slug"
```

因此 OpenRouter 路径的总费用 = Web Search 费用 + 对应模型的 token 费用。

## 配置

复制示例配置：

```bash
cp config.example.toml config.toml
```

配置优先级：

```text
CLI 参数 > 环境变量 > config.toml > 内置默认值
```

也可以完全不创建 `config.toml`。

## CLI

```bash
python3 scripts/search.py --help
```

主要参数：

```text
objective                    搜索目标
--search-query QUERY         可重复；强制至少一条中文 + 一条英文
--provider                   auto / parallel / openrouter
--mode                       auto / turbo / basic / advanced
--max-results                最终保留的最大结果数
--max-chars-total            Parallel Direct 的总摘录字符预算
--engine                     OpenRouter Web Search engine
--openrouter-model           OpenRouter 模型
--format                     json / markdown
--no-fallback                auto 模式下禁止 fallback
--config                     TOML 配置路径
```

## 输出示例

```json
{
  "objective": "研究 LangGraph durable execution 的最新变化",
  "search_queries": [
    "LangGraph durable execution updates",
    "LangGraph durable execution 持久化"
  ],
  "provider": "parallel",
  "engine": "parallel",
  "mode": "basic",
  "fallback_used": false,
  "results": [
    {
      "title": "...",
      "url": "https://...",
      "content": "...",
      "published_date": null,
      "source": "parallel"
    }
  ]
}
```

## 测试

```bash
python3 -m unittest discover -s tests -v
```

测试不访问真实 API。

## v0.1 明确不做

- 自动 LLM 质量评分
- Deep Research loop
- 网页 Extract / Crawl
- MCP Server
- Exa / Brave / Tavily 直连 Provider
- 缓存和数据库

OpenRouter 的 `engine` 参数保留为配置项，因此未来即使要通过 OpenRouter 切换 Exa / Perplexity，也不需要重写路由层。

## 后续方向

如果第一版使用稳定，再考虑：

1. 查询质量检测与重写。
2. Search + Extract。
3. Exa / Brave 等直连 Provider。
4. 缓存、去重、结果评分。
5. MCP Adapter。
