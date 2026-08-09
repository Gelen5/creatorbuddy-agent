from __future__ import annotations

import argparse
import html
import json
import os
import re
import shutil
import subprocess
import sys
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen


SKILL_DIR = Path(__file__).resolve().parents[1]
TEMPLATE_CONFIG = SKILL_DIR / "templates" / "agent_config.json"
WEB_ASSET_DIR = SKILL_DIR / "assets" / "web"
WEB_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0 Safari/537.36"


DEFAULT_MARKETING_FRAMEWORK: dict[str, Any] = {
    "source": "Adapted from Corey Haines marketingskills concepts: offer, content strategy, social, conversion, attribution.",
    "dimensions": {
        "offer": {
            "max_score": 5,
            "checks": ["specific audience", "clear outcome", "proof asset", "low-friction next step"],
        },
        "content_strategy": {
            "max_score": 5,
            "checks": ["one core idea", "content pillar fit", "repeatable format", "evidence boundary"],
        },
        "social": {
            "max_score": 5,
            "checks": ["platform-native hook", "share/save/comment reason", "distribution angle"],
        },
        "conversion": {
            "max_score": 5,
            "checks": ["CTA path", "product bridge", "objection addressed"],
        },
        "attribution": {
            "max_score": 5,
            "checks": ["source tag", "content id", "conversion metric", "review checkpoint"],
        },
    },
}


DEFAULT_XIAOHONGSHU_PLAYBOOK: dict[str, Any] = {
    "source": "Sanitized Xiaohongshu operations playbook adapted from MIT-licensed public skill patterns.",
    "workflow": ["profile_gate", "conversion_path", "topic_planner", "title_design", "comment_reply", "prepublish_review"],
    "profile_gate": [
        "3-second clarity: who this helps, what problem it solves, why it is credible, and what to do next",
        "nickname, bio, pinned notes, content line, and product bridge should point to the same promise",
        "do not invent credentials, data, client outcomes, media exposure, or third-party endorsement",
    ],
    "topic_functions": ["attract", "resonate", "trust", "educate", "convert", "interact"],
    "title_modes": ["cover_short_line", "comment_style", "insight_judgment", "search_conversion"],
    "title_banned_terms": [
        "天花板", "YYDS", "绝绝子", "封神", "宝藏", "谁懂啊", "家人们", "闭眼入", "被问爆了", "高级感", "松弛感",
    ],
    "title_banned_patterns": [
        "不是", "而是", "表面", "背后", "看起来", "本质", "原来真正的",
    ],
    "comment_reply_rules": [
        "respond to the comment first, then extend the conversation",
        "do not route every comment to private messages",
        "for objections, acknowledge the concern, clarify the boundary, then offer a low-pressure next step",
    ],
    "conversion_path": ["attract", "screen", "trust", "act", "private_message", "revisit"],
    "measurement_fields": ["content_id", "publish_time", "24h_metrics", "48h_metrics", "7d_metrics", "conversion_signal"],
}


def default_workspace() -> Path:
    root = os.environ.get("CREATORBUDDY_HOME")
    if root:
        return Path(root)
    return Path.home() / "CreatorBuddy"


def now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def read_json(path: Path, fallback: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return fallback


def append_jsonl(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False) + "\n")


def parse_json_arg(raw: str, fallback: Any) -> Any:
    if not raw:
        return fallback
    raw = raw.strip()
    if len(raw) >= 2 and raw[0] == raw[-1] == "'":
        raw = raw[1:-1]
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        repaired = re.sub(r"([{,]\s*)([A-Za-z_][A-Za-z0-9_]*)\s*:", r'\1"\2":', raw)
        try:
            return json.loads(repaired)
        except json.JSONDecodeError:
            pass
        return {"raw_text": raw, "parse_status": "needs_data"}


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rows.append(json.loads(line))
        except Exception:
            continue
    return rows


def paths(workspace: Path) -> dict[str, Path]:
    data = workspace / "data"
    return {
        "workspace": workspace,
        "config": workspace / "config" / "agent_config.json",
        "content": data / "published_content.jsonl",
        "raw_signals": data / "raw_signals.jsonl",
        "signals": data / "normalized_signals.jsonl",
        "scores": data / "latest_topic_scores.json",
        "pending": data / "pending_strategy_candidates.jsonl",
        "active": data / "active_strategy.json",
        "runs": data / "run_log.jsonl",
        "reminders": data / "review_reminders.jsonl",
        "benchmark_samples": data / "benchmark_samples.jsonl",
        "benchmarks": data / "benchmarks",
        "reports": workspace / "reports",
        "drafts": workspace / "drafts",
        "publish": workspace / "publish",
    }


def platform_label(platform: str) -> str:
    return {
        "xiaohongshu": "小红书",
        "douyin": "抖音",
        "wechat-mp": "公众号",
        "wechat-channels": "视频号",
    }.get(platform, platform)


def load_config(workspace: Path) -> dict[str, Any]:
    config = read_json(paths(workspace)["config"], {})
    if not config:
        raise SystemExit("CreatorBuddy 尚未初始化。请先运行：python scripts/creatorbuddy.py init")
    config.setdefault("onboarding", {"current_step": "connect_account", "steps": ["connect_account", "choose_benchmark", "import_content", "start_growth"]})
    config.setdefault("review_offsets", ["2h", "24h", "48h", "7d"])
    config.setdefault("marketing_framework", DEFAULT_MARKETING_FRAMEWORK)
    config.setdefault("xiaohongshu_playbook", DEFAULT_XIAOHONGSHU_PLAYBOOK)
    return config


def save_config(workspace: Path, config: dict[str, Any]) -> None:
    write_json(paths(workspace)["config"], config)


def find_platform(config: dict[str, Any], platform: str) -> dict[str, Any] | None:
    return next((item for item in config.get("platforms", []) if item.get("platform") == platform), None)


def update_onboarding(config: dict[str, Any], workspace: Path) -> None:
    platforms = [item for item in config.get("platforms", []) if item.get("enabled", True)]
    connected = any(item.get("account_id") and item.get("collect_own_account", True) for item in platforms)
    profiled = any(
        item.get("account_id")
        and item.get("positioning")
        and item.get("target_audience")
        and (item.get("content_directions") or item.get("benchmark_industries"))
        for item in platforms
    )
    benchmarked = any(item.get("benchmark_accounts") for item in platforms)
    imported = len(read_jsonl(paths(workspace)["content"])) > 0
    grown = bool(read_json(paths(workspace)["scores"], []))
    steps = [connected, profiled, benchmarked, imported, grown]
    config.setdefault("onboarding", {})["steps"] = [
        "connect_account", "configure_profile", "choose_benchmark", "import_content", "start_growth"
    ]
    config["onboarding"]["current_step"] = next(
        (step for step, complete in zip(config["onboarding"]["steps"], steps) if not complete),
        "start_growth",
    )


def require_account(workspace: Path, allow_cold_start: bool = False) -> dict[str, Any]:
    config = load_config(workspace)
    connected = [
        item for item in config.get("platforms", [])
        if item.get("enabled", True) and item.get("account_id") and item.get("collect_own_account", True)
    ]
    if not connected and not allow_cold_start:
        raise SystemExit("尚未连接自有账号。请先运行 set-account；如仅测试种子流程，请显式使用 --allow-cold-start。")
    return config


def safe_slug(value: str, fallback: str = "item") -> str:
    cleaned = re.sub(r"[^A-Za-z0-9\u4e00-\u9fff_-]+", "-", value.strip())
    cleaned = cleaned.strip("-_")[:80]
    return cleaned or fallback


def fetch_text(url: str) -> str:
    request = Request(
        url,
        headers={
            "User-Agent": WEB_UA,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Referer": "https://www.xiaohongshu.com/",
        },
    )
    try:
        with urlopen(request, timeout=60) as response:
            return response.read().decode("utf-8", errors="replace")
    except HTTPError as error:
        detail = error.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {error.code}: {detail[:240]}") from error
    except URLError as error:
        raise RuntimeError(f"request failed: {error}") from error


def fetch_binary(url: str) -> bytes:
    request = Request(url, headers={"User-Agent": WEB_UA, "Referer": "https://www.xiaohongshu.com/"})
    with urlopen(request, timeout=60) as response:
        return response.read()


def normalize_url(url: str | None) -> str:
    if not url:
        return ""
    url = url.replace("\\u002F", "/")
    if url.startswith("//"):
        return "https:" + url
    if url.startswith("http://"):
        return "https://" + url[len("http://"):]
    return url


def parse_xhs_initial_state(html: str) -> dict[str, Any]:
    marker = "window.__INITIAL_STATE__="
    start = html.find(marker)
    if start < 0:
        raise RuntimeError("window.__INITIAL_STATE__ not found; page may require login or page structure changed")
    start += len(marker)
    end = html.find("</script>", start)
    if end < 0:
        raise RuntimeError("initial state script terminator not found")
    raw = html[start:end].strip().rstrip(";")
    raw = re.sub(r"\bundefined\b", "null", raw)
    return json.loads(raw)


def extract_xhs_profile(data: dict[str, Any]) -> dict[str, Any]:
    user = data.get("user", {}) if isinstance(data.get("user"), dict) else {}
    user_page = user.get("userPageData", {}) if isinstance(user.get("userPageData"), dict) else {}
    cards: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()

    for group in user.get("notes", []):
        if not isinstance(group, list):
            continue
        for item in group:
            if not isinstance(item, dict):
                continue
            card = item.get("noteCard")
            if not isinstance(card, dict):
                continue
            cover = card.get("cover") if isinstance(card.get("cover"), dict) else {}
            interact = card.get("interactInfo") if isinstance(card.get("interactInfo"), dict) else {}
            author = card.get("user") if isinstance(card.get("user"), dict) else {}
            title = str(card.get("displayTitle") or "").strip()
            cover_url = normalize_url(str(cover.get("urlDefault") or cover.get("urlPre") or ""))
            key = (title, cover_url)
            if key in seen:
                continue
            seen.add(key)
            liked_count = interact.get("likedCount")
            try:
                liked_count = int(str(liked_count).replace(",", ""))
            except Exception:
                liked_count = 0
            note_id = str(card.get("noteId") or "")
            content_type = str(card.get("type") or "unknown")
            cards.append(
                {
                    "sample_id": note_id or f"xhs-card-{len(cards) + 1}",
                    "note_id": note_id,
                    "xsec_token": card.get("xsecToken") or item.get("xsecToken") or "",
                    "type": content_type,
                    "title": title,
                    "liked_count": liked_count,
                    "author": author.get("nickname") or author.get("nickName") or "",
                    "user_id": author.get("userId") or "",
                    "cover_url": cover_url,
                    "cover_width": cover.get("width"),
                    "cover_height": cover.get("height"),
                }
            )

    return {
        "basic_info": user_page.get("basicInfo") or {},
        "interactions": user_page.get("interactions") or [],
        "tags": user_page.get("tags") or [],
        "items": cards,
    }


def sample_understanding_status(sample: dict[str, Any]) -> dict[str, Any]:
    has_cover = bool(sample.get("cover_file"))
    has_transcript = bool(sample.get("transcript"))
    has_ocr = bool(sample.get("ocr_text"))
    if has_transcript or has_ocr:
        level = "full"
    elif has_cover:
        level = "partial"
    else:
        level = "metadata-only"
    return {
        "understanding_level": level,
        "video_downloaded": bool(sample.get("video_file")),
        "images_downloaded": has_cover,
        "ocr_text": has_ocr,
        "asr_transcript": has_transcript,
        "comments_captured": bool(sample.get("comments")),
        "reason": "profile card import; full note body/comment/media requires detail link or logged-in browser" if level != "full" else "media text is available",
    }


def benchmark_dir(workspace: Path, platform: str, benchmark_id: str) -> Path:
    return paths(workspace)["benchmarks"] / platform / safe_slug(benchmark_id, "benchmark")


def command_set_account(args: argparse.Namespace) -> int:
    workspace = Path(args.workspace or default_workspace())
    config = load_config(workspace)
    platform_cfg = find_platform(config, args.platform)
    if platform_cfg is None:
        raise SystemExit(f"未找到平台配置：{args.platform}")
    platform_cfg.update({
        "account_id": args.account_id,
        "account_name": args.account_name,
        "enabled": True,
        "collect_own_account": True,
    })
    update_onboarding(config, workspace)
    save_config(workspace, config)
    print(json.dumps({"ok": True, "platform": args.platform, "next_step": config["onboarding"]["current_step"]}, ensure_ascii=False, indent=2))
    return 0


def split_csv(raw: str) -> list[str]:
    if not raw:
        return []
    return [item.strip() for item in re.split(r"[,，\n]", raw) if item.strip()]


