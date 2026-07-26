# CreatorBuddy Agent

CreatorBuddy Agent is the Codex Skill package for inner testing.

## Install

Copy or clone this repository into your Codex skills folder:

```powershell
git clone https://github.com/Gelen5/creatorbuddy-agent.git "$env:USERPROFILE\.codex\skills\creatorbuddy-agent"
```

Then restart Codex.

## First Run

Ask Codex:

```text
使用 CreatorBuddy 初始化我的自媒体工作台
```

Or run manually:

```powershell
cd "$env:USERPROFILE\.codex\skills\creatorbuddy-agent"
python scripts\creatorbuddy.py init
python scripts\creatorbuddy.py today
```

首用时严格按以下顺序执行：连接账号、添加对标账号、检查 onboarding 状态、记录第一条已发布内容，再生成今日选题。详见 [`docs/agent-workbench-flow.md`](docs/agent-workbench-flow.md)。

Codex 和 WorkBuddy 都只调用 GitHub 仓库里的 CLI，运行时契约见 [`docs/agent-runtime-contract.md`](docs/agent-runtime-contract.md)。
WorkBuddy 的安装和调用方式见 [`docs/workbuddy-install.md`](docs/workbuddy-install.md)。

```powershell
python scripts\creatorbuddy.py set-account --platform xiaohongshu --account-id "your-account-id" --account-name "你的账号"
python scripts\creatorbuddy.py add-benchmark --platform xiaohongshu --account-id "benchmark-id" --account-name "对标账号"
python scripts\creatorbuddy.py onboarding-status
python scripts\creatorbuddy.py daily-run
```

Default workspace:

```text
%USERPROFILE%\CreatorBuddy
```

## Does The User Need A Knowledge Base?

Not required for the first inner-test version.

CreatorBuddy creates its own local workspace and stores data under:

```text
%USERPROFILE%\CreatorBuddy
```

The user should configure their own account profile in:

```text
%USERPROFILE%\CreatorBuddy\config\agent_config.json
```

They need to fill account names, positioning, target audience, keywords, products, and benchmark industries. Without an account, real recommendation commands are blocked; only an explicit `today --allow-cold-start` is allowed for testing generic seed topics.

## Optional Web UI

The CLI works without Node.js. The optional web UI requires Node.js.

```powershell
python scripts\creatorbuddy.py serve --port 5174
```

Open:

```text
http://localhost:5174
```

If Node is not in PATH, set:

```powershell
$env:NODE_EXE="C:\Path\To\node.exe"
python scripts\creatorbuddy.py serve --port 5174
```
