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
