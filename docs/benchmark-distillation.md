# Benchmark Distillation

CreatorBuddy can import Xiaohongshu benchmark profile cards and turn them into reusable creator rules.

This is the first stable phase. It focuses on public profile-card data and local files. It does not require platform API keys.

## Workflow

```text
import-benchmark
-> benchmark_profile.json
-> benchmark_samples.jsonl
-> normalized_signals.jsonl
-> segment-benchmark
-> performance_segments.json / performance_segments.md
-> distill-creator
-> creator_clone.md
-> pending_strategy_candidates.jsonl
```

## Commands

Import a Xiaohongshu benchmark profile:

```powershell
python scripts\creatorbuddy.py import-benchmark --platform xiaohongshu --url "https://www.xiaohongshu.com/user/profile/..."
```

Segment samples by visible performance data:

```powershell
python scripts\creatorbuddy.py segment-benchmark --benchmark-id "benchmark-id"
```

Distill creator rules:

```powershell
python scripts\creatorbuddy.py distill-creator --benchmark-id "benchmark-id"
```

## Outputs

Each benchmark is stored under:

```text
%USERPROFILE%\CreatorBuddy\data\benchmarks\xiaohongshu\<benchmark_id>\
```

Files:

- `profile.html`: raw public profile HTML snapshot.
- `benchmark_profile.json`: account/profile metadata and evidence boundary.
- `benchmark_samples.jsonl`: profile-card samples with title, type, likes, cover URL, and understanding status.
- `performance_segments.json`: machine-readable sample segmentation.
- `performance_segments.md`: human-readable segmentation report.
- `creator_clone.md`: distilled positioning, topic buckets, transferable templates, anti-patterns, and self-check rubric.

Global files:

- `data/benchmark_samples.jsonl`: all benchmark samples.
- `data/raw_signals.jsonl`: imported benchmark titles as trend/source signals.
- `data/normalized_signals.jsonl`: normalized signals used by `today`.
- `data/pending_strategy_candidates.jsonl`: creator-clone strategy candidate awaiting approval.

## Understanding Status

Each sample is labeled:

- `metadata-only`: title, type, cover URL, and visible likes only.
- `partial`: cover image or media snapshot exists, but no full OCR/ASR/comment evidence.
- `full`: transcript, OCR, comments, or enough media text is available.

CreatorBuddy must not treat `metadata-only` samples as fully understood.

## Evidence Boundary

Public profile cards can identify benchmark candidates and visible like ranking.

They usually cannot prove:

- full note body;
- complete carousel pages;
- spoken script;
- OCR text from images;
- comment demand;
- saves, shares, or conversion;
- why a post performed well.

Those require detail links, logged-in browser capture, OCR/ASR, or manual imports.

## Copy Boundary

CreatorBuddy uses benchmark data to learn structure and decision patterns only.

Do not copy exact wording, personal identity, screenshots, images, claims, client stories, or unverifiable performance statements.