def command_set_profile(args: argparse.Namespace) -> int:
    workspace = Path(args.workspace or default_workspace())
    config = load_config(workspace)
    platform_cfg = find_platform(config, args.platform)
    if platform_cfg is None:
        raise SystemExit(f"未找到平台配置：{args.platform}")
    updates: dict[str, Any] = {}
    for key in ["positioning", "target_audience", "commercial_goal", "core_product"]:
        value = getattr(args, key)
        if value:
            updates[key] = value
    if args.content_directions:
        updates["content_directions"] = split_csv(args.content_directions)
    if args.keywords:
        platform_cfg["benchmark_industries"] = split_csv(args.keywords)
    if not updates and not args.keywords:
        raise SystemExit("没有提供可更新的账号画像字段。")
    platform_cfg.update(updates)
    update_onboarding(config, workspace)
    save_config(workspace, config)
    print(json.dumps({
        "ok": True,
        "platform": args.platform,
        "updated": sorted([*updates.keys(), *(["benchmark_industries"] if args.keywords else [])]),
        "next_step": config["onboarding"]["current_step"],
    }, ensure_ascii=False, indent=2))
    return 0


def command_add_benchmark(args: argparse.Namespace) -> int:
    workspace = Path(args.workspace or default_workspace())
    config = load_config(workspace)
    platform_cfg = find_platform(config, args.platform)
    if platform_cfg is None:
        raise SystemExit(f"未找到平台配置：{args.platform}")
    accounts = platform_cfg.setdefault("benchmark_accounts", [])
    account = {"account_id": args.account_id, "account_name": args.account_name, "url": args.url or "", "enabled": True}
    existing = next((item for item in accounts if item.get("account_id") == args.account_id), None)
    if existing:
        existing.update(account)
    else:
        accounts.append(account)
    update_onboarding(config, workspace)
    save_config(workspace, config)
    print(json.dumps({"ok": True, "platform": args.platform, "benchmark_account": account, "next_step": config["onboarding"]["current_step"]}, ensure_ascii=False, indent=2))
    return 0


def command_import_benchmark(args: argparse.Namespace) -> int:
    workspace = Path(args.workspace or default_workspace())
    config = load_config(workspace)
    if args.platform != "xiaohongshu":
        raise SystemExit("第一期 import-benchmark 先支持 xiaohongshu。其他平台请先用 collect 导入标准化信号。")

    html = Path(args.html_file).read_text(encoding="utf-8") if args.html_file else fetch_text(args.url)
    profile = extract_xhs_profile(parse_xhs_initial_state(html))
    basic = profile.get("basic_info") or {}
    benchmark_name = args.name or str(basic.get("nickname") or "xiaohongshu-benchmark")
    benchmark_id = args.benchmark_id or safe_slug(str(basic.get("redId") or basic.get("userId") or benchmark_name), "xhs-benchmark")
    out_dir = benchmark_dir(workspace, args.platform, benchmark_id)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "profile.html").write_text(html, encoding="utf-8")

    samples: list[dict[str, Any]] = []
    image_dir = out_dir / "covers"
    for index, item in enumerate(profile.get("items", []), start=1):
        sample = {
            **item,
            "schema_version": 1,
            "benchmark_id": benchmark_id,
            "benchmark_name": benchmark_name,
            "platform": args.platform,
            "source": "xiaohongshu_public_profile",
            "source_url": args.url,
            "imported_at": now_iso(),
        }
        if args.download_covers and item.get("cover_url") and index <= args.cover_limit:
            image_dir.mkdir(parents=True, exist_ok=True)
            suffix = Path(urlparse(str(item["cover_url"])).path).suffix or ".webp"
            cover_path = image_dir / f"cover_{index:02d}{suffix}"
            try:
                cover_path.write_bytes(fetch_binary(str(item["cover_url"])))
                sample["cover_file"] = str(cover_path)
            except Exception as error:
                sample["cover_download_error"] = str(error)
        sample["understanding"] = sample_understanding_status(sample)
        samples.append(sample)

    profile_payload = {
        "schema_version": 1,
        "benchmark_id": benchmark_id,
        "benchmark_name": benchmark_name,
        "platform": args.platform,
        "source_url": args.url,
        "imported_at": now_iso(),
        "basic_info": basic,
        "interactions": profile.get("interactions", []),
        "tags": profile.get("tags", []),
        "sample_count": len(samples),
        "evidence_boundary": "Public profile cards are benchmark candidates. Detail body, comments, full media, OCR, and ASR require detail links or logged-in browser capture.",
    }
    write_json(out_dir / "benchmark_profile.json", profile_payload)
    write_jsonl(out_dir / "benchmark_samples.jsonl", samples)

    for sample in samples:
        append_jsonl(paths(workspace)["benchmark_samples"], sample)
        append_jsonl(
            paths(workspace)["raw_signals"],
            {
                "signal_id": f"{benchmark_id}-{sample.get('sample_id')}",
                "platform": args.platform,
                "topic": sample.get("title"),
                "heat": sample.get("liked_count", 0),
                "evidence_score": 8 if sample.get("understanding", {}).get("understanding_level") == "metadata-only" else 11,
                "evidence_level": "C" if sample.get("understanding", {}).get("understanding_level") == "metadata-only" else "B",
                "source": "benchmark_profile_import",
                "source_path": str(out_dir / "benchmark_samples.jsonl"),
                "observed_at": now_iso(),
            },
        )

    platform_cfg = find_platform(config, args.platform)
    if platform_cfg is not None:
        accounts = platform_cfg.setdefault("benchmark_accounts", [])
        if not any(item.get("account_id") == benchmark_id for item in accounts):
            accounts.append({"account_id": benchmark_id, "account_name": benchmark_name, "url": args.url, "enabled": True})
    update_onboarding(config, workspace)
    save_config(workspace, config)
    normalized = normalize_signals(workspace)
    print(json.dumps({
        "ok": True,
        "benchmark_id": benchmark_id,
        "profile_path": str(out_dir / "benchmark_profile.json"),
        "samples_path": str(out_dir / "benchmark_samples.jsonl"),
        "sample_count": len(samples),
        "normalized_signal_count": len(normalized),
        "next_step": "segment-benchmark",
    }, ensure_ascii=False, indent=2))
    return 0


