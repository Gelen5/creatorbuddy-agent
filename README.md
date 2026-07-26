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

But the user should configure their own account profile in:

```text
%USERPROFILE%\CreatorBuddy\config\agent_config.json
```

They need to fill account names, positioning, target audience, keywords, products, and benchmark industries. Without configuration, CreatorBuddy can still run with generic seed topics, but the output will be less personalized.

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
