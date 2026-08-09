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
python scripts\creatorbuddy.py quickstart
python scripts\creatorbuddy.py today
```

`quickstart` 会一步步询问：你是谁、做哪个平台、账号定位、核心产品、对标账号、发过什么内容，并自动写入本地 workspace。

首用时严格按以下顺序执行：连接账号、补账号画像、添加对标账号、记录第一条内容资产，再生成今日选题。详见 [`docs/agent-workbench-flow.md`](docs/agent-workbench-flow.md) 和 [`docs/content-asset-schema.md`](docs/content-asset-schema.md)。

Codex 和 WorkBuddy 都只调用 GitHub 仓库里的 CLI，运行时契约见 [`docs/agent-runtime-contract.md`](docs/agent-runtime-contract.md)。
WorkBuddy 的安装和调用方式见 [`docs/workbuddy-install.md`](docs/workbuddy-install.md)。

Marketing judgment is built into `today` and `draft`: each recommendation now carries offer, content strategy, social distribution, conversion, and attribution fields. See [`docs/marketing-framework.md`](docs/marketing-framework.md).

Xiaohongshu-specific drafts also include a sanitized playbook for profile clarity, topic function, title mode, comment plan, conversion path, and review metrics. See [`docs/xiaohongshu-playbook.md`](docs/xiaohongshu-playbook.md).

Benchmark distillation is available for Xiaohongshu public profile cards: import a benchmark profile, segment visible samples, then generate a `creator_clone.md`. See [`docs/benchmark-distillation.md`](docs/benchmark-distillation.md).

```powershell
python scripts\creatorbuddy.py quickstart
python scripts\creatorbuddy.py set-account --platform xiaohongshu --account-id "your-account-id" --account-name "你的账号"
python scripts\creatorbuddy.py set-profile --platform xiaohongshu --positioning "你的账号定位" --target-audience "目标用户" --content-directions "方向1,方向2" --commercial-goal "商业目标" --core-product "核心产品"
python scripts\creatorbuddy.py add-benchmark --platform xiaohongshu --account-id "benchmark-id" --account-name "对标账号"
python scripts\creatorbuddy.py add-content --platform xiaohongshu --title "第一条内容" --body "正文或脚本" --metrics-json "{\"likes\":0}"
python scripts\creatorbuddy.py import-benchmark --platform xiaohongshu --url "https://www.xiaohongshu.com/user/profile/..."
python scripts\creatorbuddy.py segment-benchmark --benchmark-id "benchmark-id"
python scripts\creatorbuddy.py distill-creator --benchmark-id "benchmark-id"
python scripts\creatorbuddy.py onboarding-status
python scripts\creatorbuddy.py workflow-audit
python scripts\creatorbuddy.py daily-run
```

`workflow-audit` is the inner-test acceptance check for the commercial MVP loop. It verifies evidence for:

1. first-use flow;
2. account configuration center;
3. content asset database;
4. today's content opportunity report;
5. Xiaohongshu draft and precheck loop;
6. benchmark distillation;
7. pre-publish check;
8. post-publish review;
9. strategy approval and self-growth readback.

It returns `ok: true` only when the current workspace has durable files proving all nine items.

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

The CLI works without Node.js. The optional web UI requires Node.js. The first web MVP is intentionally a control console with five pages: 首页、账号中心、内容机会、内容库、复盘中心。

```powershell
python scripts\creatorbuddy.py serve --port 5174
```

Open:

```text
http://localhost:5174
```

首次使用网页端时，进入 `账号中心`，填写初始化表单并点击 `完成初始化`。网页会调用同一个 CLI `quickstart`，自动写入账号配置、对标账号和第一条内容资产。

If Node is not in PATH, set:

```powershell
$env:NODE_EXE="C:\Path\To\node.exe"
python scripts\creatorbuddy.py serve --port 5174
```