def classify_metric_segments(samples: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    ranked = sorted(samples, key=lambda item: int(item.get("liked_count", 0) or 0), reverse=True)
    compact = [
        {
            "sample_id": item.get("sample_id"),
            "title": item.get("title"),
            "liked_count": item.get("liked_count", 0),
            "type": item.get("type"),
            "understanding_level": item.get("understanding", {}).get("understanding_level", "metadata-only"),
        }
        for item in ranked
    ]
    return {
        "highest_likes": compact[:5],
        "weak_samples": list(reversed(compact[-5:])) if compact else [],
        "needs_detail_fetch": [item for item in compact if item.get("understanding_level") == "metadata-only"][:10],
        "high_saves": [],
        "high_comments": [],
        "high_shares": [],
    }


def command_segment_benchmark(args: argparse.Namespace) -> int:
    workspace = Path(args.workspace or default_workspace())
    out_dir = benchmark_dir(workspace, args.platform, args.benchmark_id)
    source = out_dir / "benchmark_samples.jsonl"
    samples = read_jsonl(source)
    if not samples:
        raise SystemExit(f"没有找到对标样本：{source}")
    segments = {
        "schema_version": 1,
        "benchmark_id": args.benchmark_id,
        "platform": args.platform,
        "created_at": now_iso(),
        "sample_count": len(samples),
        "segments": classify_metric_segments(samples),
        "evidence_boundary": "Profile-card import currently segments mostly by visible likes. Saves/comments/shares stay empty until detail or logged-in data is imported.",
    }
    write_json(out_dir / "performance_segments.json", segments)
    lines = [
        f"# 对标样本分层｜{args.benchmark_id}",
        "",
        f"生成时间：{segments['created_at']}",
        "",
        "## 高点赞样本",
    ]
    for item in segments["segments"]["highest_likes"]:
        lines.append(f"- {item.get('liked_count', 0)}｜{item.get('title')}｜{item.get('understanding_level')}")
    lines.extend(["", "## 弱样本"])
    for item in segments["segments"]["weak_samples"]:
        lines.append(f"- {item.get('liked_count', 0)}｜{item.get('title')}｜{item.get('understanding_level')}")
    lines.extend(["", "## 需要详情页/登录态补全"])
    for item in segments["segments"]["needs_detail_fetch"]:
        lines.append(f"- {item.get('title')}｜{item.get('understanding_level')}")
    (out_dir / "performance_segments.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps({"ok": True, "segments_path": str(out_dir / "performance_segments.json"), "report": str(out_dir / "performance_segments.md")}, ensure_ascii=False, indent=2))
    return 0


def infer_topic_buckets(samples: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rules = [
        ("教程/方法", ["教程", "方法", "怎么", "步骤", "指南", "入门"]),
        ("避坑/错误", ["避坑", "错误", "别", "不要", "踩坑"]),
        ("工具/清单", ["工具", "清单", "模板", "合集", "推荐"]),
        ("案例/复盘", ["案例", "复盘", "实操", "结果", "经验"]),
        ("情绪/共鸣", ["焦虑", "普通人", "终于", "不会", "卡住"]),
    ]
    buckets: list[dict[str, Any]] = []
    for name, keywords in rules:
        matched = [item for item in samples if any(keyword in str(item.get("title") or "") for keyword in keywords)]
        if matched:
            buckets.append({"name": name, "count": len(matched), "examples": [item.get("title") for item in matched[:3]]})
    if not buckets and samples:
        buckets.append({"name": "待人工命名", "count": len(samples), "examples": [item.get("title") for item in samples[:3]]})
    return buckets


def command_distill_creator(args: argparse.Namespace) -> int:
    workspace = Path(args.workspace or default_workspace())
    out_dir = benchmark_dir(workspace, args.platform, args.benchmark_id)
    profile = read_json(out_dir / "benchmark_profile.json", {})
    samples = read_jsonl(out_dir / "benchmark_samples.jsonl")
    if not samples:
        raise SystemExit(f"没有找到对标样本：{out_dir / 'benchmark_samples.jsonl'}")
    segments = read_json(out_dir / "performance_segments.json", {})
    if not segments:
        segments = {"segments": classify_metric_segments(samples)}
        write_json(out_dir / "performance_segments.json", segments)
    basic = profile.get("basic_info") or {}
    benchmark_name = profile.get("benchmark_name") or basic.get("nickname") or args.benchmark_id
    topic_buckets = infer_topic_buckets(samples)
    high_like_titles = [item.get("title") for item in segments.get("segments", {}).get("highest_likes", [])[:5]]
    understanding_counts: dict[str, int] = {}
    for sample in samples:
        level = sample.get("understanding", {}).get("understanding_level", "metadata-only")
        understanding_counts[level] = understanding_counts.get(level, 0) + 1

    lines = [
        f"# Creator Clone: {benchmark_name}",
        "",
        "## Source Inventory",
        f"- platform: {args.platform}",
        f"- benchmark_id: {args.benchmark_id}",
        f"- sample_count: {len(samples)}",
        f"- understanding: {json.dumps(understanding_counts, ensure_ascii=False)}",
        "",
        "## Positioning",
        f"- nickname: {basic.get('nickname') or benchmark_name}",
        f"- description: {basic.get('desc') or basic.get('description') or '待补充信息'}",
        "- evidence boundary: profile-card import cannot prove full script, comment demand, or conversion mechanism.",
        "",
        "## Topic Buckets",
    ]
    for bucket in topic_buckets:
        lines.append(f"- {bucket['name']}｜{bucket['count']} 条｜例：{' / '.join(str(x) for x in bucket['examples'])}")
    lines.extend(["", "## Performance Segmentation", "### Highest Likes"])
    for title in high_like_titles:
        lines.append(f"- {title}")
    lines.extend(
        [
            "",
            "## Transferable Templates",
            "1. Searchable problem -> concrete step list -> low-pressure save/comment action.",
            "2. User stuck point -> mistake correction -> proof needed before conversion.",
            "3. Tool or workflow promise -> small task -> completion standard.",
            "",
            "## Anti-Patterns",
            "- Do not copy exact wording, personal identity, images, screenshots, claims, or creator story.",
            "- Do not treat metadata-only samples as fully understood.",
            "- Do not infer comments, saves, shares, or conversion without captured evidence.",
            "",
            "## Self-Check Rubric",
            "- Does the topic map to one bucket?",
            "- Is the hook concrete enough for the target user?",
            "- Is proof required and available?",
            "- Is the next action low pressure?",
            "- Are source limitations still visible?",
            "",
            "## Next Candidate Ideas",
        ]
    )
    for bucket in topic_buckets[:5]:
        lines.append(f"- 用「{bucket['name']}」做一条适配自己账号的原创内容，先选一个可验证的小任务。")
    clone_path = out_dir / "creator_clone.md"
    clone_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    append_jsonl(
        paths(workspace)["pending"],
        {
            "candidate_id": f"creator-clone-{args.benchmark_id}-{datetime.now().strftime('%Y%m%d%H%M%S')}",
            "created_at": now_iso(),
            "applies_to": [args.platform],
            "rule": f"参考 {benchmark_name} 的对标蒸馏时，只迁移选题桶和结构规则，不复制原文、身份、素材或未经验证的成绩。",
            "evidence": str(clone_path),
        },
    )
    print(json.dumps({"ok": True, "clone_path": str(clone_path), "topic_bucket_count": len(topic_buckets)}, ensure_ascii=False, indent=2))
    return 0


def command_onboarding_status(args: argparse.Namespace) -> int:
    workspace = Path(args.workspace or default_workspace())
    config = load_config(workspace)
    update_onboarding(config, workspace)
    save_config(workspace, config)
    platforms = [item for item in config.get("platforms", []) if item.get("enabled", True)]
    connected = [item for item in platforms if item.get("account_id") and item.get("collect_own_account", True)]
    profiled = [
        item for item in connected
        if item.get("positioning") and item.get("target_audience") and (item.get("content_directions") or item.get("benchmark_industries"))
    ]
    benchmarked = [item for item in platforms if item.get("benchmark_accounts")]
    published_count = len(read_jsonl(paths(workspace)["content"]))
    scores_ready = bool(read_json(paths(workspace)["scores"], []))
    result = {
        "ok": bool(connected and profiled and benchmarked and published_count > 0 and scores_ready),
        "current_step": config["onboarding"]["current_step"],
        "steps": {
            "connect_account": bool(connected),
            "configure_profile": bool(profiled),
            "choose_benchmark": bool(benchmarked),
            "import_content": published_count > 0,
            "start_growth": scores_ready,
        },
        "connected_platforms": [item.get("platform") for item in connected],
        "profiled_platforms": [item.get("platform") for item in profiled],
        "published_content_count": published_count,
        "next_action": {
            "connect_account": "set-account",
            "configure_profile": "set-profile",
            "choose_benchmark": "add-benchmark",
            "import_content": "add-content or review",
            "start_growth": "today",
        }.get(config["onboarding"]["current_step"], "today"),
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


def item_status(ok: bool, evidence: list[str], missing: list[str]) -> dict[str, Any]:
    return {
        "status": "complete" if ok else "incomplete",
        "evidence": evidence,
        "missing": missing,
    }


def command_workflow_audit(args: argparse.Namespace) -> int:
    workspace = Path(args.workspace or default_workspace())
    config = load_config(workspace)
    ps = paths(workspace)
    platforms = [item for item in config.get("platforms", []) if item.get("enabled", True)]
    connected = [item for item in platforms if item.get("account_id") and item.get("collect_own_account", True)]
    profiled = [
        item for item in connected
        if item.get("positioning") and item.get("target_audience") and (item.get("content_directions") or item.get("benchmark_industries"))
    ]
    content_rows = read_jsonl(ps["content"])
    scores = read_json(ps["scores"], [])
    active = read_json(ps["active"], {"active_rules": []})
    active_rules = active.get("active_rules") or []
    pending = read_jsonl(ps["pending"])
    reports = list(ps["reports"].glob("*")) if ps["reports"].exists() else []
    drafts = list(ps["drafts"].glob("*.json")) if ps["drafts"].exists() else []
    xhs_draft_paths = []
    strategy_readback_paths = []
    for draft_path in drafts:
        draft = read_json(draft_path, {})
        if draft.get("platform") == "xiaohongshu" and draft.get("xiaohongshu_brief"):
            xhs_draft_paths.append(draft_path)
        if draft.get("strategy_context"):
            strategy_readback_paths.append(draft_path)
    clone_paths = list(ps["benchmarks"].glob("xiaohongshu/*/creator_clone.md")) if ps["benchmarks"].exists() else []
    precheck_reports = [path for path in reports if path.name.endswith("-precheck.json")]
    post_review_reports = [path for path in reports if path.name.endswith("-post-review.md")]
    today_reports = [path for path in reports if path.name.endswith("-今日内容机会.md")]
    reviewed_rows = [row for row in content_rows if row.get("status") == "reviewed" or row.get("review_status") == "reviewed"]

    expected_steps = ["connect_account", "configure_profile", "choose_benchmark", "import_content", "start_growth"]
    items = {
        "1_first_use_flow": item_status(
            config.get("onboarding", {}).get("steps") == expected_steps,
            [str(ps["config"])],
            [] if config.get("onboarding", {}).get("steps") == expected_steps else ["onboarding steps mismatch"],
        ),
        "2_account_config_center": item_status(
            bool(connected and profiled),
            [str(ps["config"])],
            [] if connected and profiled else ["set-account", "set-profile"],
        ),
        "3_content_asset_database": item_status(
            ps["content"].exists() and bool(content_rows),
            [str(ps["content"])],
            [] if content_rows else ["add-content or review"],
        ),
        "4_today_opportunity_report": item_status(
            bool(scores and today_reports),
            [str(ps["scores"]), *[str(path) for path in today_reports[-1:]]],
            [] if scores and today_reports else ["today"],
        ),
        "5_xiaohongshu_loop": item_status(
            bool(any(item.get("platform") == "xiaohongshu" for item in profiled) and xhs_draft_paths and precheck_reports),
            [str(path) for path in xhs_draft_paths[-1:] + precheck_reports[-1:]],
            [] if xhs_draft_paths and precheck_reports else ["draft --platform xiaohongshu", "precheck --platform xiaohongshu"],
        ),
        "6_benchmark_distillation": item_status(
            bool(read_jsonl(ps["benchmark_samples"]) and clone_paths),
            [str(ps["benchmark_samples"]), *[str(path) for path in clone_paths[-1:]]],
            [] if clone_paths else ["import-benchmark", "segment-benchmark", "distill-creator"],
        ),
        "7_prepublish_check": item_status(
            bool(precheck_reports),
            [str(path) for path in precheck_reports[-1:]],
            [] if precheck_reports else ["precheck"],
        ),
        "8_postpublish_review": item_status(
            bool(reviewed_rows and post_review_reports),
            [str(ps["content"]), *[str(path) for path in post_review_reports[-1:]]],
            [] if reviewed_rows and post_review_reports else ["post-review"],
        ),
        "9_strategy_approval_and_readback": item_status(
            bool(pending and active_rules and strategy_readback_paths),
            [str(ps["pending"]), str(ps["active"]), *[str(path) for path in strategy_readback_paths[-1:]]],
            [] if pending and active_rules and strategy_readback_paths else ["self-growth", "approve-strategy", "draft after approve-strategy"],
        ),
    }
    ok = all(item["status"] == "complete" for item in items.values())
    print(json.dumps({"ok": ok, "workspace": str(workspace), "items": items}, ensure_ascii=False, indent=2))
    return 0 if ok else 1


def initialize_workspace(workspace: Path, workspace_id: str = "", owner: str = "") -> dict[str, Any]:
    ps = paths(workspace)
    config = read_json(TEMPLATE_CONFIG, {})
    config["workspace_id"] = workspace_id or config.get("workspace_id") or "creatorbuddy-workspace"
    config["owner"] = owner or config.get("owner") or ""
    config["updated_at"] = now_iso()
    write_json(ps["config"], config)
    write_json(ps["scores"], [])
    ps["content"].parent.mkdir(parents=True, exist_ok=True)
    ps["content"].write_text("", encoding="utf-8")
    ps["raw_signals"].write_text("", encoding="utf-8")
    ps["signals"].write_text("", encoding="utf-8")
    ps["reminders"].write_text("", encoding="utf-8")
    ps["pending"].write_text("", encoding="utf-8")
    ps["benchmark_samples"].write_text("", encoding="utf-8")
    write_json(
        ps["active"],
        {
            "schema_version": 1,
            "updated_at": now_iso(),
            "workspace_id": config["workspace_id"],
            "active_rules": [
                {
                    "rule_id": "platform-differentiation",
                    "status": "active",
                    "rule": "同一主题要按平台分别判断表达方式，不直接跨平台复制。",
                    "evidence": "CreatorBuddy default rule",
                }
            ],
        },
    )
    ps["reports"].mkdir(parents=True, exist_ok=True)
    ps["drafts"].mkdir(parents=True, exist_ok=True)
    return config


def command_init(args: argparse.Namespace) -> int:
    workspace = Path(args.workspace or default_workspace())
    ps = paths(workspace)
    if ps["config"].exists() and not args.force:
        print(json.dumps({"ok": True, "workspace": str(workspace), "message": "already initialized"}, ensure_ascii=False, indent=2))
        return 0

    initialize_workspace(workspace, args.workspace_id, args.owner)
    print(json.dumps({"ok": True, "workspace": str(workspace), "config": str(ps["config"])}, ensure_ascii=False, indent=2))
    return 0


def prompt_value(label: str, current: str = "", required: bool = True) -> str:
    suffix = f" [{current}]" if current else ""
    while True:
        value = input(f"{label}{suffix}: ").strip()
        if value:
            return value
        if current:
            return current
        if not required:
            return ""
        print("这个字段建议填写，后续选题会用到。")


def quickstart_value(args: argparse.Namespace, name: str, label: str, current: str = "", required: bool = True) -> str:
    value = str(getattr(args, name, "") or "").strip()
    if value:
        return value
    if args.non_interactive:
        if required and not current:
            raise SystemExit(f"quickstart 缺少必要参数：--{name.replace('_', '-')}")
        return current
    return prompt_value(label, current, required)


def command_quickstart(args: argparse.Namespace) -> int:
    workspace = Path(args.workspace or default_workspace())
    ps = paths(workspace)
    if not ps["config"].exists():
        initialize_workspace(workspace, args.workspace_id, args.owner)

    config = load_config(workspace)
    platform = args.platform or "xiaohongshu"
    platform_cfg = find_platform(config, platform)
    if platform_cfg is None:
        supported = ", ".join(str(item.get("platform")) for item in config.get("platforms", []))
        raise SystemExit(f"未找到平台配置：{platform}。当前支持：{supported}")

    owner = quickstart_value(args, "owner", "你是谁 / 工作区名称", str(config.get("owner") or ""), required=False)
    account_name = quickstart_value(args, "account_name", "你的账号名称", str(platform_cfg.get("account_name") or ""))
    account_id = quickstart_value(args, "account_id", "你的账号 ID / 备注 ID", str(platform_cfg.get("account_id") or safe_slug(account_name, "account")))
    positioning = quickstart_value(args, "positioning", "你的账号定位", str(platform_cfg.get("positioning") or ""))
    target_audience = quickstart_value(args, "target_audience", "你的目标用户是谁", str(platform_cfg.get("target_audience") or ""))
    content_directions = quickstart_value(
        args,
        "content_directions",
        "你的内容方向，多个用逗号隔开",
        "，".join(platform_cfg.get("content_directions", []) or []),
    )
    commercial_goal = quickstart_value(args, "commercial_goal", "你的商业目标", str(platform_cfg.get("commercial_goal") or ""), required=False)
    core_product = quickstart_value(args, "core_product", "你的核心产品 / 服务 / 承接方式", str(platform_cfg.get("core_product") or ""), required=False)
    keywords = quickstart_value(
        args,
        "keywords",
        "你关注的行业关键词，多个用逗号隔开",
        "，".join(platform_cfg.get("benchmark_industries", []) or []),
        required=False,
    )
    benchmark_name = quickstart_value(args, "benchmark_name", "你的对标账号名称", "", required=False)
    benchmark_id = quickstart_value(
        args,
        "benchmark_id",
        "对标账号 ID / 备注 ID",
        safe_slug(benchmark_name, "benchmark") if benchmark_name else "",
        required=False,
    )
    first_title = quickstart_value(args, "first_title", "你发过的一条内容标题", "", required=False)
    first_body = quickstart_value(args, "first_body", "这条内容的正文 / 脚本", "", required=False)

    if owner:
        config["owner"] = owner
    platform_cfg.update({
        "account_id": account_id,
        "account_name": account_name,
        "enabled": True,
        "collect_own_account": True,
        "positioning": positioning,
        "target_audience": target_audience,
        "content_directions": split_csv(content_directions),
        "commercial_goal": commercial_goal,
        "core_product": core_product,
    })
    if keywords:
        platform_cfg["benchmark_industries"] = split_csv(keywords)
    if core_product:
        product_keywords = config.setdefault("product_keywords", [])
        for item in split_csv(core_product):
            if item not in product_keywords:
                product_keywords.append(item)
    if benchmark_name:
        accounts = platform_cfg.setdefault("benchmark_accounts", [])
        benchmark = {
            "account_id": benchmark_id or safe_slug(benchmark_name, "benchmark"),
            "account_name": benchmark_name,
            "url": args.benchmark_url or "",
            "enabled": True,
        }
        existing = next((item for item in accounts if item.get("account_id") == benchmark["account_id"]), None)
        if existing:
            existing.update(benchmark)
        else:
            accounts.append(benchmark)

    update_onboarding(config, workspace)
    save_config(workspace, config)

    content_id = ""
    if first_title:
        row = {
            "schema_version": 1,
            "content_id": args.first_content_id or f"{platform}-{datetime.now().strftime('%Y%m%d%H%M%S')}",
            "platform": platform,
            "status": "published",
            "topic": args.first_topic or first_title,
            "title": first_title,
            "cover": "",
            "body": first_body,
            "script": "",
            "proof_assets": [],
            "product_bridge": core_product,
            "published_at": args.first_published_at or "",
            "metrics": parse_json_arg(args.first_metrics_json, {}),
            "comments": [],
            "conversions": {},
            "review": "",
            "next_change": "",
            "lessons": [],
            "source": "quickstart",
            "created_at": now_iso(),
            "updated_at": now_iso(),
        }
        append_jsonl(ps["content"], row)
        content_id = row["content_id"]
        update_onboarding(config, workspace)
        save_config(workspace, config)

    status_payload = {
        "ok": True,
        "workspace": str(workspace),
        "platform": platform,
        "account": {
            "account_id": account_id,
            "account_name": account_name,
            "positioning": positioning,
            "target_audience": target_audience,
            "content_directions": split_csv(content_directions),
            "commercial_goal": commercial_goal,
            "core_product": core_product,
        },
        "benchmark_added": bool(benchmark_name),
        "first_content_id": content_id,
        "next_commands": [
            "python scripts/creatorbuddy.py onboarding-status",
            "python scripts/creatorbuddy.py today",
            f"python scripts/creatorbuddy.py draft --platform {platform}",
        ],
    }
    update_onboarding(config, workspace)
    save_config(workspace, config)
    status_payload["onboarding"] = {
        "current_step": config.get("onboarding", {}).get("current_step"),
        "steps": config.get("onboarding", {}).get("steps", []),
    }
    print(json.dumps(status_payload, ensure_ascii=False, indent=2))
    return 0


def keyword_hits(text: str, keywords: list[str]) -> int:
    lowered = text.lower()
    return sum(1 for keyword in keywords if keyword and keyword.lower() in lowered)


def marketing_judgment(
    topic: str,
    platform: str,
    config: dict[str, Any],
    published: list[dict[str, Any]],
    signals: list[dict[str, Any]],
) -> dict[str, Any]:
    platform_cfg = find_platform(config, platform) or {}
    target_audience = platform_cfg.get("target_audience") or "待补充信息"
    positioning = platform_cfg.get("positioning") or "待补充信息"
    topic_text = topic.lower()
    product_keywords = [str(item) for item in config.get("product_keywords", [])]
    benchmark_terms = [str(item) for item in platform_cfg.get("benchmark_industries", [])]
    matching_signals = [
        item for item in signals
        if item.get("platform") in (platform, "all")
        and str(item.get("topic") or item.get("title") or "").lower() in topic_text
    ]
    published_on_platform = [item for item in published if item.get("platform") == platform]
    has_conversion_records = any(item.get("conversions") for item in published_on_platform)
    has_metrics = any(item.get("metrics") for item in published_on_platform)

    offer_score = 2 + min(3, keyword_hits(topic_text, product_keywords))
    content_score = 2 + min(3, keyword_hits(topic_text, benchmark_terms) + (1 if matching_signals else 0))
    social_score = 3 + (1 if platform in {"xiaohongshu", "douyin", "wechat-channels"} else 0)
    conversion_score = 2 + min(3, keyword_hits(topic_text, product_keywords) + (1 if positioning != "待补充信息" else 0))
    attribution_score = 1 + (1 if matching_signals else 0) + (1 if has_metrics else 0) + (1 if has_conversion_records else 0)

    dimensions = [
        {
            "name": "offer",
            "score": min(5, offer_score),
            "max_score": 5,
            "reason": "Topic can be tied to a sellable promise when product keywords and proof are present.",
            "missing": [] if product_keywords else ["product_keywords"],
        },
        {
            "name": "content_strategy",
            "score": min(5, content_score),
            "max_score": 5,
            "reason": "Topic should fit one repeatable pillar and one concrete content format.",
            "missing": [] if benchmark_terms or matching_signals else ["benchmark_industries_or_signals"],
        },
        {
            "name": "social",
            "score": min(5, social_score),
            "max_score": 5,
            "reason": "Platform-native packaging must still be handled by the platform skill.",
            "missing": [],
        },
        {
            "name": "conversion",
            "score": min(5, conversion_score),
            "max_score": 5,
            "reason": "Content needs a product bridge and a low-friction next action.",
            "missing": [] if positioning != "待补充信息" else ["platform_positioning"],
        },
        {
            "name": "attribution",
            "score": min(5, attribution_score),
            "max_score": 5,
            "reason": "Every content item should carry source, content id, metrics, and conversion follow-up.",
            "missing": [] if has_metrics or has_conversion_records else ["metrics_or_conversion_records"],
        },
    ]
    score = sum(int(item["score"]) for item in dimensions)
    return {
        "source": "marketingskills_adapted_framework",
        "score": score,
        "max_score": 25,
        "target_audience": target_audience,
        "positioning": positioning,
        "dimensions": dimensions,
        "offer_brief": {
            "audience": target_audience,
            "promise": f"Help the audience make progress on: {topic}",
            "proof_needed": "待补充信息" if not matching_signals else matching_signals[0].get("source_path", "") or matching_signals[0].get("source", ""),
            "next_step": "comment, save, DM, consult, course, or service path must be selected before publishing",
        },
        "content_strategy": {
            "pillar": benchmark_terms[0] if benchmark_terms else "待补充信息",
            "format": "platform-native educational proof piece",
            "single_idea": topic,
        },
        "social_distribution": {
            "platform": platform,
            "hook_requirement": "use the platform skill to adapt hook, title, cover, and CTA",
            "engagement_goal": "save/share/comment/DM, chosen per platform",
        },
        "conversion_path": {
            "cta": "low-friction next action",
            "product_bridge": product_keywords[:5],
            "objection_to_address": "why this is practical today, not just another AI tutorial",
        },
        "attribution_plan": {
            "content_id_required": True,
            "source_tag": platform,
            "review_checkpoints": config.get("review_offsets", ["2h", "24h", "48h", "7d"]),
            "conversion_fields": ["leads", "dm_count", "consultations", "sales", "revenue"],
        },
    }


def score_topic(
    topic: str,
    platform: str,
    config: dict[str, Any],
    active_rules: list[dict[str, Any]],
    published: list[dict[str, Any]],
    signals: list[dict[str, Any]],
) -> dict[str, Any]:
    text = topic.lower()
    product_keywords = [str(x).lower() for x in config.get("product_keywords", [])]
    risk_keywords = [str(x) for x in config.get("risk_keywords", [])]
    platform_cfg = next((item for item in config.get("platforms", []) if item.get("platform") == platform), {})
    industry_keywords = [str(x).lower() for x in platform_cfg.get("benchmark_industries", [])]

    matching_signals = [item for item in signals if item.get("platform") in (platform, "all") and topic.lower() in str(item.get("topic", item.get("title", ""))).lower()]
    trend = min(25, 8 + max([int(item.get("heat", 0) or 0) for item in matching_signals] or [0]))
    account_terms = " ".join(str(row.get("title", "")) + " " + " ".join(row.get("lessons", []) or []) for row in published)
    account_fit = 12 + min(8, sum(1 for kw in industry_keywords if kw and (kw in text or kw in account_terms.lower())) * 2)
    product_fit = 12 + min(8, sum(1 for kw in product_keywords if kw and kw in text) * 2)
    history = 10 + min(5, len(active_rules) + sum(1 for row in published if row.get("lessons")))
    evidence = 5 if not matching_signals else max(5, min(15, max(int(item.get("evidence_score", 5) or 5) for item in matching_signals)))
    cost = 5
    risk = [word for word in risk_keywords if word and word in topic]
    marketing = marketing_judgment(topic, platform, config, published, signals)
    marketing_boost = min(10, int(marketing["score"]) // 3)
    score = min(95, trend + account_fit + product_fit + history + evidence + cost + marketing_boost - len(risk) * 8)
    source = "normalized_public_signal" if matching_signals else "config_seed"
    evidence_level = "B" if matching_signals else "C"
    return {
        "platform": platform,
        "topic": topic,
        "source": source,
        "source_path": matching_signals[0].get("source_path", "") if matching_signals else "",
        "heat": trend,
        "score": score,
        "reasons": [
            f"趋势基础 {trend}/25",
            f"账号/行业匹配 {account_fit}/20",
            f"产品承接 {product_fit}/20",
            f"历史策略 {history}/15",
            f"证据强度 {evidence}/15",
            f"营销判断 {marketing['score']}/25",
        ],
        "evidence_level": evidence_level,
        "risk": risk,
        "marketing_judgment": marketing,
    }


def generate_scores(workspace: Path, topics: list[str] | None = None) -> list[dict[str, Any]]:
    config = load_config(workspace)
    ps = paths(workspace)
    active = read_json(ps["active"], {"active_rules": []}).get("active_rules", [])
    published = read_jsonl(ps["content"])
    signals = read_jsonl(ps["signals"])
    topics = topics or []
    for signal in signals:
        signal_topic = str(signal.get("topic") or signal.get("title") or "").strip()
        if signal_topic and signal_topic not in topics:
            topics.append(signal_topic)
    if not topics:
        for platform in config.get("platforms", []):
            for keyword in platform.get("benchmark_industries", [])[:2]:
                topics.append(f"{keyword}：普通人今天可以直接照做的 3 个任务")
    candidates: list[dict[str, Any]] = []
    for platform in config.get("platforms", []):
        if platform.get("enabled") is False:
            continue
        for topic in topics:
            candidates.append(score_topic(topic, platform.get("platform", "xiaohongshu"), config, active, published, signals))
    candidates.sort(key=lambda item: item["score"], reverse=True)
    write_json(ps["scores"], candidates)
    return candidates


def normalize_signals(workspace: Path) -> list[dict[str, Any]]:
    ps = paths(workspace)
    normalized: list[dict[str, Any]] = []
    for row in read_jsonl(ps["raw_signals"]):
        topic = str(row.get("topic") or row.get("title") or "").strip()
        if not topic:
            continue
        heat = max(0, min(25, int(row.get("heat", row.get("likes", 0)) or 0)))
        normalized.append({
            "signal_id": row.get("signal_id") or f"signal-{len(normalized) + 1}",
            "platform": row.get("platform") or "all",
            "topic": topic,
            "heat": heat,
            "evidence_score": int(row.get("evidence_score", 10) or 10),
            "evidence_level": row.get("evidence_level") or "B",
            "source": row.get("source") or "external_adapter",
            "source_path": row.get("source_path") or "",
            "observed_at": row.get("observed_at") or now_iso(),
        })
    write_jsonl(ps["signals"], normalized)
    return normalized


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")


def command_collect(args: argparse.Namespace) -> int:
    workspace = Path(args.workspace or default_workspace())
    config = load_config(workspace)
    ps = paths(workspace)
    if args.signal_json:
        try:
            payload = json.loads(args.signal_json)
        except json.JSONDecodeError as error:
            raise SystemExit(f"signal JSON 无法解析：{error}") from error
        rows = payload if isinstance(payload, list) else [payload]
        for row in rows:
            if isinstance(row, dict):
                append_jsonl(ps["raw_signals"], row)
    if args.file:
        source = Path(args.file)
        if not source.exists():
            raise SystemExit(f"信号文件不存在：{source}")
        text = source.read_text(encoding="utf-8")
        try:
            payload = json.loads(text)
            rows = payload if isinstance(payload, list) else [payload]
        except json.JSONDecodeError:
            rows = [json.loads(line) for line in text.splitlines() if line.strip()]
        for row in rows:
            if isinstance(row, dict):
                append_jsonl(ps["raw_signals"], row)
    normalized = normalize_signals(workspace)
    print(json.dumps({
        "ok": True,
        "workspace": str(workspace),
        "source": "local_adapter_input" if (args.signal_json or args.file) else "existing_raw_signals",
        "platforms": [item.get("platform") for item in config.get("platforms", []) if item.get("enabled", True)],
        "normalized_count": len(normalized),
        "note": "未提供外部适配器输入时不伪造平台数据；当前评分会明确使用 config_seed。",
    }, ensure_ascii=False, indent=2))
    return 0


def command_today(args: argparse.Namespace) -> int:
    workspace = Path(args.workspace or default_workspace())
    config = require_account(workspace, args.allow_cold_start)
    topics = args.topic or []
    candidates = generate_scores(workspace, topics)
    top = candidates[:5]
    report = paths(workspace)["reports"] / f"{datetime.now().strftime('%Y-%m-%d')}-今日内容机会.md"
    owned_count = len(read_jsonl(paths(workspace)["content"]))
    signal_count = len(read_jsonl(paths(workspace)["signals"]))
    benchmark_count = len(read_jsonl(paths(workspace)["benchmark_samples"]))
    active_rule_count = len(read_json(paths(workspace)["active"], {"active_rules": []}).get("active_rules", []))
    lines = [
        "---",
        "type: 今日内容机会报告",
        "schema_version: 1",
        f"created_at: {now_iso()}",
        "---",
        "",
        "# 今日内容机会",
        "",
        "## 输入状态",
        "",
        f"- 自有内容资产：{owned_count} 条",
        f"- 标准化公开信号：{signal_count} 条",
        f"- 对标样本：{benchmark_count} 条",
        f"- 已确认策略：{active_rule_count} 条",
        f"- 账号目标：{config.get('goal', '待补充信息')}",
        "",
        "## 今日优先推荐",
        "",
    ]
    for idx, item in enumerate(top, start=1):
        marketing = item.get("marketing_judgment", {})
        lines.extend(
            [
                f"## {idx}. {platform_label(item['platform'])}｜{item['topic']}",
                "",
                f"- 推荐分：{item['score']}",
                f"- 证据等级：{item['evidence_level']}",
                f"- 目标用户：{marketing.get('target_audience', '待补充信息')}",
                f"- 理由：{'；'.join(item['reasons'])}",
                f"- 风险：{', '.join(item['risk']) if item['risk'] else '暂无明显风险'}",
                f"- Offer：{marketing.get('offer_brief', {}).get('promise', '待补充信息')}",
                f"- 内容策略：{marketing.get('content_strategy', {}).get('single_idea', item['topic'])}",
                f"- 转化路径：{marketing.get('conversion_path', {}).get('cta', '待补充信息')}",
                f"- 归因计划：content_id + {', '.join(marketing.get('attribution_plan', {}).get('conversion_fields', []))}",
                f"- 下一步：`draft --platform {item['platform']} --topic \"{item['topic']}\"`",
                "",
            ]
        )
    lines.extend(
        [
            "## 证据边界",
            "",
            "- 推荐分用于排序，不代表爆款保证。",
            "- 公开样本不等同于自己的后台数据。",
            "- 缺少评论、私信、成交数据时，不做转化归因。",
            "",
            "## 下一步动作",
            "",
            "1. 选择 1 个推荐选题生成草稿。",
            "2. 执行发布前检查。",
            "3. 发布后用 `add-content` 或 `review` 记录指标、评论和转化。",
        ]
    )
    report.write_text("\n".join(lines), encoding="utf-8")
    append_jsonl(paths(workspace)["runs"], {"run_id": datetime.now().strftime("%Y%m%d%H%M%S"), "created_at": now_iso(), "report": str(report)})
    print(json.dumps({"ok": True, "schema_version": 1, "workspace": str(workspace), "report": str(report), "top": top}, ensure_ascii=False, indent=2))
    return 0


def choose_xiaohongshu_topic_function(topic: str, marketing: dict[str, Any]) -> str:
    lowered = topic.lower()
    if any(word in topic for word in ["怎么", "教程", "步骤", "方法", "清单", "模板"]):
        return "educate"
    if any(word in topic for word in ["避坑", "错误", "卡住", "焦虑", "不会"]):
        return "resonate"
    if any(word in topic for word in ["案例", "复盘", "实操", "结果"]):
        return "trust"
    if any(word in topic for word in ["咨询", "课程", "训练营", "服务", "成交"]) or "course" in lowered:
        return "convert"
    if any(word in topic for word in ["你觉得", "评论", "投票", "选择"]):
        return "interact"
    if marketing.get("conversion_path", {}).get("product_bridge"):
        return "trust"
    return "attract"


def xiaohongshu_playbook_brief(topic: str, config: dict[str, Any], marketing: dict[str, Any]) -> dict[str, Any]:
    playbook = config.get("xiaohongshu_playbook") or DEFAULT_XIAOHONGSHU_PLAYBOOK
    topic_function = choose_xiaohongshu_topic_function(topic, marketing)
    title_mode = "search_conversion" if topic_function in {"educate", "convert"} else "comment_style"
    if topic_function == "trust":
        title_mode = "insight_judgment"
    return {
        "source": "xiaohongshu_playbook_sanitized",
        "workflow": playbook.get("workflow", DEFAULT_XIAOHONGSHU_PLAYBOOK["workflow"]),
        "profile_gate": {
            "check": playbook.get("profile_gate", [])[:3],
            "workspace_fields": ["platforms[].positioning", "platforms[].target_audience", "product_keywords"],
        },
        "topic_planner": {
            "primary_function": topic_function,
            "allowed_functions": playbook.get("topic_functions", DEFAULT_XIAOHONGSHU_PLAYBOOK["topic_functions"]),
            "series_rule": "publish trust and education before heavy conversion when the account is cold-starting",
        },
        "title_design": {
            "mode": title_mode,
            "requirements": [
                "one concrete scene or user situation",
                "keyword anchor in title or cover",
                "no invented numbers, outcomes, identity stories, or third-party proof",
            ],
            "banned_terms": playbook.get("title_banned_terms", [])[:12],
        },
        "comment_plan": {
            "pinned_comment": "补充一个公开可见的自查问题或下一篇内容，不把评论作为领资料条件。",
            "reply_rules": playbook.get("comment_reply_rules", [])[:3],
        },
        "conversion_path": {
            "steps": playbook.get("conversion_path", DEFAULT_XIAOHONGSHU_PLAYBOOK["conversion_path"]),
            "next_action": marketing.get("conversion_path", {}).get("cta") or "save, comment, follow-up note, trial, consultation, or product page",
        },
        "measurement": {
            "fields": playbook.get("measurement_fields", DEFAULT_XIAOHONGSHU_PLAYBOOK["measurement_fields"]),
            "review_checkpoints": config.get("review_offsets", ["2h", "24h", "48h", "7d"]),
        },
    }


def make_draft(topic: str, platform: str, marketing: dict[str, Any] | None = None, config: dict[str, Any] | None = None) -> dict[str, Any]:
    label = platform_label(platform)
    marketing = marketing or {}
    config = config or {}
    platform_checklist = {
        "xiaohongshu": ["主页承接要清楚", "标题要有搜索词或评论区口吻", "正文要有步骤感", "置顶评论要补价值", "结尾引导收藏或低压行动"],
        "douyin": ["前 3 秒先给冲突", "一条视频只讲一个观点", "口播句子要短"],
        "wechat-mp": ["开头建立问题背景", "中段给案例和推理", "结尾自然承接产品"],
    }.get(platform, ["保留证据来源", "避免夸大承诺", "明确下一步行动"])
    return {
        "platform": platform,
        "platform_label": label,
        "title": topic,
        "opening": f"如果你正在做「{topic}」，先不要追求完整体系，先跑通一个能交付结果的小任务。",
        "structure": [
            "用户现在卡在哪里",
            "给出 3 个可以马上完成的任务",
            "每个任务说明输入、操作和完成标准",
            "用一个低压 CTA 承接下一步",
        ],
        "body": f"选题：{topic}\n\n角度：把抽象方法压缩成普通人今天能照做的任务。\n\n正文骨架：\n1. 先说痛点。\n2. 给 3 个任务。\n3. 展示完成标准。\n4. 收尾引导继续行动。",
        "marketing_brief": {
            "framework_source": marketing.get("source", "marketingskills_adapted_framework"),
            "score": marketing.get("score"),
            "offer": marketing.get("offer_brief", {}),
            "content_strategy": marketing.get("content_strategy", {}),
            "social_distribution": marketing.get("social_distribution", {}),
            "conversion_path": marketing.get("conversion_path", {}),
            "attribution_plan": marketing.get("attribution_plan", {}),
        },
        "xiaohongshu_brief": xiaohongshu_playbook_brief(topic, config, marketing) if platform == "xiaohongshu" else {},
        "checklist": platform_checklist,
        "created_at": now_iso(),
    }


def command_draft(args: argparse.Namespace) -> int:
    workspace = Path(args.workspace or default_workspace())
    config = require_account(workspace)
    candidates = read_json(paths(workspace)["scores"], [])
    topic = args.topic or (candidates[0]["topic"] if candidates else "")
    platform = args.platform or (candidates[0]["platform"] if candidates else "xiaohongshu")
    if not topic:
        raise SystemExit("缺少选题。请传入 --topic，或先运行 today。")
    active_rules = read_json(paths(workspace)["active"], {"active_rules": []}).get("active_rules", [])
    existing_candidate = next((item for item in candidates if item.get("topic") == topic and item.get("platform") == platform), None)
    marketing = existing_candidate.get("marketing_judgment") if existing_candidate else None
    if not marketing:
        marketing = marketing_judgment(topic, platform, config, read_jsonl(paths(workspace)["content"]), read_jsonl(paths(workspace)["signals"]))
    draft = make_draft(topic, platform, marketing, config)
    draft["strategy_context"] = [rule.get("rule") for rule in active_rules if not rule.get("applies_to") or platform in rule.get("applies_to", [])]
    draft["evidence_boundary"] = "推荐分用于排序，不代表爆款保证；请结合实际证据和发布前检查。"
    out = paths(workspace)["drafts"] / f"{datetime.now().strftime('%Y%m%d%H%M%S')}-{platform}.json"
    write_json(out, draft)
    print(json.dumps({"ok": True, "draft_path": str(out), "draft": draft}, ensure_ascii=False, indent=2))
    return 0


def build_precheck_payload(workspace: Path, platform: str, title: str, content: str) -> dict[str, Any]:
    config = load_config(workspace)
    text = f"{title}\n{content}"
    risks = [word for word in config.get("risk_keywords", []) if word and word in text]
    xhs_title_risks = []
    playbook = config.get("xiaohongshu_playbook") or DEFAULT_XIAOHONGSHU_PLAYBOOK
    if platform == "xiaohongshu":
        xhs_title_risks = [word for word in playbook.get("title_banned_terms", []) if word and word in title]
        risks.extend([f"小红书标题空泛词：{word}" for word in xhs_title_risks])
    missing = []
    if not title.strip():
        missing.append("标题为空")
    if not content.strip():
        missing.append("正文/脚本为空")
    if "content_id" not in text and "转化" not in text and "CTA" not in text.upper():
        missing.append("缺少转化或归因说明")
    suggestions = ["保留具体证据", "避免夸大收益", "确认平台表达方式", "补充 CTA、content_id 和发布后归因字段"]
    if platform == "xiaohongshu":
        suggestions.append("小红书标题优先用具体场景、用户处境或搜索问题")
    if platform == "wechat-mp":
        suggestions.append("公众号文章需要确认标题、摘要、封面、正文排版和移动端预览")
    payload = {
        "ok": not risks and not missing,
        "verdict": "可以进入人工发布确认" if not risks and not missing else "小改后发布",
        "risks": risks,
        "missing": missing,
        "suggestions": suggestions,
        "created_at": now_iso(),
    }
    return payload


def write_precheck_report(workspace: Path, platform: str, payload: dict[str, Any]) -> Path:
    report = paths(workspace)["reports"] / f"{datetime.now().strftime('%Y%m%d%H%M%S')}-{platform}-precheck.json"
    write_json(report, payload)
    return report


def command_precheck(args: argparse.Namespace) -> int:
    workspace = Path(args.workspace or default_workspace())
    title = args.title or ""
    content = args.content or ""
    if args.file:
        content = Path(args.file).read_text(encoding="utf-8")
    payload = build_precheck_payload(workspace, args.platform, title, content)
    report = write_precheck_report(workspace, args.platform, payload)
    payload["report"] = str(report)
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


def resolve_wechat_publisher_dir() -> Path | None:
    candidates = []
    env_dir = os.environ.get("CREATORBUDDY_WECHAT_PUBLISHER_DIR") or os.environ.get("WECHAT_PUBLISHER_DIR")
    if env_dir:
        candidates.append(Path(env_dir))
    candidates.extend([
        SKILL_DIR.parent / "wechat-publisher",
        Path.home() / ".codex" / "skills" / "wechat-publisher",
        Path("D:/Download/codex/.codex/skills/wechat-publisher"),
    ])
    for candidate in candidates:
        if (candidate / "scripts" / "publish.ts").exists():
            return candidate
    return None


def split_paragraphs(content: str) -> list[str]:
    parts = [part.strip() for part in re.split(r"\n\s*\n", content.strip()) if part.strip()]
    if parts:
        return parts
    return [line.strip() for line in content.splitlines() if line.strip()]


def render_wechat_preview_document(title: str, article: str) -> str:
    safe_title = html.escape(title)
    return f"""<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8" />
<meta name="viewport" content="width=device-width, initial-scale=1.0" />
<title>{safe_title}</title>
<style>
* {{ margin:0; padding:0; box-sizing:border-box; }}
body {{ background:#f0f0f0; display:flex; justify-content:center; padding:20px; font-family:-apple-system,BlinkMacSystemFont,'PingFang SC','Microsoft YaHei',sans-serif; }}
.phone-frame {{ width:375px; background:#fff; border-radius:24px; box-shadow:0 8px 40px rgba(0,0,0,.12); overflow:hidden; }}
.phone-header {{ height:44px; display:flex; align-items:center; justify-content:center; font-size:12px; color:#999; border-bottom:1px solid #f0f0f0; }}
.copy-bar {{ position:sticky; bottom:0; background:#fff; border-top:1px solid #eee; padding:12px 16px; display:flex; gap:8px; }}
.copy-bar button {{ flex:1; padding:10px; border:none; border-radius:8px; font-size:13px; font-weight:600; cursor:pointer; }}
.btn-copy {{ background:#1d1d1f; color:#fff; }}
.btn-top {{ background:#f5f5f7; color:#1d1d1f; }}
</style>
</head>
<body>
<div class="phone-frame">
  <div class="phone-header">公众号文章预览</div>
  <div id="article-content">
<!-- ARTICLE HTML START -->
{article}
<!-- ARTICLE HTML END -->
  </div>
  <div class="copy-bar">
    <button class="btn-copy" onclick="copyArticle()">复制带样式 HTML</button>
    <button class="btn-top" onclick="window.scrollTo({{top:0,behavior:'smooth'}})">回到顶部</button>
  </div>
</div>
<script>
function copyArticle() {{
  const html = document.getElementById('article-content').innerHTML;
  navigator.clipboard.write([new ClipboardItem({{
    'text/html': new Blob([html], {{type: 'text/html'}}),
    'text/plain': new Blob([html], {{type: 'text/plain'}})
  }})]).then(() => {{
    const b = document.querySelector('.btn-copy');
    b.textContent = '已复制';
    setTimeout(() => b.textContent = '复制带样式 HTML', 2000);
  }});
}}
</script>
</body>
</html>
"""


def render_wechat_article_html(title: str, content: str, author: str = "", digest: str = "", layout: str = "simple") -> str:
    safe_title = html.escape(title)
    safe_author = html.escape(author or "CreatorBuddy")
    safe_digest = html.escape(digest or "由 CreatorBuddy 生成的公众号发布预览，请在后台预览后再发布。")
    paragraphs = split_paragraphs(content)
    if not paragraphs:
        paragraphs = ["待补充正文。"]

    if layout == "component":
        return render_wechat_preview_document(title, render_wechat_component_article(title, paragraphs, safe_author, safe_digest))

    body_blocks = []
    for index, paragraph in enumerate(paragraphs, start=1):
        escaped = html.escape(paragraph).replace("\n", "<br />")
        if re.match(r"^(#{1,3}\s+|[一二三四五六七八九十]+[、.．]|[0-9]+[、.．])", paragraph):
            heading = re.sub(r"^#{1,3}\s+", "", paragraph)
            safe_heading = html.escape(heading)
            body_blocks.append(
                f'<section style="display:flex;align-items:center;gap:10px;margin:22px 0 10px;">'
                f'<span style="display:inline-flex;align-items:center;justify-content:center;width:26px;height:26px;border-radius:50%;background:#1f3d35;color:#fff;font-size:13px;font-weight:800;">{index}</span>'
                f'<p style="margin:0;font-size:16px;line-height:1.55;color:#1d1d1f;font-weight:700;">{safe_heading}</p>'
                f'</section>'
            )
        else:
            body_blocks.append(f'<p style="margin:12px 0;font-size:15px;line-height:1.85;color:#242624;">{escaped}</p>')

    article = f"""
<section style="margin:0 auto;padding:24px 20px 32px;max-width:677px;background:#fff;color:#1d1d1f;font-family:-apple-system,BlinkMacSystemFont,'PingFang SC','Microsoft YaHei',sans-serif;font-size:15px;line-height:1.8;letter-spacing:0;">
  <section style="margin:0 0 22px;padding:28px 20px;border-radius:14px;background:#14241f;text-align:center;">
    <p style="margin:0 0 8px;font-size:11px;line-height:1.6;color:rgba(255,255,255,0.42);font-weight:600;letter-spacing:3px;">CREATORBUDDY · 公众号</p>
    <p style="margin:0 0 10px;font-size:21px;line-height:1.38;color:#fff;font-weight:800;">{safe_title}</p>
    <p style="margin:0;font-size:13px;line-height:1.7;color:rgba(255,255,255,0.62);">{safe_digest}</p>
  </section>
  <h1 style="display:none;">{safe_title}</h1>
  <p style="margin:0 0 18px;font-size:13px;line-height:1.7;color:#7a7d78;">作者：{safe_author}</p>
  {''.join(body_blocks)}
  <section style="margin:26px 0 0;padding:18px;border-radius:10px;background:#f4f7f5;border:1px solid #e2ebe6;">
    <p style="margin:0 0 8px;font-size:16px;line-height:1.5;color:#1f3d35;font-weight:750;">发布前确认</p>
    <p style="margin:8px 0 0;font-size:14px;line-height:1.75;color:#4f5b55;">请在公众号后台预览标题、封面、摘要、图片和移动端换行后再发布。CreatorBuddy 只负责生成发布物料，不替代最终人工确认。</p>
  </section>
</section>
""".strip()

    return render_wechat_preview_document(title, article)


def render_wechat_component_article(title: str, paragraphs: list[str], safe_author: str, safe_digest: str) -> str:
    safe_title = html.escape(title)
    intro = html.escape(paragraphs[0])
    rest = paragraphs[1:] or ["先把问题拆成一个今天能执行的小任务，再用内容承接产品路径。"]
    sections = []
    step_words = ["第一", "第二", "第三"]
    step_items = rest[:3]
    for index, paragraph in enumerate(rest, start=1):
        safe = html.escape(re.sub(r"^#{1,3}\s+", "", paragraph)).replace("\n", "<br />")
        if index <= 3:
            sections.append(
                f'<section style="margin:48px 0 24px;padding:0 20px;display:flex;align-items:center;">'
                f'<div style="text-align:center;flex:0 0 auto;margin-right:14px;"><p style="margin:0;font-size:28px;font-weight:900;line-height:1;color:#059669;">{index:02d}</p><p style="margin:2px 0 0;font-size:10px;font-weight:700;letter-spacing:2px;color:#9CA3AF;">PART</p></div>'
                f'<div style="width:1px;height:36px;background:#E5E7EB;flex:0 0 auto;margin-right:14px;"></div>'
                f'<div><p style="margin:0;font-size:17px;font-weight:900;color:#111827;">{safe[:48]}</p><p style="margin:2px 0 0;font-size:11px;color:#9CA3AF;">CreatorBuddy 发布检查</p></div>'
                f'</section>'
            )
        sections.append(f'<p style="margin:0 20px 20px;font-size:14px;line-height:1.85;letter-spacing:0.5px;color:#374151;text-align:justify;">{safe}</p>')
        if index == 1:
            sections.append(
                '<section style="margin:0 20px 24px;padding:14px 16px;border-radius:10px;background:#ECFDF5;border-left:3px solid #059669;">'
                '<p style="margin:0;font-size:14px;line-height:1.8;color:#065F46;"><strong>提示</strong> — 这篇文章已进入发布适配器，请在公众号后台确认标题、摘要、封面和移动端换行。</p>'
                '</section>'
            )

    step_cards = []
    for idx, item in enumerate(step_items[:3]):
        safe_item = html.escape(re.sub(r"^#{1,3}\s+", "", item))
        step_cards.append(
            f'<section style="margin:8px 20px;padding:10px 14px;border-radius:8px;background:#f9fafb;border:1px solid #e5e7eb;">'
            f'<p style="margin:0;font-size:15px;line-height:1.8;color:#1d1d1f;"><span style="color:#059669;font-weight:800;margin-right:6px;">{step_words[idx]}</span>{safe_item}</p>'
            f'</section>'
        )

    return f"""
<section style="max-width:677px;margin:0 auto;background:#ffffff;font-family:-apple-system,BlinkMacSystemFont,'PingFang SC','Hiragino Sans GB','Microsoft YaHei',sans-serif;color:#374151;line-height:1.75;letter-spacing:0.5px;overflow-x:hidden;">
  <section style="margin:0 20px 32px;background:#fff;border:1.5px solid rgba(5,150,105,0.15);border-radius:20px;box-shadow:0 4px 20px rgba(0,0,0,0.06);overflow:hidden;">
    <div style="padding:32px 24px 28px;">
      <p style="margin:0 0 14px;font-size:11px;font-weight:700;letter-spacing:2px;color:#9CA3AF;">CREATORBUDDY · 公众号</p>
      <p style="margin:0;font-size:28px;font-weight:900;line-height:1.12;letter-spacing:-1px;color:#111827;">{safe_title}</p>
      <p style="margin:12px 0 0;font-size:13px;line-height:1.7;color:#6B7280;">{safe_digest}</p>
    </div>
    <div style="height:6px;background:linear-gradient(90deg,#059669,#10B981);"></div>
  </section>
  <h1 style="display:none;">{safe_title}</h1>
  <p style="margin:0 20px 20px;font-size:12px;line-height:1.7;color:#9CA3AF;">作者：{safe_author}</p>
  <p style="margin:0 20px 20px;font-size:14px;line-height:1.85;letter-spacing:0.5px;color:#374151;text-align:justify;">{intro}</p>
  <section style="margin:0 20px 24px;padding:14px 16px;border-radius:10px;background:#ECFDF5;border-left:3px solid #059669;">
    <p style="margin:0;font-size:14px;line-height:1.8;color:#065F46;"><strong>这篇文章解决什么</strong> — 把一个内容机会整理成公众号可阅读、可复制、可复盘的发布版本。</p>
  </section>
  {''.join(step_cards)}
  {''.join(sections)}
  <section style="margin:28px 20px 20px;padding:18px;border-radius:12px;background:#111827;">
    <p style="margin:0 0 8px;font-size:16px;line-height:1.5;color:#fff;font-weight:800;">写在最后</p>
    <p style="margin:8px 0;font-size:15px;line-height:1.8;color:rgba(255,255,255,0.82);">发布不是终点。发出后请回到 CreatorBuddy 记录阅读、点赞、评论、私信和转化，再让复盘进入下一次选题。</p>
  </section>
  <section style="margin:16px 20px 0;">
    <span style="display:inline-block;padding:4px 10px;border-radius:20px;background:#f3f4f6;color:#9ca3af;font-size:11px;margin-right:6px;">#公众号</span>
    <span style="display:inline-block;padding:4px 10px;border-radius:20px;background:#f3f4f6;color:#9ca3af;font-size:11px;margin-right:6px;">#内容增长</span>
    <span style="display:inline-block;padding:4px 10px;border-radius:20px;background:#f3f4f6;color:#9ca3af;font-size:11px;">#CreatorBuddy</span>
  </section>
</section>
""".strip()


def command_wechat_publish(args: argparse.Namespace) -> int:
    workspace = Path(args.workspace or default_workspace())
    load_config(workspace)
    title = args.title.strip()
    content = args.content or ""
    if args.file:
        content = Path(args.file).read_text(encoding="utf-8")
    if args.draft_file:
        draft = read_json(Path(args.draft_file), {})
        title = title or str(draft.get("title") or "")
        content = content or str(draft.get("body") or draft.get("opening") or "")
    if not title:
        raise SystemExit("wechat-publish 需要 --title，或传入包含 title 的 --draft-file。")
    if not content.strip():
        raise SystemExit("wechat-publish 需要 --content / --file，或传入包含 body 的 --draft-file。")
    layout = args.layout or "simple"
    if layout not in {"simple", "component"}:
        raise SystemExit("wechat-publish --layout 仅支持 simple 或 component。")

    precheck = build_precheck_payload(workspace, "wechat-mp", title, content)
    precheck_report = write_precheck_report(workspace, "wechat-mp", precheck)

    out_dir = paths(workspace)["publish"] / "wechat-mp"
    out_dir.mkdir(parents=True, exist_ok=True)
    preview = out_dir / f"{datetime.now().strftime('%Y%m%d%H%M%S')}-{safe_slug(title, 'wechat-article')}.html"
    preview.write_text(render_wechat_article_html(title, content, args.author, args.digest, layout), encoding="utf-8")

    publisher_dir = resolve_wechat_publisher_dir()
    payload: dict[str, Any] = {
        "ok": True,
        "adapter": "wechat-publisher",
        "platform": "wechat-mp",
        "mode": "copy-preview",
        "layout": layout,
        "title": title,
        "preview_path": str(preview),
        "precheck": precheck,
        "precheck_report": str(precheck_report),
        "publisher_dir": str(publisher_dir) if publisher_dir else "",
        "next_action": "打开 preview_path，复制带样式 HTML 到公众号后台；如需一键进草稿箱，配置凭证后使用 --send-draft --cover <封面图>。",
        "created_at": now_iso(),
    }

    if args.send_draft:
        if not publisher_dir:
            payload.update({
                "ok": False,
                "mode": "draft-add",
                "error": "未找到 wechat-publisher skill。请安装 wechat-publisher，或设置 CREATORBUDDY_WECHAT_PUBLISHER_DIR。",
            })
            print(json.dumps(payload, ensure_ascii=False, indent=2))
            return 2
        if not args.cover and not args.gen_cover:
            payload.update({
                "ok": False,
                "mode": "draft-add",
                "error": "一键进草稿箱需要封面：传 --cover <path>，或在配置 OPENAI_API_KEY 后使用 --gen-cover。",
            })
            print(json.dumps(payload, ensure_ascii=False, indent=2))
            return 2
        npx = shutil.which("npx.cmd") or shutil.which("npx")
        if not npx:
            payload.update({"ok": False, "mode": "draft-add", "error": "未找到 npx。请先安装 Node.js。"})
            print(json.dumps(payload, ensure_ascii=False, indent=2))
            return 2
        publish_args = [npx, "tsx", "publish.ts", str(preview), "--title", title]
        if args.author:
            publish_args.extend(["--author", args.author])
        if args.digest:
            publish_args.extend(["--digest", args.digest])
        if args.cover:
            publish_args.extend(["--cover", args.cover])
        if args.gen_cover:
            publish_args.append("--gen-cover")
        if args.no_comment:
            publish_args.append("--no-comment")
        proc = subprocess.run(
            publish_args,
            cwd=publisher_dir / "scripts",
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )
        payload.update({
            "ok": proc.returncode == 0,
            "mode": "draft-add",
            "returncode": proc.returncode,
            "stdout": proc.stdout,
            "stderr": proc.stderr.replace(os.environ.get("WECHAT_APP_SECRET", ""), "***") if os.environ.get("WECHAT_APP_SECRET") else proc.stderr,
        })
        append_jsonl(paths(workspace)["runs"], {"run_id": datetime.now().strftime("%Y%m%d%H%M%S"), "created_at": now_iso(), "adapter": "wechat-publisher", "preview_path": str(preview), "mode": payload["mode"], "layout": layout, "ok": payload["ok"]})
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0 if payload["ok"] else 1

    append_jsonl(paths(workspace)["runs"], {"run_id": datetime.now().strftime("%Y%m%d%H%M%S"), "created_at": now_iso(), "adapter": "wechat-publisher", "preview_path": str(preview), "mode": payload["mode"], "layout": layout, "ok": True})
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


def command_add_content(args: argparse.Namespace) -> int:
    workspace = Path(args.workspace or default_workspace())
    config = load_config(workspace)
    body = args.body or ""
    if args.file:
        body = Path(args.file).read_text(encoding="utf-8")
    title = args.title.strip()
    if not title:
        raise SystemExit("内容标题不能为空。")
    row = {
        "schema_version": 1,
        "content_id": args.content_id or f"{args.platform}-{datetime.now().strftime('%Y%m%d%H%M%S')}",
        "platform": args.platform,
        "status": args.status,
        "topic": args.topic or title,
        "title": title,
        "cover": args.cover or "",
        "body": body,
        "script": args.script or "",
        "proof_assets": split_csv(args.proof_assets),
        "product_bridge": args.product_bridge or "",
        "published_at": args.published_at or "",
        "metrics": parse_json_arg(args.metrics_json, {}),
        "comments": parse_json_arg(args.comments_json, []),
        "conversions": parse_json_arg(args.conversions_json, {}),
        "review": args.review or "",
        "next_change": args.next_change or "",
        "lessons": split_csv(args.lessons),
        "source": args.source or "manual_content_asset",
        "created_at": now_iso(),
        "updated_at": now_iso(),
    }
    append_jsonl(paths(workspace)["content"], row)
    update_onboarding(config, workspace)
    save_config(workspace, config)
    print(json.dumps({"ok": True, "content_id": row["content_id"], "content_path": str(paths(workspace)["content"])}, ensure_ascii=False, indent=2))
    return 0


def command_review(args: argparse.Namespace) -> int:
    workspace = Path(args.workspace or default_workspace())
    metrics: Any = parse_json_arg(args.metrics_json, {})
    row = {
        "content_id": args.content_id or f"{args.platform}-{datetime.now().strftime('%Y%m%d%H%M%S')}",
        "platform": args.platform,
        "title": args.title,
        "published_at": args.published_at or "",
        "local_path": args.local_path or "",
        "metrics": metrics,
        "comments": parse_json_arg(args.comments_json, []),
        "conversions": parse_json_arg(args.conversions_json, {}),
        "lessons": parse_json_arg(args.lessons_json, []),
        "review_status": "pending",
        "created_at": now_iso(),
    }
    append_jsonl(paths(workspace)["content"], row)
    config = load_config(workspace)
    update_onboarding(config, workspace)
    save_config(workspace, config)
    print(json.dumps({"ok": True, "record": row}, ensure_ascii=False, indent=2))
    return 0


def latest_content_by_id(workspace: Path, content_id: str) -> dict[str, Any] | None:
    matches = [row for row in read_jsonl(paths(workspace)["content"]) if row.get("content_id") == content_id]
    return matches[-1] if matches else None


def diagnose_metrics(row: dict[str, Any]) -> tuple[str, list[str], list[str]]:
    metrics = row.get("metrics") if isinstance(row.get("metrics"), dict) else {}
    comments = row.get("comments") if isinstance(row.get("comments"), list) else []
    conversions = row.get("conversions") if isinstance(row.get("conversions"), dict) else {}
    likes = int(metrics.get("likes", 0) or 0)
    saves = int(metrics.get("saves", metrics.get("collects", 0)) or 0)
    views = int(metrics.get("views", metrics.get("reads", metrics.get("plays", 0))) or 0)
    dm_count = int(conversions.get("dm_count", conversions.get("inquiries", 0)) or 0)
    lessons: list[str] = []
    next_actions: list[str] = []
    if views <= 0:
        verdict = "待补充曝光数据"
        lessons.append("复盘前必须补充曝光、阅读或播放数据。")
        next_actions.append("补录 views/reads/plays 后重新复盘。")
    elif likes + saves == 0:
        verdict = "互动弱"
        lessons.append("标题或开头没有形成足够点击和收藏理由。")
        next_actions.append("下一条测试更具体的标题、封面承诺和前 3 行。")
    elif saves >= likes:
        verdict = "收藏价值较强"
        lessons.append("保存型结构有效，后续可以增加清单、步骤、模板类内容。")
        next_actions.append("复用保存型结构，并补充更明确的产品承接。")
    else:
        verdict = "有基础互动"
        lessons.append("内容具备基础互动，下一步需要验证评论和转化。")
        next_actions.append("补充置顶评论和低压 CTA，观察私信或咨询。")
    if comments:
        lessons.append("评论区已有反馈，应提炼用户原话作为下次选题输入。")
    if dm_count > 0:
        lessons.append("该内容产生私信/咨询，应进入转化型策略候选。")
    return verdict, lessons, next_actions


def command_post_review(args: argparse.Namespace) -> int:
    workspace = Path(args.workspace or default_workspace())
    load_config(workspace)
    row = latest_content_by_id(workspace, args.content_id)
    if row is None:
        raise SystemExit(f"未找到 content_id：{args.content_id}")
    verdict, lessons, next_actions = diagnose_metrics(row)
    if args.lesson:
        lessons.extend(split_csv(args.lesson))
    reviewed = {
        **row,
        "status": "reviewed",
        "review": args.review or verdict,
        "review_status": "reviewed",
        "next_change": args.next_change or "；".join(next_actions),
        "lessons": list(dict.fromkeys([*(row.get("lessons") or []), *lessons])),
        "reviewed_at": now_iso(),
        "updated_at": now_iso(),
    }
    append_jsonl(paths(workspace)["content"], reviewed)
    report = paths(workspace)["reports"] / f"{reviewed['content_id']}-post-review.md"
    lines = [
        f"# 发布后复盘｜{reviewed['title']}",
        "",
        f"- content_id: {reviewed['content_id']}",
        f"- platform: {reviewed['platform']}",
        f"- verdict: {verdict}",
        f"- metrics: {json.dumps(reviewed.get('metrics', {}), ensure_ascii=False)}",
        f"- conversions: {json.dumps(reviewed.get('conversions', {}), ensure_ascii=False)}",
        "",
        "## 经验",
        *[f"- {lesson}" for lesson in reviewed["lessons"]],
        "",
        "## 下一次改法",
        reviewed["next_change"] or "待补充信息",
    ]
    report.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps({"ok": True, "content_id": reviewed["content_id"], "report": str(report), "lessons": reviewed["lessons"]}, ensure_ascii=False, indent=2))
    return 0


def parse_published_at(value: str) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).replace(tzinfo=None)
    except ValueError:
        return None


def command_review_due(args: argparse.Namespace) -> int:
    workspace = Path(args.workspace or default_workspace())
    config = load_config(workspace)
    now = datetime.now()
    offsets = {"2h": timedelta(hours=2), "24h": timedelta(hours=24), "48h": timedelta(hours=48), "7d": timedelta(days=7)}
    reminders: list[dict[str, Any]] = []
    for row in read_jsonl(paths(workspace)["content"]):
        published_at = parse_published_at(str(row.get("published_at") or ""))
        if not published_at:
            continue
        for offset in config.get("review_offsets", ["2h", "24h", "48h", "7d"]):
            due_at = published_at + offsets.get(offset, timedelta(0))
            if due_at <= now:
                reminders.append({
                    "content_id": row.get("content_id"),
                    "platform": row.get("platform"),
                    "title": row.get("title"),
                    "checkpoint": offset,
                    "due_at": due_at.isoformat(timespec="seconds"),
                    "status": "pending" if row.get("review_status") != "reviewed" else "reviewed",
                })
    write_jsonl(paths(workspace)["reminders"], reminders)
    report = paths(workspace)["reports"] / f"{date.today().isoformat()}-review-reminders.md"
    lines = ["# 发布复盘提醒", "", f"生成时间：{now_iso()}", ""]
    if not reminders:
        lines.append("暂无到期复盘；缺少有效发布时间的内容会标记为待补充。")
    for item in reminders:
        lines.append(f"- [{item['checkpoint']}] {item.get('platform')}｜{item.get('title')}｜{item.get('content_id')}")
    report.write_text("\n".join(lines) + "\n", encoding="utf-8")
    if getattr(args, "emit", True):
        print(json.dumps({"ok": True, "reminder_count": len(reminders), "report": str(report)}, ensure_ascii=False, indent=2))
    return 0


def command_self_growth(args: argparse.Namespace) -> int:
    workspace = Path(args.workspace or default_workspace())
    config = load_config(workspace)
    scores = read_json(paths(workspace)["scores"], [])
    published = [row for row in read_jsonl(paths(workspace)["content"]) if row.get("lessons")]
    candidates: list[dict[str, Any]] = []
    if scores:
        top = scores[0]
        candidates.append({
            "candidate_id": f"topic-fit-{date.today().isoformat()}",
            "rule": f"下一次生成前优先检查与「{top.get('topic')}」相近的账号/产品匹配角度。",
            "evidence": top.get("source_path") or top.get("source") or "latest_topic_scores.json",
            "applies_to": [top.get("platform")],
            "status": "pending_confirmation",
            "created_at": now_iso(),
        })
    if published:
        last = published[-1]
        lesson = last.get("lessons")
        lesson_text = lesson[0] if isinstance(lesson, list) and lesson else str(lesson)
        candidates.append({
            "candidate_id": f"review-lesson-{last.get('content_id')}",
            "rule": f"生成同平台内容前先读取最近复盘经验：{lesson_text}",
            "evidence": last.get("content_id"),
            "applies_to": [last.get("platform")],
            "status": "pending_confirmation",
            "created_at": now_iso(),
        })
    existing = {row.get("candidate_id") for row in read_jsonl(paths(workspace)["pending"])}
    new_candidates = [row for row in candidates if row.get("candidate_id") not in existing]
    for row in new_candidates:
        append_jsonl(paths(workspace)["pending"], row)
    report = paths(workspace)["reports"] / f"{date.today().isoformat()}-self-growth.md"
    lines = ["# Agent 自成长候选", "", f"生成时间：{now_iso()}", ""]
    lines.extend(f"- `{row['candidate_id']}`：{row['rule']}" for row in new_candidates)
    if not new_candidates:
        lines.append("暂无新的策略候选；需要先有评分结果或带 lessons 的复盘记录。")
    lines.append("\n策略候选必须经用户确认后，才能进入 active_strategy。")
    report.write_text("\n".join(lines) + "\n", encoding="utf-8")
    if getattr(args, "emit", True):
        print(json.dumps({"ok": True, "candidate_count": len(new_candidates), "report": str(report), "candidates": new_candidates}, ensure_ascii=False, indent=2))
    return 0


def command_approve_strategy(args: argparse.Namespace) -> int:
    workspace = Path(args.workspace or default_workspace())
    pending = read_jsonl(paths(workspace)["pending"])
    match = next((row for row in pending if row.get("candidate_id") == args.candidate_id), None)
    if not match:
        raise SystemExit(f"未找到策略候选：{args.candidate_id}")
    active = read_json(paths(workspace)["active"], {"schema_version": 1, "active_rules": []})
    rule = {
        "rule_id": match["candidate_id"],
        "status": "active",
        "rule": match.get("rule"),
        "evidence": match.get("evidence"),
        "applies_to": match.get("applies_to", []),
        "approved_at": now_iso(),
    }
    if not any(item.get("rule_id") == rule["rule_id"] for item in active.setdefault("active_rules", [])):
        active["active_rules"].append(rule)
    active["updated_at"] = now_iso()
    write_json(paths(workspace)["active"], active)
    print(json.dumps({"ok": True, "approved": rule, "active_strategy": str(paths(workspace)["active"])}, ensure_ascii=False, indent=2))
    return 0


def command_install_scheduler(args: argparse.Namespace) -> int:
    workspace = Path(args.workspace or default_workspace()).expanduser().resolve()
    load_config(workspace)
    runner = workspace / "config" / "run_creatorbuddy_daily.ps1"
    script_path = Path(__file__).resolve()
    runner.write_text(
        "$ErrorActionPreference = \"Stop\"\n"
        "$env:PYTHONIOENCODING = \"utf-8\"\n"
        f"python \"{script_path}\" --workspace \"{workspace}\" daily-run\n",
        encoding="utf-8",
    )
    result: dict[str, Any] = {"ok": True, "runner": str(runner), "registered": False}
    if args.register:
        task = "CreatorBuddy Agent Daily Run"
        proc = subprocess.run(
            ["schtasks", "/Create", "/TN", task, "/SC", "DAILY", "/ST", args.time, "/TR", f'powershell -NoProfile -ExecutionPolicy Bypass -File "{runner}"', "/F"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )
        result.update({"registered": proc.returncode == 0, "stdout": proc.stdout, "stderr": proc.stderr})
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["registered"] or not args.register else 1


def command_daily_run(args: argparse.Namespace) -> int:
    workspace = Path(args.workspace or default_workspace())
    config = require_account(workspace)
    collect = normalize_signals(workspace)
    candidates = generate_scores(workspace)
    review_args = argparse.Namespace(workspace=str(workspace), emit=False)
    command_review_due(review_args)
    growth_args = argparse.Namespace(workspace=str(workspace), emit=False)
    command_self_growth(growth_args)
    payload = {
        "ok": True,
        "run_id": datetime.now().strftime("%Y%m%d%H%M%S"),
        "created_at": now_iso(),
        "workflow": ["collect", "read_owned_data", "score_topics", "review_due", "self_growth"],
        "normalized_signal_count": len(collect),
        "candidate_count": len(candidates),
        "top": candidates[0] if candidates else None,
        "active_strategy_count": len(read_json(paths(workspace)["active"], {}).get("active_rules", [])),
        "note": "无外部适配器输入时，趋势部分保持 config_seed，不伪造平台数据。",
    }
    append_jsonl(paths(workspace)["runs"], payload)
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


def command_doctor(args: argparse.Namespace) -> int:
    workspace = Path(args.workspace or default_workspace())
    ps = paths(workspace)
    node_path = os.environ.get("NODE_EXE") or shutil.which("node")
    payload = {
        "ok": True,
        "workspace": str(workspace),
        "initialized": ps["config"].exists(),
        "config": str(ps["config"]),
        "scores": ps["scores"].exists(),
        "web_assets": WEB_ASSET_DIR.exists(),
        "node_available": node_path is not None,
        "node_path": node_path or "",
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


def command_serve(args: argparse.Namespace) -> int:
    workspace = Path(args.workspace or default_workspace())
    node_path = os.environ.get("NODE_EXE") or shutil.which("node")
    if not node_path:
        print("Node.js 未找到。CLI 功能仍可使用；如需网页工作台，请安装 Node.js 或设置 NODE_EXE。", file=sys.stderr)
        return 2
    target = workspace / "web"
    if args.refresh_web or not (target / "server.js").exists():
        if target.exists():
            shutil.rmtree(target)
        shutil.copytree(WEB_ASSET_DIR, target)
    env = os.environ.copy()
    env["CREATORBUDDY_VAULT"] = str(workspace)
    env["CREATORBUDDY_CLI"] = str(Path(__file__).resolve())
    env["PORT"] = str(args.port)
    print(f"CreatorBuddy web starting: http://localhost:{args.port}")
    return subprocess.call([node_path, "server.js"], cwd=target, env=env)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="CreatorBuddy Codex skill CLI")
    parser.add_argument("--workspace", default="", help="CreatorBuddy workspace path")
    sub = parser.add_subparsers(dest="command", required=True)

    init = sub.add_parser("init", help="initialize a user's local CreatorBuddy workspace")
    init.add_argument("--workspace-id", default="")
    init.add_argument("--owner", default="")
    init.add_argument("--force", action="store_true")
    init.set_defaults(func=command_init)

    quickstart = sub.add_parser("quickstart", help="交互式完成新用户首用配置，并写入账号、对标和第一条内容资产")
    quickstart.add_argument("--workspace-id", default="")
    quickstart.add_argument("--owner", default="")
    quickstart.add_argument("--platform", default="xiaohongshu")
    quickstart.add_argument("--account-id", default="")
    quickstart.add_argument("--account-name", default="")
    quickstart.add_argument("--positioning", default="")
    quickstart.add_argument("--target-audience", default="")
    quickstart.add_argument("--content-directions", default="")
    quickstart.add_argument("--commercial-goal", default="")
    quickstart.add_argument("--core-product", default="")
    quickstart.add_argument("--keywords", default="")
    quickstart.add_argument("--benchmark-name", default="")
    quickstart.add_argument("--benchmark-id", default="")
    quickstart.add_argument("--benchmark-url", default="")
    quickstart.add_argument("--first-title", default="")
    quickstart.add_argument("--first-topic", default="")
    quickstart.add_argument("--first-body", default="")
    quickstart.add_argument("--first-content-id", default="")
    quickstart.add_argument("--first-published-at", default="")
    quickstart.add_argument("--first-metrics-json", default="")
    quickstart.add_argument("--non-interactive", action="store_true", help="用于测试或脚本模式；缺少必要字段时直接失败")
    quickstart.set_defaults(func=command_quickstart)

    account = sub.add_parser("set-account", help="连接或更新一个自有平台账号")
    account.add_argument("--platform", required=True)
    account.add_argument("--account-id", required=True)
    account.add_argument("--account-name", required=True)
    account.set_defaults(func=command_set_account)

    profile = sub.add_parser("set-profile", help="更新平台账号画像：定位、用户、内容方向、商业目标和核心产品")
    profile.add_argument("--platform", required=True)
    profile.add_argument("--positioning", default="")
    profile.add_argument("--target-audience", default="")
    profile.add_argument("--content-directions", default="")
    profile.add_argument("--commercial-goal", default="")
    profile.add_argument("--core-product", default="")
    profile.add_argument("--keywords", default="")
    profile.set_defaults(func=command_set_profile)

    benchmark = sub.add_parser("add-benchmark", help="添加或更新一个对标账号")
    benchmark.add_argument("--platform", required=True)
    benchmark.add_argument("--account-id", required=True)
    benchmark.add_argument("--account-name", required=True)
    benchmark.add_argument("--url", default="")
    benchmark.set_defaults(func=command_add_benchmark)

    onboarding = sub.add_parser("onboarding-status", help="检查工作台是否完成首用流程")
    onboarding.set_defaults(func=command_onboarding_status)

    audit = sub.add_parser("workflow-audit", help="审计 9 项正式版闭环要求的当前 workspace 证据")
    audit.set_defaults(func=command_workflow_audit)

    collect = sub.add_parser("collect", help="接收外部适配器信号并标准化，不伪造平台数据")
    collect.add_argument("--signal-json", default="")
    collect.add_argument("--file", default="")
    collect.set_defaults(func=command_collect)

    importer = sub.add_parser("import-benchmark", help="导入对标账号公开样本，第一期支持小红书主页")
    importer.add_argument("--platform", required=True)
    importer.add_argument("--url", default="")
    importer.add_argument("--html-file", default="", help="For tests or manually saved Xiaohongshu profile HTML")
    importer.add_argument("--benchmark-id", default="")
    importer.add_argument("--name", default="")
    importer.add_argument("--download-covers", action="store_true")
    importer.add_argument("--cover-limit", type=int, default=30)
    importer.set_defaults(func=command_import_benchmark)

    segment = sub.add_parser("segment-benchmark", help="按可见指标分层对标样本")
    segment.add_argument("--platform", default="xiaohongshu")
    segment.add_argument("--benchmark-id", required=True)
    segment.set_defaults(func=command_segment_benchmark)

    distill = sub.add_parser("distill-creator", help="从对标样本生成 creator_clone.md")
    distill.add_argument("--platform", default="xiaohongshu")
    distill.add_argument("--benchmark-id", required=True)
    distill.set_defaults(func=command_distill_creator)

    daily = sub.add_parser("daily-run", help="严格执行采集、读取、评分、复盘提醒和自成长")
    daily.set_defaults(func=command_daily_run)

    today = sub.add_parser("today", help="generate today's content opportunities")
    today.add_argument("--topic", action="append", default=[])
    today.add_argument("--allow-cold-start", action="store_true", help="仅用于没有账号时测试配置种子，不代表真实数据")
    today.set_defaults(func=command_today)

    draft = sub.add_parser("draft", help="create a content draft brief")
    draft.add_argument("--topic", default="")
    draft.add_argument("--platform", default="")
    draft.set_defaults(func=command_draft)

    precheck = sub.add_parser("precheck", help="run a lightweight pre-publish check")
    precheck.add_argument("--platform", default="xiaohongshu")
    precheck.add_argument("--title", default="")
    precheck.add_argument("--content", default="")
    precheck.add_argument("--file", default="")
    precheck.set_defaults(func=command_precheck)

    wechat_publish = sub.add_parser("wechat-publish", help="调用 wechat-publisher 适配器生成公众号复制预览，可选一键写入草稿箱")
    wechat_publish.add_argument("--title", default="")
    wechat_publish.add_argument("--content", default="")
    wechat_publish.add_argument("--file", default="")
    wechat_publish.add_argument("--draft-file", default="")
    wechat_publish.add_argument("--author", default="")
    wechat_publish.add_argument("--digest", default="")
    wechat_publish.add_argument("--layout", default="simple", choices=["simple", "component"], help="公众号预览排版：simple 稳定简版；component 使用组件化精排版")
    wechat_publish.add_argument("--cover", default="")
    wechat_publish.add_argument("--gen-cover", action="store_true")
    wechat_publish.add_argument("--send-draft", action="store_true", help="需要已配置公众号凭证和封面，调用 wechat-publisher 写入草稿箱")
    wechat_publish.add_argument("--no-comment", action="store_true")
    wechat_publish.set_defaults(func=command_wechat_publish)

    content = sub.add_parser("add-content", help="写入一条内容资产，可用于草稿、已发布内容和复盘沉淀")
    content.add_argument("--platform", required=True)
    content.add_argument("--title", required=True)
    content.add_argument("--status", default="published", choices=["idea", "draft", "scheduled", "published", "reviewed"])
    content.add_argument("--topic", default="")
    content.add_argument("--cover", default="")
    content.add_argument("--body", default="")
    content.add_argument("--script", default="")
    content.add_argument("--file", default="")
    content.add_argument("--proof-assets", default="")
    content.add_argument("--product-bridge", default="")
    content.add_argument("--published-at", default="")
    content.add_argument("--metrics-json", default="")
    content.add_argument("--content-id", default="")
    content.add_argument("--comments-json", default="")
    content.add_argument("--conversions-json", default="")
    content.add_argument("--review", default="")
    content.add_argument("--next-change", default="")
    content.add_argument("--lessons", default="")
    content.add_argument("--source", default="")
    content.set_defaults(func=command_add_content)

    review = sub.add_parser("review", help="record a published content item for later review")
    review.add_argument("--platform", required=True)
    review.add_argument("--title", required=True)
    review.add_argument("--published-at", default="")
    review.add_argument("--metrics-json", default="")
    review.add_argument("--content-id", default="")
    review.add_argument("--local-path", default="")
    review.add_argument("--comments-json", default="")
    review.add_argument("--conversions-json", default="")
    review.add_argument("--lessons-json", default="")
    review.set_defaults(func=command_review)

    post_review = sub.add_parser("post-review", help="按 content_id 生成发布后复盘并写回经验")
    post_review.add_argument("--content-id", required=True)
    post_review.add_argument("--review", default="")
    post_review.add_argument("--next-change", default="")
    post_review.add_argument("--lesson", default="")
    post_review.set_defaults(func=command_post_review)

    due = sub.add_parser("review-due", help="生成 2h/24h/48h/7d 到期复盘提醒")
    due.set_defaults(func=command_review_due)

    growth = sub.add_parser("self-growth", help="从评分和复盘生成待确认策略候选")
    growth.set_defaults(func=command_self_growth)

    approve = sub.add_parser("approve-strategy", help="确认一个策略候选并写入策略库")
    approve.add_argument("--candidate-id", required=True)
    approve.set_defaults(func=command_approve_strategy)

    scheduler = sub.add_parser("install-scheduler", help="生成并可选注册 Windows 每日任务")
    scheduler.add_argument("--time", default="09:30")
    scheduler.add_argument("--register", action="store_true")
    scheduler.set_defaults(func=command_install_scheduler)

    doctor = sub.add_parser("doctor", help="check local setup")
    doctor.set_defaults(func=command_doctor)

    serve = sub.add_parser("serve", help="start optional local CreatorBuddy web workbench")
    serve.add_argument("--port", type=int, default=5174)
    serve.add_argument("--refresh-web", action="store_true")
    serve.set_defaults(func=command_serve)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
