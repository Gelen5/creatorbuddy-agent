# Agent Runtime Contract

CreatorBuddy 的执行核心只有 `scripts/creatorbuddy.py`。Codex、WorkBuddy 或其他入口都只负责收集用户输入、调用命令和展示结果，不得在入口层重写评分、复盘或策略逻辑。

## 统一调用方式

```powershell
python scripts/creatorbuddy.py --workspace "<workspace>" <command>
```

其中 `<workspace>` 只保存账号配置、原始信号、标准化信号、发布记录、报告和策略；执行代码始终来自 GitHub 仓库。

## 入口职责

| 入口 | 必须做的事 | 不得做的事 |
| --- | --- | --- |
| Codex Skill | 识别意图、确认上下文、调用 CLI、解释证据边界 | 在对话里绕过 CLI 直接编造评分或策略 |
| WorkBuddy | 将用户表单/对话映射为 CLI 参数，展示 JSON 和报告路径 | 维护另一套评分、复盘或策略数据库 |
| 外部平台适配器 | 输出 raw signal JSON/JSONL，保留来源和观察时间 | 把公开样本伪装成自有账号后台数据 |
| Workspace | 保存输入与输出资产 | 承担核心业务判断逻辑 |

## 推荐调用顺序

```text
init
  -> set-account
  -> add-benchmark
  -> onboarding-status
  -> collect
  -> daily-run
  -> draft
  -> precheck
  -> review
  -> review-due
  -> self-growth
  -> approve-strategy
```

如果某一步缺少数据，入口应展示 CLI 返回的 `待补充` 或 `unknown`，不得自行补齐。

## 内容生成强制闸门

当入口要生成抖音口播稿、封面文案、标题、作品描述、今日选题或任何面向创作者发布的内容时，必须先完成以下取证和诊断。没有完成时，只能输出缺失项和下一步动作，不能输出最终稿。

```text
读取自有数据
  -> 读取产品/案例证据
  -> 读取历史风格规则
  -> 执行开头诊断
  -> 抽取对标结构
  -> 生成内容
  -> 输出流程执行回执
```

流程执行回执字段固定为：

| 字段 | 要求 |
| --- | --- |
| Owned evidence read | 最近自有内容、数据、评论、当天输入或已发布记录 |
| Product/case proof read | 具体产品、Skill、客户案例、工作流或已验证经历 |
| Style rules read | 用户确认过的口播风格、封面规则或平台规则 |
| Hook diagnosis | 话题、Hook、可信度、悬念、口播顺滑度 |
| Benchmark structure used | 真实结果、反常识判断、创作者状态、具体问题 |
| Missing data | 缺少的数据不得猜测 |
| Business-path connection | 如何连接 Skill、Agent、训练营、咨询、项目服务或长期目标 |

硬约束：

- 未读取自有数据，不得推荐选题。
- 未读取产品或案例证据，不得生成产品口播稿。
- 未执行开头诊断，不得输出前 3 秒。
- 未抽取对标结构，不得输出最终口播稿。
- 不得用抽象方法论替代具体案例；每条稿必须落到一个真实对象。
- 用户指出“没有按 Agent 流程”时，入口必须先审计漏掉哪一步，再重新执行闸门。
