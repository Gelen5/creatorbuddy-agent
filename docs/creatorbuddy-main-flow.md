# CreatorBuddy Product Flow

This document is the productized main path for inner-test users. Keep this path small.

## Main User Flow

```text
quickstart
  -> run-daily
  -> collect-platform when new owned/public data is available
  -> draft
  -> precheck
  -> publish / add-content
  -> review
  -> self-growth
  -> next draft reads active strategy
```

## What Each Step Does

| Step | User meaning | CLI command | Durable output |
| --- | --- | --- | --- |
| Setup account | Tell CreatorBuddy who I am and what I sell | `quickstart` | `config/agent_config.json` |
| First value | See the first content opportunity and draft | `quickstart` | `reports/*first-run-opportunity.md`, `drafts/*first-draft.json` |
| Daily decision | Decide what to make today | `run-daily` | `data/latest_topic_scores.json`, `data/run_log.jsonl` |
| Data intake | Import owned metrics, benchmark details, or articles | `collect-platform` | `data/platform_raw_records.jsonl`, content/signals/sample libraries |
| Create content | Turn one opportunity into a platform brief | `draft` | `drafts/*.json` |
| Safety gate | Check title, body, evidence, platform risk | `precheck` | `reports/*precheck.md` |
| Publish record | Store draft/published asset and metrics | `add-content`, `wechat-publish`, or `review` | `data/published_content.jsonl` |
| Review | Explain performance after publishing | `post-review` / `review-due` | reports and lessons in content library |
| Self-growth | Propose reusable rules from evidence | `self-growth`, then `approve-strategy` | `data/pending_strategy_candidates.jsonl`, `data/active_strategy.json` |

## Product Rule

For normal users, expose only:

- `quickstart`
- `run-daily`
- `draft`
- `precheck`
- `collect-platform` through guided Web/API forms
- `wechat-publish` when platform is WeChat Official Account
- `add-content` / `review`

Keep these as advanced/internal tools:

- `collect`
- `import-benchmark`
- `segment-benchmark`
- `distill-creator`
- `review-due`
- `self-growth`
- `approve-strategy`
- `workflow-audit`
- `install-scheduler`

## Web Rule

The Web UI should not reimplement scoring, review, strategy, or publishing logic. It only gathers form input, calls the CLI through `assets/web/server.js`, and displays generated files.

The visible Web path should be:

```text
Account Center form
  -> /api/quickstart
  -> show first report and first draft
  -> /api/collect when the user has backend export, article html, note detail, or adapter JSON
  -> /api/daily-run
  -> /api/draft
  -> /api/prepublish
  -> /api/wechat-publish when needed
```

Avoid adding a second button or API that does the same job as `run-daily`.
