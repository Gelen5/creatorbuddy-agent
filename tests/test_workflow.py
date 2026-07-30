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
            run_cli(workspace, "add-benchmark", "--platform", "xiaohongshu", "--account-id", "bench-1", "--account-name", "测试对标")
            signal = workspace / "signal.json"
            signal.write_text(json.dumps({"platform": "xiaohongshu", "topic": "AI工具教程", "heat": 22, "source": "test-adapter"}), encoding="utf-8")
            run_cli(workspace, "collect", "--file", str(signal))
            result = json.loads(run_cli(workspace, "daily-run").stdout)
            self.assertEqual(result["normalized_signal_count"], 1)
            self.assertTrue((workspace / "data" / "normalized_signals.jsonl").exists())
            self.assertTrue((workspace / "data" / "review_reminders.jsonl").exists())
            self.assertTrue((workspace / "data" / "run_log.jsonl").exists())

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


if __name__ == "__main__":
    unittest.main()
