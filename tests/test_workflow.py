import json
import subprocess
import sys
import tempfile
import unittest
import os
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CLI = ROOT / "scripts" / "creatorbuddy.py"


def run_cli(workspace: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(CLI), "--workspace", str(workspace), *args],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        env={**os.environ, "PYTHONIOENCODING": "utf-8"},
        check=check,
    )


class WorkflowSmokeTest(unittest.TestCase):
    def test_quickstart_writes_first_user_configuration(self):
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            result = json.loads(run_cli(
                workspace,
                "quickstart",
                "--non-interactive",
                "--owner",
                "测试用户",
                "--platform",
                "xiaohongshu",
                "--account-id",
                "own-quick",
                "--account-name",
                "测试小红书号",
                "--positioning",
                "帮助普通人用 AI 做内容",
                "--target-audience",
                "自媒体新手",
                "--content-directions",
                "AI工具教程,案例复盘",
                "--commercial-goal",
                "内容获客",
                "--core-product",
                "AI训练营",
                "--keywords",
                "AI工具教程,AI变现",
                "--benchmark-name",
                "测试对标号",
                "--benchmark-id",
                "bench-quick",
                "--first-title",
                "AI工具教程第一篇",
                "--first-body",
                "正文或脚本",
                "--first-content-id",
                "quick-001",
                "--first-metrics-json",
                "{\"likes\":3,\"saves\":1}",
            ).stdout)
            self.assertTrue(result["ok"])
            config = json.loads((workspace / "config" / "agent_config.json").read_text(encoding="utf-8"))
            platform = next(item for item in config["platforms"] if item["platform"] == "xiaohongshu")
            self.assertEqual(config["owner"], "测试用户")
            self.assertEqual(platform["account_name"], "测试小红书号")
            self.assertEqual(platform["benchmark_accounts"][0]["account_id"], "bench-quick")
            rows = (workspace / "data" / "published_content.jsonl").read_text(encoding="utf-8").splitlines()
            self.assertEqual(len(rows), 1)
            self.assertEqual(json.loads(rows[0])["content_id"], "quick-001")
            status = json.loads(run_cli(workspace, "onboarding-status").stdout)
            self.assertEqual(status["next_action"], "today")

    def test_account_gate_and_cold_start_override(self):
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            run_cli(workspace, "init")
            blocked = run_cli(workspace, "today", check=False)
            self.assertNotEqual(blocked.returncode, 0)
            allowed = run_cli(workspace, "today", "--allow-cold-start")
            self.assertEqual(json.loads(allowed.stdout)["ok"], True)

    def test_daily_run_normalizes_signal_and_writes_outputs(self):
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            run_cli(workspace, "init")
            run_cli(workspace, "set-account", "--platform", "xiaohongshu", "--account-id", "own-1", "--account-name", "测试账号")
            run_cli(
                workspace,
                "set-profile",
                "--platform",
                "xiaohongshu",
                "--positioning",
                "帮助普通人用 AI 做内容",
                "--target-audience",
                "自媒体新手",
                "--content-directions",
                "AI工具教程,案例复盘",
                "--commercial-goal",
                "内容获客",
                "--core-product",
                "AI训练营",
            )
            run_cli(workspace, "add-benchmark", "--platform", "xiaohongshu", "--account-id", "bench-1", "--account-name", "测试对标")
            signal = workspace / "signal.json"
            signal.write_text(json.dumps({"platform": "xiaohongshu", "topic": "AI工具教程", "heat": 22, "source": "test-adapter"}), encoding="utf-8")
            run_cli(workspace, "collect", "--file", str(signal))
            result = json.loads(run_cli(workspace, "daily-run").stdout)
            self.assertEqual(result["normalized_signal_count"], 1)
            self.assertTrue((workspace / "data" / "normalized_signals.jsonl").exists())
            self.assertTrue((workspace / "data" / "review_reminders.jsonl").exists())
            self.assertTrue((workspace / "data" / "run_log.jsonl").exists())
            today = json.loads(run_cli(workspace, "today").stdout)
            report_text = Path(today["report"]).read_text(encoding="utf-8")
            self.assertIn("## 输入状态", report_text)
            self.assertIn("## 今日优先推荐", report_text)
            self.assertIn("## 证据边界", report_text)
            self.assertIn("## 下一步动作", report_text)

    def test_profile_and_content_asset_complete_onboarding_inputs(self):
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            run_cli(workspace, "init")
            run_cli(workspace, "set-account", "--platform", "xiaohongshu", "--account-id", "own-1", "--account-name", "测试账号")
            status = json.loads(run_cli(workspace, "onboarding-status").stdout)
            self.assertEqual(status["current_step"], "configure_profile")

            profile = json.loads(run_cli(
                workspace,
                "set-profile",
                "--platform",
                "xiaohongshu",
                "--positioning",
                "帮助普通人用 AI 做内容",
                "--target-audience",
                "自媒体新手",
                "--content-directions",
                "AI工具教程,案例复盘",
                "--commercial-goal",
                "内容获客",
                "--core-product",
                "AI训练营",
                "--keywords",
                "AI工具教程,普通人AI副业",
            ).stdout)
            self.assertIn("configure_profile", json.loads(run_cli(workspace, "onboarding-status").stdout)["steps"])
            self.assertEqual(profile["next_step"], "choose_benchmark")
            run_cli(workspace, "add-benchmark", "--platform", "xiaohongshu", "--account-id", "bench-1", "--account-name", "测试对标")
            content = json.loads(run_cli(
                workspace,
                "add-content",
                "--platform",
                "xiaohongshu",
                "--title",
                "AI工具教程第一篇",
                "--topic",
                "AI工具教程",
                "--body",
                "正文",
                "--proof-assets",
                "截图,流程",
                "--product-bridge",
                "AI训练营",
                "--metrics-json",
                "{\"likes\": 3}",
                "--lessons",
                "标题要更具体",
            ).stdout)
            self.assertTrue(content["ok"])
            rows = (workspace / "data" / "published_content.jsonl").read_text(encoding="utf-8").splitlines()
            self.assertEqual(len(rows), 1)
            row = json.loads(rows[0])
            self.assertEqual(row["proof_assets"], ["截图", "流程"])
            self.assertEqual(row["lessons"], ["标题要更具体"])

            loose = json.loads(run_cli(
                workspace,
                "add-content",
                "--platform",
                "xiaohongshu",
                "--title",
                "PowerShell JSON 容错",
                "--metrics-json",
                "{views:100,likes:3,saves:6}",
            ).stdout)
            self.assertTrue(loose["ok"])
            loose_row = json.loads((workspace / "data" / "published_content.jsonl").read_text(encoding="utf-8").splitlines()[-1])
            self.assertEqual(loose_row["metrics"]["views"], 100)

    def test_post_review_writes_lessons_for_self_growth(self):
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            run_cli(workspace, "init")
            run_cli(workspace, "set-account", "--platform", "xiaohongshu", "--account-id", "own-1", "--account-name", "测试账号")
            run_cli(workspace, "add-content", "--platform", "xiaohongshu", "--content-id", "xhs-001", "--title", "AI工具教程", "--metrics-json", "{\"views\":100,\"likes\":3,\"saves\":6}")
            reviewed = json.loads(run_cli(workspace, "post-review", "--content-id", "xhs-001").stdout)
            self.assertTrue(Path(reviewed["report"]).exists())
            self.assertTrue(reviewed["lessons"])
            growth = json.loads(run_cli(workspace, "self-growth").stdout)
            self.assertTrue(growth["candidates"])
            self.assertIn("review-lesson-xhs-001", growth["candidates"][0]["candidate_id"])

    def test_strategy_is_read_by_next_draft(self):
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            run_cli(workspace, "init")
            run_cli(workspace, "set-account", "--platform", "xiaohongshu", "--account-id", "own-1", "--account-name", "测试账号")
            run_cli(workspace, "today")
            run_cli(workspace, "self-growth")
            pending = workspace / "data" / "pending_strategy_candidates.jsonl"
            candidate = json.loads(pending.read_text(encoding="utf-8").splitlines()[0])["candidate_id"]
            run_cli(workspace, "approve-strategy", "--candidate-id", candidate)
            draft = json.loads(run_cli(workspace, "draft", "--platform", "xiaohongshu").stdout)["draft"]
            self.assertTrue(draft["strategy_context"])

    def test_marketing_framework_is_in_scores_and_drafts(self):
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            run_cli(workspace, "init")
            run_cli(workspace, "set-account", "--platform", "xiaohongshu", "--account-id", "own-1", "--account-name", "test-account")
            result = json.loads(run_cli(workspace, "today", "--topic", "AI Agent course conversion case").stdout)
            marketing = result["top"][0]["marketing_judgment"]
            self.assertEqual(marketing["source"], "marketingskills_adapted_framework")
            self.assertEqual(len(marketing["dimensions"]), 5)
            self.assertIn("offer_brief", marketing)
            self.assertIn("conversion_path", marketing)
            self.assertIn("attribution_plan", marketing)

            draft = json.loads(run_cli(workspace, "draft", "--platform", "xiaohongshu", "--topic", "AI Agent course conversion case").stdout)["draft"]
            self.assertEqual(draft["marketing_brief"]["framework_source"], "marketingskills_adapted_framework")
            self.assertIn("offer", draft["marketing_brief"])
            self.assertIn("content_strategy", draft["marketing_brief"])
            self.assertIn("social_distribution", draft["marketing_brief"])
            self.assertIn("conversion_path", draft["marketing_brief"])
            self.assertIn("attribution_plan", draft["marketing_brief"])
            self.assertEqual(draft["xiaohongshu_brief"]["source"], "xiaohongshu_playbook_sanitized")
            self.assertIn("profile_gate", draft["xiaohongshu_brief"])
            self.assertIn("topic_planner", draft["xiaohongshu_brief"])
            self.assertIn("title_design", draft["xiaohongshu_brief"])
            self.assertIn("comment_plan", draft["xiaohongshu_brief"])
            self.assertIn("measurement", draft["xiaohongshu_brief"])

    def test_xiaohongshu_precheck_flags_empty_title_cliches(self):
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            run_cli(workspace, "init")
            result = json.loads(run_cli(
                workspace,
                "precheck",
                "--platform",
                "xiaohongshu",
                "--title",
                "AI工具宝藏教程",
                "--content",
                "content_id: xhs-1\n正文包含具体步骤和转化路径。",
            ).stdout)
            self.assertEqual(result["verdict"], "小改后发布")
            self.assertIn("小红书标题空泛词：宝藏", result["risks"])

    def test_wechat_publisher_adapter_generates_copy_preview_without_credentials(self):
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            run_cli(workspace, "init")
            run_cli(workspace, "set-account", "--platform", "wechat-mp", "--account-id", "wx-1", "--account-name", "测试公众号")
            run_cli(
                workspace,
                "set-profile",
                "--platform",
                "wechat-mp",
                "--positioning",
                "帮助普通人用 AI 做内容",
                "--target-audience",
                "自媒体新手",
                "--content-directions",
                "AI工具教程,案例复盘",
                "--commercial-goal",
                "内容获客",
                "--core-product",
                "AI训练营",
            )
            result = json.loads(run_cli(
                workspace,
                "wechat-publish",
                "--title",
                "AI工具教程第一篇",
                "--content",
                "content_id: wx-001\n\n这是一篇公众号文章正文。\n\nCTA 转化：欢迎继续关注。",
                "--author",
                "测试作者",
            ).stdout)
            self.assertTrue(result["ok"])
            self.assertEqual(result["adapter"], "wechat-publisher")
            self.assertEqual(result["mode"], "copy-preview")
            preview = Path(result["preview_path"])
            self.assertTrue(preview.exists())
            text = preview.read_text(encoding="utf-8")
            self.assertIn("ARTICLE HTML START", text)
            self.assertIn("复制带样式 HTML", text)
            self.assertTrue(Path(result["precheck_report"]).exists())
            self.assertTrue(result["content_id"].startswith("wechat-mp-draft-"))
            rows = [json.loads(line) for line in (workspace / "data" / "published_content.jsonl").read_text(encoding="utf-8").splitlines()]
            self.assertEqual(rows[-1]["status"], "draft")
            self.assertEqual(rows[-1]["source"], "wechat_publisher_adapter")
            self.assertEqual(rows[-1]["publish_adapter"]["preview_path"], result["preview_path"])

    def test_wechat_publisher_doctor_reports_dependency_status(self):
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            run_cli(workspace, "init")
            doctor = json.loads(run_cli(workspace, "wechat-publisher-doctor", check=False).stdout)
            self.assertIn("publisher_installed", doctor["checks"])
            self.assertIn("node_available", doctor["checks"])
            self.assertIn("copy-preview 不需要公众号凭证", doctor["note"])

    def test_wechat_publisher_adapter_supports_component_layout(self):
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            run_cli(workspace, "init")
            run_cli(workspace, "set-account", "--platform", "wechat-mp", "--account-id", "wx-1", "--account-name", "测试公众号")
            run_cli(
                workspace,
                "set-profile",
                "--platform",
                "wechat-mp",
                "--positioning",
                "帮助普通人用 AI 做内容",
                "--target-audience",
                "自媒体新手",
                "--content-directions",
                "AI工具教程,案例复盘",
            )
            result = json.loads(run_cli(
                workspace,
                "wechat-publish",
                "--title",
                "AI工具教程组件排版",
                "--content",
                "开场说明\n\n第一步：确定任务\n\n第二步：生成草稿\n\n第三步：复盘优化",
                "--layout",
                "component",
            ).stdout)
            self.assertTrue(result["ok"])
            self.assertEqual(result["layout"], "component")
            text = Path(result["preview_path"]).read_text(encoding="utf-8")
            self.assertIn("CREATORBUDDY · 公众号", text)
            self.assertIn("PART", text)
            self.assertIn("#内容增长", text)
            self.assertIn("linear-gradient(90deg,#059669,#10B981)", text)

    def test_import_segment_and_distill_xiaohongshu_benchmark(self):
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            run_cli(workspace, "init")
            state = {
                "user": {
                    "userPageData": {
                        "basicInfo": {"nickname": "测试对标号", "redId": "bench001", "desc": "AI 工具教程"},
                        "interactions": [{"type": "fans", "count": "1000"}],
                        "tags": ["AI", "教程"],
                    },
                    "notes": [[
                        {"index": 1, "noteCard": {"noteId": "n1", "type": "normal", "displayTitle": "AI工具教程入门", "interactInfo": {"likedCount": 120}, "user": {"nickname": "测试对标号", "userId": "u1"}, "cover": {"urlDefault": "https://example.com/1.webp"}}},
                        {"index": 2, "noteCard": {"noteId": "n2", "type": "normal", "displayTitle": "普通人AI避坑清单", "interactInfo": {"likedCount": 38}, "user": {"nickname": "测试对标号", "userId": "u1"}, "cover": {"urlDefault": "https://example.com/2.webp"}}},
                        {"index": 3, "noteCard": {"noteId": "n3", "type": "video", "displayTitle": "WorkBuddy实操案例", "interactInfo": {"likedCount": 210}, "user": {"nickname": "测试对标号", "userId": "u1"}, "cover": {"urlDefault": "https://example.com/3.webp"}}},
                    ]],
                }
            }
            html = workspace / "xhs_profile.html"
            html.write_text(f"<html><script>window.__INITIAL_STATE__={json.dumps(state, ensure_ascii=False)}</script></html>", encoding="utf-8")

            imported = json.loads(run_cli(
                workspace,
                "import-benchmark",
                "--platform",
                "xiaohongshu",
                "--url",
                "https://www.xiaohongshu.com/user/profile/bench001",
                "--html-file",
                str(html),
            ).stdout)
            self.assertEqual(imported["sample_count"], 3)
            self.assertTrue(Path(imported["samples_path"]).exists())
            self.assertTrue((workspace / "data" / "benchmark_samples.jsonl").exists())
            samples = (workspace / "data" / "benchmark_samples.jsonl").read_text(encoding="utf-8").splitlines()
            self.assertEqual(len(samples), 3)
            first = json.loads(samples[0])
            self.assertEqual(first["understanding"]["understanding_level"], "metadata-only")

            segmented = json.loads(run_cli(workspace, "segment-benchmark", "--benchmark-id", "bench001").stdout)
            self.assertTrue(Path(segmented["report"]).exists())

            distilled = json.loads(run_cli(workspace, "distill-creator", "--benchmark-id", "bench001").stdout)
            clone = Path(distilled["clone_path"])
            self.assertTrue(clone.exists())
            clone_text = clone.read_text(encoding="utf-8")
            self.assertIn("Creator Clone: 测试对标号", clone_text)
            self.assertIn("Topic Buckets", clone_text)

    def test_workflow_audit_proves_all_nine_requirements_after_full_run(self):
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            run_cli(workspace, "init")
            run_cli(workspace, "set-account", "--platform", "xiaohongshu", "--account-id", "own-1", "--account-name", "测试账号")
            run_cli(
                workspace,
                "set-profile",
                "--platform",
                "xiaohongshu",
                "--positioning",
                "帮助普通人用 AI 做内容",
                "--target-audience",
                "自媒体新手",
                "--content-directions",
                "AI工具教程,案例复盘",
                "--commercial-goal",
                "内容获客",
                "--core-product",
                "AI训练营",
            )
            run_cli(workspace, "add-benchmark", "--platform", "xiaohongshu", "--account-id", "bench001", "--account-name", "测试对标号")
            run_cli(workspace, "add-content", "--platform", "xiaohongshu", "--content-id", "xhs-001", "--title", "AI工具教程", "--metrics-json", "{\"views\":100,\"likes\":3,\"saves\":6}")

            state = {
                "user": {
                    "userPageData": {
                        "basicInfo": {"nickname": "测试对标号", "redId": "bench001", "desc": "AI 工具教程"},
                        "interactions": [],
                        "tags": ["AI", "教程"],
                    },
                    "notes": [[
                        {"index": 1, "noteCard": {"noteId": "n1", "type": "normal", "displayTitle": "AI工具教程入门", "interactInfo": {"likedCount": 120}, "user": {"nickname": "测试对标号", "userId": "u1"}, "cover": {"urlDefault": "https://example.com/1.webp"}}}
                    ]],
                }
            }
            html = workspace / "xhs_profile.html"
            html.write_text(f"<html><script>window.__INITIAL_STATE__={json.dumps(state, ensure_ascii=False)}</script></html>", encoding="utf-8")
            run_cli(workspace, "import-benchmark", "--platform", "xiaohongshu", "--url", "https://www.xiaohongshu.com/user/profile/bench001", "--html-file", str(html))
            run_cli(workspace, "segment-benchmark", "--benchmark-id", "bench001")
            run_cli(workspace, "distill-creator", "--benchmark-id", "bench001")
            run_cli(workspace, "today")
            run_cli(workspace, "draft", "--platform", "xiaohongshu", "--topic", "AI工具教程")
            precheck = json.loads(run_cli(workspace, "precheck", "--platform", "xiaohongshu", "--title", "AI工具教程", "--content", "content_id: xhs-001 CTA 转化 正文").stdout)
            self.assertTrue(Path(precheck["report"]).exists())
            run_cli(workspace, "post-review", "--content-id", "xhs-001")
            growth = json.loads(run_cli(workspace, "self-growth").stdout)
            run_cli(workspace, "approve-strategy", "--candidate-id", growth["candidates"][0]["candidate_id"])
            readback_draft = json.loads(run_cli(workspace, "draft", "--platform", "xiaohongshu", "--topic", "AI工具教程复盘").stdout)
            self.assertTrue(readback_draft["draft"]["strategy_context"])
            audit = json.loads(run_cli(workspace, "workflow-audit").stdout)
            self.assertTrue(audit["ok"])
            self.assertTrue(all(item["status"] == "complete" for item in audit["items"].values()))


if __name__ == "__main__":
    unittest.main()
