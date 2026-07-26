# WorkBuddy 使用方式

CreatorBuddy 的核心不是某个聊天界面，而是 GitHub 仓库中的 `scripts/creatorbuddy.py`。WorkBuddy 只需要具备调用 PowerShell/Python 命令的能力，就可以作为入口使用；它不需要复制一套评分或复盘逻辑。

## 安装

```powershell
git clone https://github.com/Gelen5/creatorbuddy-agent.git "$env:USERPROFILE\creatorbuddy-agent"
```

## 运行

```powershell
$Repo = "$env:USERPROFILE\creatorbuddy-agent"
$Workspace = "$env:USERPROFILE\CreatorBuddy"
python "$Repo\scripts\creatorbuddy.py" --workspace $Workspace init
python "$Repo\scripts\creatorbuddy.py" --workspace $Workspace onboarding-status
```

## WorkBuddy 入口约束

- 所有账号、对标、选题、发布、复盘和策略操作都转成 CLI 命令。
- WorkBuddy 只展示 CLI 输出和报告路径，不在自身保存第二份策略库。
- `workspace` 可以指向 Obsidian vault；代码仍从 GitHub 仓库执行。
- 没有平台适配器时，WorkBuddy 必须显示“待补充”，不能把配置种子当作真实爆款数据。
- 每日任务调用 `daily-run`，不要分别重写 `today`、`review` 或策略逻辑。
