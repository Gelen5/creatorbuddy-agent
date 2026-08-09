# Platform Data Intake v1

This is the first stable platform data intake layer for CreatorBuddy inner testing.

It does not bypass platform login, CAPTCHA, rate limits, or private APIs. It accepts user-provided exports, browser-saved HTML, known article/note URLs, or adapter JSON and writes them into CreatorBuddy's existing data model.

## Command

```powershell
python scripts\creatorbuddy.py collect-platform --platform <platform> --kind <kind> [--file path] [--url url] [--json json]
```

Supported in v1:

| Goal | Platform | Kind |
| --- | --- | --- |
| Import owned account content and metrics | `xiaohongshu`, `wechat-mp`, `douyin`, `wechat-channels` | `owned` |
| Import Xiaohongshu benchmark note detail | `xiaohongshu` | `xhs-note` |
| Import WeChat Official Account article | `wechat-mp` | `wechat-article` |
| Configure collection from Web | any supported platform | same kinds above |

## 1. Owned Account Data

Use this when the user exports backend data or an external adapter produces JSON/CSV.

```powershell
python scripts\creatorbuddy.py collect-platform --platform xiaohongshu --kind owned --json '[{"content_id":"xhs-001","title":"AI工具教程","likes":10,"saves":4,"comments":2}]'
```

Writes:

- `data/published_content.jsonl`
- `data/raw_signals.jsonl`
- `data/normalized_signals.jsonl`
- `data/platform_raw_records.jsonl`
- `reports/*-collect.md`

Evidence level: `A`, because the user provided owned account data.

## 2. Xiaohongshu Benchmark Note Detail

Use this when a Xiaohongshu note detail page, saved HTML, or adapter JSON is available.

```powershell
python scripts\creatorbuddy.py collect-platform --platform xiaohongshu --kind xhs-note --benchmark-id "bench001" --file note.html
```

Writes:

- `data/benchmark_samples.jsonl`
- `data/raw_signals.jsonl`
- `data/normalized_signals.jsonl`
- `data/platform_raw_records.jsonl`
- `reports/*-collect.md`

Evidence level: `B` when body/detail is present; `C` when only metadata is available.

Boundary: public note details are benchmark samples, not owned backend metrics.

## 3. WeChat Official Account Article

Public sample:

```powershell
python scripts\creatorbuddy.py collect-platform --platform wechat-mp --kind wechat-article --file article.html
```

Owned article:

```powershell
python scripts\creatorbuddy.py collect-platform --platform wechat-mp --kind wechat-article --file article.html --owned --content-id wx-001
```

Writes public articles into benchmark samples and owned articles into the content library.

Boundary: article HTML can provide title/body, but backend reads, shares, follows, and conversion data still need an owned export.

## 5. Web Collection Task

The Web `/api/collect` endpoint now calls the same CLI:

```text
POST /api/collect
{
  "platform": "xiaohongshu",
  "kind": "owned",
  "json": "[{\"content_id\":\"xhs-001\",\"title\":\"AI工具教程\",\"likes\":10}]"
}
```

The Account Center page exposes a Data Intake v1 form for:

- platform;
- kind;
- URL;
- local file path;
- JSON;
- benchmark id/name;
- owned article toggle.

The Web layer must not parse platform data itself. It only calls `collect-platform` and displays the generated report.
