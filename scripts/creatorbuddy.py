from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any


SKILL_DIR = Path(__file__).resolve().parents[1]
TEMPLATE_CONFIG = SKILL_DIR / "templates" / "agent_config.json"
WEB_ASSET_DIR = SKILL_DIR / "assets" / "web"


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
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
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
        "reports": workspace / "reports",
        "drafts": workspace / "drafts",
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
    benchmarked = any(item.get("benchmark_industries") or item.get("benchmark_accounts") for item in platforms)
    imported = len(read_jsonl(paths(workspace)["content"])) > 0
    grown = bool(read_json(paths(workspace)["scores"], []))
    steps = [connected, benchmarked, imported, grown]
    config.setdefault("onboarding", {})["steps"] = [
        "connect_account", "choose_benchmark", "import_content", "start_growth"
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


def command_onboarding_status(args: argparse.Namespace) -> int:
    workspace = Path(args.workspace or default_workspace())
    config = load_config(workspace)
    update_onboarding(config, workspace)
    save_config(workspace, config)
    platforms = [item for item in config.get("platforms", []) if item.get("enabled", True)]
    connected = [item for item in platforms if item.get("account_id") and item.get("collect_own_account", True)]
    benchmarked = [item for item in platforms if item.get("benchmark_industries") or item.get("benchmark_accounts")]
    published_count = len(read_jsonl(paths(workspace)["content"]))
    scores_ready = bool(read_json(paths(workspace)["scores"], []))
    result = {
        "ok": bool(connected and benchmarked and published_count > 0 and scores_ready),
        "current_step": config["onboarding"]["current_step"],
        "steps": {
            "connect_account": bool(connected),
            "choose_benchmark": bool(benchmarked),
            "import_content": published_count > 0,
            "start_growth": scores_ready,
        },
        "connected_platforms": [item.get("platform") for item in connected],
        "published_content_count": published_count,
        "next_action": {
            "connect_account": "set-account",
            "choose_benchmark": "add-benchmark",
            "import_content": "review",
            "start_growth": "today",
        }.get(config["onboarding"]["current_step"], "today"),
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


def command_init(args: argparse.Namespace) -> int:
    workspace = Path(args.workspace or default_workspace())
    ps = paths(workspace)
    if ps["config"].exists() and not args.force:
        print(json.dumps({"ok": True, "workspace": str(workspace), "message": "already initialized"}, ensure_ascii=False, indent=2))
        return 0

    config = read_json(TEMPLATE_CONFIG, {})
    config["workspace_id"] = args.workspace_id or config.get("workspace_id") or "creatorbuddy-workspace"
    config["owner"] = args.owner or config.get("owner") or ""
    config["updated_at"] = now_iso()
    write_json(ps["config"], config)

    write_json(ps["scores"], [])
    ps["content"].parent.mkdir(parents=True, exist_ok=True)
    ps["content"].write_text("", encoding="utf-8")
    ps["raw_signals"].write_text("", encoding="utf-8")
    ps["signals"].write_text("", encoding="utf-8")
    ps["reminders"].write_text("", encoding="utf-8")
    ps["pending"].write_text("", encoding="utf-8")
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
    print(json.dumps({"ok": True, "workspace": str(workspace), "config": str(ps["config"])}, ensure_ascii=False, indent=2))
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
    require_account(workspace, args.allow_cold_start)
    topics = args.topic or []
    candidates = generate_scores(workspace, topics)
    top = candidates[:5]
    report = paths(workspace)["reports"] / f"{datetime.now().strftime('%Y-%m-%d')}-今日内容机会.md"
    lines = ["# 今日内容机会", "", f"生成时间：{now_iso()}", ""]
    for idx, item in enumerate(top, start=1):
        lines.extend(
            [
                f"## {idx}. {platform_label(item['platform'])}｜{item['topic']}",
                "",
                f"- 推荐分：{item['score']}",
                f"- 证据等级：{item['evidence_level']}",
                f"- 理由：{'；'.join(item['reasons'])}",
                f"- 风险：{', '.join(item['risk']) if item['risk'] else '暂无明显风险'}",
                f"- Offer：{item.get('marketing_judgment', {}).get('offer_brief', {}).get('promise', '待补充信息')}",
                f"- 转化路径：{item.get('marketing_judgment', {}).get('conversion_path', {}).get('cta', '待补充信息')}",
                f"- 归因计划：content_id + {', '.join(item.get('marketing_judgment', {}).get('attribution_plan', {}).get('conversion_fields', []))}",
                "",
            ]
        )
    report.write_text("\n".join(lines), encoding="utf-8")
    append_jsonl(paths(workspace)["runs"], {"run_id": datetime.now().strftime("%Y%m%d%H%M%S"), "created_at": now_iso(), "report": str(report)})
    print(json.dumps({"ok": True, "workspace": str(workspace), "report": str(report), "top": top}, ensure_ascii=False, indent=2))
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


def command_precheck(args: argparse.Namespace) -> int:
    workspace = Path(args.workspace or default_workspace())
    config = load_config(workspace)
    title = args.title or ""
    content = args.content or ""
    if args.file:
        content = Path(args.file).read_text(encoding="utf-8")
    text = f"{title}\n{content}"
    risks = [word for word in config.get("risk_keywords", []) if word and word in text]
    xhs_title_risks = []
    playbook = config.get("xiaohongshu_playbook") or DEFAULT_XIAOHONGSHU_PLAYBOOK
    if args.platform == "xiaohongshu":
        xhs_title_risks = [word for word in playbook.get("title_banned_terms", []) if word and word in title]
        risks.extend([f"小红书标题空泛词：{word}" for word in xhs_title_risks])
    missing = []
    if not title.strip():
        missing.append("标题为空")
    if not content.strip():
        missing.append("正文/脚本为空")
    if "content_id" not in text and "转化" not in text and "CTA" not in text.upper():
        missing.append("缺少转化或归因说明")
    payload = {
        "ok": not risks and not missing,
        "verdict": "可以进入人工发布确认" if not risks and not missing else "小改后发布",
        "risks": risks,
        "missing": missing,
        "suggestions": ["保留具体证据", "避免夸大收益", "确认平台表达方式", "补充 CTA、content_id 和发布后归因字段", "小红书标题优先用具体场景、用户处境或搜索问题"],
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
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

    account = sub.add_parser("set-account", help="连接或更新一个自有平台账号")
    account.add_argument("--platform", required=True)
    account.add_argument("--account-id", required=True)
    account.add_argument("--account-name", required=True)
    account.set_defaults(func=command_set_account)

    benchmark = sub.add_parser("add-benchmark", help="添加或更新一个对标账号")
    benchmark.add_argument("--platform", required=True)
    benchmark.add_argument("--account-id", required=True)
    benchmark.add_argument("--account-name", required=True)
    benchmark.add_argument("--url", default="")
    benchmark.set_defaults(func=command_add_benchmark)

    onboarding = sub.add_parser("onboarding-status", help="检查工作台是否完成首用流程")
    onboarding.set_defaults(func=command_onboarding_status)

    collect = sub.add_parser("collect", help="接收外部适配器信号并标准化，不伪造平台数据")
    collect.add_argument("--signal-json", default="")
    collect.add_argument("--file", default="")
    collect.set_defaults(func=command_collect)

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
