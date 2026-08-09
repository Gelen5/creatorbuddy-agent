# Content Asset Schema

CreatorBuddy stores creator-owned content assets in:

```text
data/published_content.jsonl
```

Despite the legacy filename, the file can hold ideas, drafts, scheduled posts, published posts, and reviewed posts. Each line is one JSON object.

## Required Fields

| Field | Type | Meaning |
| --- | --- | --- |
| `schema_version` | number | Current value is `1`. |
| `content_id` | string | Stable content identifier. |
| `platform` | string | `xiaohongshu`, `douyin`, `wechat-mp`, or `wechat-channels`. |
| `status` | string | `idea`, `draft`, `scheduled`, `published`, or `reviewed`. |
| `topic` | string | Topic or opportunity being tested. |
| `title` | string | Published title or draft title. |
| `created_at` | string | Local ISO timestamp. |
| `updated_at` | string | Local ISO timestamp. |

## Optional But Important Fields

| Field | Type | Meaning |
| --- | --- | --- |
| `cover` | string | Cover path, URL, or cover copy. |
| `body` | string | Xiaohongshu body, WeChat article text, or caption. |
| `script` | string | Short-video spoken script. |
| `proof_assets` | array | Screenshots, cases, workflow evidence, data, or files used as proof. |
| `product_bridge` | string | Product, service, course, community, or consultation path. |
| `published_at` | string | Actual publish timestamp when known. |
| `metrics` | object | Reads, plays, likes, saves, comments, shares, follows, etc. |
| `comments` | array/object | User feedback or selected comments. |
| `conversions` | object | DM count, inquiries, consultations, sales, revenue, or trial signups. |
| `review` | string | Post-publish diagnosis. |
| `next_change` | string | What to test next. |
| `lessons` | array | Lessons eligible for self-growth strategy candidates. |
| `source` | string | `manual_content_asset`, `platform_import`, `draft`, or adapter id. |

## CLI

Add a content asset:

```powershell
python scripts\creatorbuddy.py add-content --platform xiaohongshu --title "第一条内容" --body "正文或脚本"
```

Add metrics and lessons:

```powershell
python scripts\creatorbuddy.py add-content --platform xiaohongshu --title "第一条内容" --metrics-json "{\"likes\":12,\"saves\":4}" --lessons "标题要更具体"
```

Legacy command `review` still works for published content. New integrations should prefer `add-content` because it covers the full content lifecycle.

Generate a post-publish review from an existing content asset:

```powershell
python scripts\creatorbuddy.py post-review --content-id "xiaohongshu-20260809"
```

`post-review` appends a new reviewed record with `lessons`, writes a markdown report under `reports/`, and makes the lesson available to `self-growth`.

## Evidence Rule

Missing metrics must remain empty or `待补充信息`. Do not infer reads, sales, leads, or conversion from public samples.
