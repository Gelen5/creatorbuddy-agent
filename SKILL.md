---
name: creatorbuddy-agent
description: CreatorBuddy 自媒体增长 Agent 内测包。Use when the user wants to initialize a CreatorBuddy workspace, generate daily self-media topic opportunities, create platform-specific draft briefs, run pre-publish checks, record published content for review, or start the optional local CreatorBuddy web workbench inside Codex. Triggers include CreatorBuddy, 自媒体Agent, 今日选题, 内容机会, 发布检查, 复盘, 小红书/抖音/公众号内容增长.
---

# CreatorBuddy Agent

CreatorBuddy is a local-first self-media growth agent for Codex users. It helps a creator move through:

```text
连接账号 -> 配置行业/对标 -> 读取自有数据 -> 采集公开信号 -> 选题评分 -> 平台化草稿 -> 发布检查 -> 发布记录 -> 复盘 -> 策略确认 -> 下次生成前回读
```

## Strict Agent Workflow

Every account, benchmark, topic, draft, publishing, review, or self-growth task must follow this order:

1. Confirm workspace, account, platform, goal, and deliverable.
2. Read owned account/content/review/conversion evidence first.
3. Collect current public industry and benchmark signals only when trend judgment is needed.
4. Label evidence as owned, public sample, inference, historical, or unknown.
5. Score with sources, reasons, evidence strength, platform fit, and production cost.
6. Route platform-specific work to the matching platform logic.
7. Run pre-publish checks before marking content ready.
8. Record published time, platform, metrics, comments, conversions, and review state.
9. Review at `2h`, `24h`, `48h`, and `7d`, recording facts before explanations.
10. Write strategy candidates after review; require user confirmation before activation.
11. Read confirmed active strategies before the next recommendation or draft.

Never present public samples as owned backend metrics, guarantee virality, invent missing metrics or conversions, or promote an unconfirmed review into a permanent rule.

## Marketing Judgment Layer

CreatorBuddy absorbs the useful marketing decision frames from `coreyhaines31/marketingskills` as local runtime fields, not as a second execution engine. `today` and `draft` must surface:

- offer: audience, promise, proof needed, next step;
- content strategy: pillar, single idea, repeatable format;
- social distribution: platform-native hook and engagement goal;
- conversion: CTA, product bridge, objection to address;
- attribution: content id, source tag, review checkpoints, conversion fields.

Use these fields to improve prioritization and briefs. Do not claim leads, sales, revenue, or attribution unless those facts are present in the workspace records.

## Xiaohongshu Playbook Layer

CreatorBuddy includes a sanitized Xiaohongshu playbook for drafts and pre-publish checks. It absorbs reusable operating patterns from a MIT-licensed public Xiaohongshu workbench, but it does not expose that project's brand, author, manual, or external skill names in user-facing output.

For Xiaohongshu drafts, `draft` must add `xiaohongshu_brief` with:

- profile gate: 3-second clarity, pinned note fit, product bridge;
- topic planner: attract, resonate, trust, educate, convert, or interact;
- title design: cover short line, comment style, insight judgment, or search conversion;
- comment plan: pinned comment and objection reply rules;
- conversion path: attract, screen, trust, act, private message, revisit;
- measurement: content_id, publish time, 24h/48h/7d metrics, conversion signal.

For Xiaohongshu prechecks, reject generic title words such as `天花板`, `宝藏`, `被问爆了`, `高级感`, and other empty platform cliches when they appear in the title.

## Benchmark Distillation Layer

CreatorBuddy can now import and distill Xiaohongshu benchmark accounts:

```powershell
python scripts/creatorbuddy.py import-benchmark --platform xiaohongshu --url "https://www.xiaohongshu.com/user/profile/..."
python scripts/creatorbuddy.py segment-benchmark --benchmark-id "<benchmark_id>"
python scripts/creatorbuddy.py distill-creator --benchmark-id "<benchmark_id>"
```

This first phase supports:

- public Xiaohongshu profile-card extraction;
- sample understanding labels: `metadata-only`, `partial`, `full`;
- performance segmentation from visible metrics, mainly likes until detail data is imported;
- `creator_clone.md` generation with positioning, topic buckets, transferable templates, anti-patterns, and self-check rubric.

Evidence boundary:

- profile cards are benchmark candidates, not full content understanding;
- body text, comments, full carousel media, OCR, ASR, saves, shares, and conversion require detail links, logged-in capture, or manual imports;
- never copy exact wording, identity, images, screenshots, claims, or creator stories.

## Mandatory Draft Gate

For Douyin/TikTok scripts, covers, titles, captions, topic plans, or any creator-facing content draft, the agent must pass this gate before writing final copy:

