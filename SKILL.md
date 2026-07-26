---
name: creatorbuddy-agent
description: CreatorBuddy 自媒体增长 Agent 内测包。Use when the user wants to initialize a CreatorBuddy workspace, generate daily self-media topic opportunities, create platform-specific draft briefs, run pre-publish checks, record published content for review, or start the optional local CreatorBuddy web workbench inside Codex. Triggers include CreatorBuddy, 自媒体Agent, 今日选题, 内容机会, 发布检查, 复盘, 小红书/抖音/公众号内容增长.
---

# CreatorBuddy Agent

CreatorBuddy is a local-first self-media growth agent for Codex users. It helps a creator move through:

```text
账号配置 -> 今日内容机会 -> 草稿简报 -> 发布检查 -> 发布记录 -> 复盘沉淀
```

Use the bundled CLI for deterministic work:

```powershell
python scripts/creatorbuddy.py <command>
```

## First Use

If the user has not initialized CreatorBuddy, run:

```powershell
python scripts/creatorbuddy.py init
python scripts/creatorbuddy.py doctor
```

Default workspace:

```text
%USERPROFILE%\CreatorBuddy
```

The user can override it with:

```powershell
$env:CREATORBUDDY_HOME="D:\CreatorBuddy"
```

or per command:

```powershell
python scripts/creatorbuddy.py --workspace "D:\CreatorBuddy" init
```

## Common Commands

Generate today's content opportunities:

```powershell
python scripts/creatorbuddy.py today
```

Generate opportunities from a specific topic:

```powershell
python scripts/creatorbuddy.py today --topic "WorkBuddy 新手教程"
```

Create a draft brief:

```powershell
python scripts/creatorbuddy.py draft --platform xiaohongshu --topic "WorkBuddy 新手第一次用，先跑通这 3 个任务"
```

Run a pre-publish check:

```powershell
python scripts/creatorbuddy.py precheck --title "标题" --content "正文或脚本"
```

Record published content for later review:

```powershell
python scripts/creatorbuddy.py review --platform xiaohongshu --title "已发布标题" --metrics-json "{\"likes\":10,\"collects\":3}"
```

Start the optional local web workbench:

```powershell
python scripts/creatorbuddy.py serve --port 5174
```

## User Configuration

After initialization, ask the user to edit:

```text
%USERPROFILE%\CreatorBuddy\config\agent_config.json
```

They should fill:

- workspace owner;
- platform account names;
- account positioning;
- target audience;
- benchmark industries;
- benchmark accounts;
- product keywords.

Do not hard-code Gelen, Gelen OS, or the original developer's accounts into a user's workspace.

## Evidence Rules

- Treat generated scores as prioritization, not proof that a topic will go viral.
- If platform account data is not connected, say it is using config seeds and local records only.
- Keep public samples, user-owned records, and AI inference separate.
- Preserve user data inside that user's CreatorBuddy workspace.

## Optional Web Workbench

The web workbench bundled in `assets/web` is a local MVP. It is useful for visual inspection, but Codex usage should not depend on it. If Node.js is unavailable, use the CLI commands instead.
