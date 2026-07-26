from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any


SKILL_DIR = Path(__file__).resolve().parents[1]
TEMPLATE_CONFIG = SKILL_DIR / "templates" / "agent_config.json"
WEB_ASSET_DIR = SKILL_DIR / "assets" / "web"


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
        "scores": data / "latest_topic_scores.json",
        "pending": data / "pending_strategy_candidates.jsonl",
        "active": data / "active_strategy.json",
        "runs": data / "run_log.jsonl",
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
    return config


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


def score_topic(topic: str, platform: str, config: dict[str, Any], active_rules: list[dict[str, Any]]) -> dict[str, Any]:
    text = topic.lower()
    product_keywords = [str(x).lower() for x in config.get("product_keywords", [])]
    risk_keywords = [str(x) for x in config.get("risk_keywords", [])]
    platform_cfg = next((item for item in config.get("platforms", []) if item.get("platform") == platform), {})
    industry_keywords = [str(x).lower() for x in platform_cfg.get("benchmark_industries", [])]

    trend = 20
    account_fit = 16 + min(4, sum(1 for kw in industry_keywords if kw and kw in text) * 2)
    product_fit = 12 + min(8, sum(1 for kw in product_keywords if kw and kw in text) * 2)
    history = 12 + min(3, len(active_rules))
    evidence = 10
    cost = 5
    risk = [word for word in risk_keywords if word and word in topic]
    score = min(95, trend + account_fit + product_fit + history + evidence + cost - len(risk) * 8)
    return {
        "platform": platform,
        "topic": topic,
        "source": "manual_or_config_seed",
        "source_path": "",
        "heat": trend,
        "score": score,
        "reasons": [
            f"趋势基础 {trend}/25",
            f"账号/行业匹配 {account_fit}/20",
            f"产品承接 {product_fit}/20",
            f"历史策略 {history}/15",
            f"证据强度 {evidence}/15",
        ],
        "evidence_level": "C",
        "risk": risk,
    }


def generate_scores(workspace: Path, topics: list[str] | None = None) -> list[dict[str, Any]]:
    config = load_config(workspace)
    ps = paths(workspace)
    active = read_json(ps["active"], {"active_rules": []}).get("active_rules", [])
    topics = topics or []
    if not topics:
        for platform in config.get("platforms", []):
            for keyword in platform.get("benchmark_industries", [])[:2]:
                topics.append(f"{keyword}：普通人今天可以直接照做的 3 个任务")
    candidates: list[dict[str, Any]] = []
    for platform in config.get("platforms", []):
        if platform.get("enabled") is False:
            continue
        for topic in topics:
            candidates.append(score_topic(topic, platform.get("platform", "xiaohongshu"), config, active))
    candidates.sort(key=lambda item: item["score"], reverse=True)
    write_json(ps["scores"], candidates)
    return candidates


def command_today(args: argparse.Namespace) -> int:
    workspace = Path(args.workspace or default_workspace())
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
                "",
            ]
        )
    report.write_text("\n".join(lines), encoding="utf-8")
    append_jsonl(paths(workspace)["runs"], {"run_id": datetime.now().strftime("%Y%m%d%H%M%S"), "created_at": now_iso(), "report": str(report)})
    print(json.dumps({"ok": True, "workspace": str(workspace), "report": str(report), "top": top}, ensure_ascii=False, indent=2))
    return 0


def make_draft(topic: str, platform: str) -> dict[str, Any]:
    label = platform_label(platform)
    platform_checklist = {
        "xiaohongshu": ["标题要有搜索词", "正文要有步骤感", "结尾引导收藏或评论"],
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
        "checklist": platform_checklist,
        "created_at": now_iso(),
    }


def command_draft(args: argparse.Namespace) -> int:
    workspace = Path(args.workspace or default_workspace())
    candidates = read_json(paths(workspace)["scores"], [])
    topic = args.topic or (candidates[0]["topic"] if candidates else "")
    platform = args.platform or (candidates[0]["platform"] if candidates else "xiaohongshu")
    if not topic:
        raise SystemExit("缺少选题。请传入 --topic，或先运行 today。")
    draft = make_draft(topic, platform)
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
    missing = []
    if not title.strip():
        missing.append("标题为空")
    if not content.strip():
        missing.append("正文/脚本为空")
    payload = {
        "ok": not risks and not missing,
        "verdict": "可以进入人工发布确认" if not risks and not missing else "小改后发布",
        "risks": risks,
        "missing": missing,
        "suggestions": ["保留具体证据", "避免夸大收益", "确认平台表达方式"],
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


def command_review(args: argparse.Namespace) -> int:
    workspace = Path(args.workspace or default_workspace())
    metrics: dict[str, Any] = {}
    if args.metrics_json:
        try:
            metrics = json.loads(args.metrics_json)
        except json.JSONDecodeError:
            metrics = {"raw_metrics_text": args.metrics_json}
    row = {
        "content_id": args.content_id or f"{args.platform}-{datetime.now().strftime('%Y%m%d%H%M%S')}",
        "platform": args.platform,
        "title": args.title,
        "published_at": args.published_at or "",
        "metrics": metrics,
        "review_status": "pending",
        "created_at": now_iso(),
    }
    append_jsonl(paths(workspace)["content"], row)
    print(json.dumps({"ok": True, "record": row}, ensure_ascii=False, indent=2))
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

    today = sub.add_parser("today", help="generate today's content opportunities")
    today.add_argument("--topic", action="append", default=[])
    today.set_defaults(func=command_today)

    draft = sub.add_parser("draft", help="create a content draft brief")
    draft.add_argument("--topic", default="")
    draft.add_argument("--platform", default="")
    draft.set_defaults(func=command_draft)

    precheck = sub.add_parser("precheck", help="run a lightweight pre-publish check")
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
    review.set_defaults(func=command_review)

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