1. Read owned evidence first: recent owned content, metrics, comments, daily inputs, existing content assets, and product/case proof.
2. Read the user's current style rules and previous confirmed drafts.
3. Run a hook diagnosis before writing the first 3 seconds: topic, hook, credibility, suspense, and spoken-flow fit.
4. Extract the benchmark structure before writing: real result, counterintuitive judgment, creator state, and concrete problem.
5. Only then write the draft, and connect it to the user's business path.

The final response or generated markdown must include a short workflow receipt:

```text
Owned evidence read:
Product/case proof read:
Style rules read:
Hook diagnosis:
Benchmark structure used:
Missing data:
Business-path connection:
```

If any required item is missing, do not output a final script. Output the missing evidence list and the next collection action instead.

Hard rules:

- No owned evidence, no recommendation.
- No product or case proof, no product script.
- No hook diagnosis, no first-three-second script.
- No benchmark structure, no final script.
- Do not replace concrete proof with abstract lines such as "serve a user and produce a result."
- Each creator script must anchor to a concrete object: a product, skill, published piece, customer case, workflow, or verified experience.
- If the user says the agent skipped the workflow, first audit the missed steps, then rerun the workflow before rewriting.

The repository CLI is the only execution core. A Codex or WorkBuddy surface must call these commands and must not reimplement scoring, review, or strategy logic. The workspace directory is only a data/report target.

Use the bundled CLI for deterministic work:

```powershell
python scripts/creatorbuddy.py <command>
```

## First Use

If the user has not initialized CreatorBuddy, run:

```powershell
python scripts/creatorbuddy.py quickstart
python scripts/creatorbuddy.py doctor
```

`quickstart` should be the default first-use path. It asks for owner, platform, account profile, product, benchmark account, and first content asset, then writes the workspace config automatically.

Manual equivalent:

```powershell
python scripts/creatorbuddy.py set-account --platform xiaohongshu --account-id "your-account-id" --account-name "你的账号"
python scripts/creatorbuddy.py set-profile --platform xiaohongshu --positioning "账号定位" --target-audience "目标用户" --content-directions "内容方向1,内容方向2" --commercial-goal "商业目标" --core-product "核心产品"
python scripts/creatorbuddy.py add-benchmark --platform xiaohongshu --account-id "benchmark-id" --account-name "对标账号"
python scripts/creatorbuddy.py onboarding-status
python scripts/creatorbuddy.py add-content --platform xiaohongshu --title "第一条内容资产" --body "正文或脚本" --metrics-json '{"likes":0,"comments":0}'
python scripts/creatorbuddy.py today
python scripts/creatorbuddy.py workflow-audit
```

每日完整运行：

```powershell
python scripts/creatorbuddy.py daily-run
```

注册 Windows 每日运行任务：

```powershell
python scripts/creatorbuddy.py install-scheduler --time 09:30 --register
```

录入外部适配器信号后标准化：

```powershell
python scripts/creatorbuddy.py collect --file "signals.jsonl"
```

生成和确认自成长策略：

```powershell
python scripts/creatorbuddy.py self-growth
python scripts/creatorbuddy.py approve-strategy --candidate-id "candidate-id"
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

Audit the full commercial MVP loop:

```powershell
python scripts/creatorbuddy.py workflow-audit
```

Record published content for later review:

```powershell
python scripts/creatorbuddy.py review --platform xiaohongshu --title "已发布标题" --metrics-json "{\"likes\":10,\"collects\":3}"
```

完整发布记录可以补充评论、转化和复盘经验：

```powershell
python scripts/creatorbuddy.py review --platform xiaohongshu --title "已发布标题" --published-at "2026-07-26T20:00:00" --metrics-json "{\"likes\":10}" --comments-json "[\"用户反馈\"]" --conversions-json "{\"inquiries\":1}" --lessons-json "[\"开头需要更具体\"]"
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
- If platform account data is not connected, block normal recommendations; only an explicit `today --allow-cold-start` may use config seeds for testing.
- Keep public samples, user-owned records, and AI inference separate.
- Preserve user data inside that user's CreatorBuddy workspace.

## Optional Web Workbench

The web workbench bundled in `assets/web` is a local MVP. It is useful for visual inspection, but Codex usage should not depend on it. If Node.js is unavailable, use the CLI commands instead.

The web MVP must stay focused on five usable console pages:

- 首页：今天该做什么；
- 账号中心：我是谁、卖什么、做什么平台；
- 内容机会：今日选题报告、评分和证据；
- 内容库：已发布内容和数据；
- 复盘中心：表现分析、策略候选和自成长沉淀。

The 账号中心 page must expose a first-use form that calls `/api/quickstart`, which delegates to `python scripts/creatorbuddy.py quickstart --non-interactive`. Do not write account configuration directly in browser-only logic.
