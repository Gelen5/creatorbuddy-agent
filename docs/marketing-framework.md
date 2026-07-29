# Marketing Framework Integration

CreatorBuddy now includes a local marketing judgment layer adapted from the useful parts of `coreyhaines31/marketingskills`:

- offer
- content strategy
- social distribution
- conversion
- attribution

This is not a vendored copy of the external skill pack. CreatorBuddy keeps the single execution core in `scripts/creatorbuddy.py` and uses the framework as a small scoring and brief-generation layer.

## Runtime Contract

The marketing layer reads only local CreatorBuddy workspace data:

- `config/agent_config.json`
- `data/normalized_signals.jsonl`
- `data/published_content.jsonl`
- `data/active_strategy.json`

It does not fetch external marketingskills files at runtime, does not make network calls, and does not treat public samples as owned account metrics.

## Output Fields

`today`, `daily-run`, and score generation add `marketing_judgment` to each topic candidate:

- `score` and `max_score`
- `dimensions`
- `offer_brief`
- `content_strategy`
- `social_distribution`
- `conversion_path`
- `attribution_plan`

`draft` adds `marketing_brief` with the same core sections so the content brief carries a product and measurement path, not only a platform writing checklist.

## Evidence Boundary

The framework is a prioritization aid. It can say a topic has a plausible offer bridge or conversion path, but it cannot prove leads, sales, revenue, or platform performance unless those facts exist in the workspace records.

Missing facts remain `待补充信息`.
