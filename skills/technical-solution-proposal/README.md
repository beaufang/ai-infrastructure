# technical-solution-proposal

用于编写、重构和评审整体技术方案的中文 Skill。

## 目录

```text
technical-solution-proposal/
├── SKILL.md
├── README.md
├── references/
│   ├── user-interview.md
│   ├── codebase-exploration.md
│   ├── external-research.md
│   ├── proposal-structure.md
│   ├── review-rubric.md
│   └── output-modes.md
└── examples/
    ├── problem-framing-example.md
    ├── research-report-example.md
    └── proposal-example.md
```

## 使用原则

`SKILL.md` 负责总控，只规定流程、阶段产物和硬性质量门槛。

`references/` 中的文档按需读取：

| 文件 | 使用时机 |
|---|---|
| `user-interview.md` | 需要澄清目标、问题、约束和决策时 |
| `codebase-exploration.md` | 方案涉及存量系统改造时 |
| `external-research.md` | 需要搜索 GitHub、官方文档、论文和行业实践时 |
| `proposal-structure.md` | 开始组织整体技术方案正文时 |
| `review-rubric.md` | 初稿完成后进行反向评审时 |
| `output-modes.md` | 需要在技术评审、管理汇报和对外发布之间转换时 |

`examples/` 用于校准输出，不应被当作固定模板照抄。

## 推荐调用方式

### 重构已有方案

```text
使用 technical-solution-proposal 的重构模式。

受众：技术负责人和相关研发团队。
目标：确认总体路线和首期边界。
现有方案：@docs/agent-evaluation.md
代码库：当前仓库。

先诊断文档和制定调查计划，不要直接重写。
```

### 新建整体方案

```text
使用 technical-solution-proposal 的新建模式，
为统一 Agent 评估平台形成技术评审方案。

先与我确认问题和关键约束；
随后探索现有代码库和外部方案；
完成调查回传后，再提出候选路线。
```

### 对外发布

```text
将已确认的技术评审方案转换为 external 模式。
删除内部系统名、组织信息和敏感实现，
保留问题、核心洞察、整体机制、实践结果与局限。
```

## 使用建议

1. 不要让模型在一次调用中机械完成全部阶段。
2. 先完成问题与证据调查，再形成候选方案。
3. 重大新发现应回传用户，不要静默修改方向。
4. 主方案保持整体逻辑，详细设计拆为独立文档。
5. 示例中的 Agent 评估主题仅用于演示方法。
