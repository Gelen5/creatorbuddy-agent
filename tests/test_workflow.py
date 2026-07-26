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


if __name__ == "__main__":
    unittest.main()
