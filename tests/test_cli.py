"""
tests/test_cli.py
Comprehensive unit test suite for antigravity_telemetry.cli
"""

import io
import json
import unittest
from unittest.mock import patch, MagicMock
import subprocess

import antigravity_telemetry.cli as cli


class TestAntigravityTelemetryCli(unittest.TestCase):

    def test_extract_session_ids_from_text(self):
        text = (
            "feat: add feature\n\n"
            "Antigravity-Session-ID: 53ab9a5b-7ca6-4d25-9e39-21463c3bcd6b\n"
            "antigravity-session-id: 53AB9A5B-7CA6-4D25-9E39-21463C3BCD6B\n"
            "Antigravity-Session-ID: 11111111-2222-3333-4444-555555555555\n"
        )
        cids = cli.extract_session_ids_from_text(text)
        self.assertEqual(cids, [
            "53ab9a5b-7ca6-4d25-9e39-21463c3bcd6b",
            "11111111-2222-3333-4444-555555555555"
        ])

    def test_parse_varints(self):
        data = bytes([0x08, 0x96, 0x01])
        res = cli.parse_varints(data)
        self.assertEqual(res.get(1), 150)

    def test_calc_usd_cost(self):
        cost = cli.calc_usd_cost(1_000_000, 1_000_000, 1_000_000)
        self.assertAlmostEqual(cost, 1.575, places=3)

    @patch.object(cli, "get_all_pr_commits_and_head")
    @patch.object(cli, "get_pr_comments")
    def test_verify_no_commits_passes(self, mock_comments, mock_commits):
        mock_commits.return_value = (
            [{"oid": "abc12345", "messageHeadline": "feat: human", "messageBody": ""}],
            "abc12345678"
        )
        mock_comments.return_value = [{"body": "some comment", "authorAssociation": "OWNER"}]
        passed, msg, receipt, head = cli.verify_pr_telemetry(42)
        self.assertTrue(passed)
        self.assertIn("No Antigravity session commits detected", msg)
        self.assertEqual(head, "abc12345678")

    @patch.object(cli, "get_all_pr_commits_and_head")
    @patch.object(cli, "get_pr_comments")
    def test_verify_missing_receipt_fails(self, mock_comments, mock_commits):
        mock_commits.return_value = (
            [{
                "oid": "abc12345",
                "messageHeadline": "feat: ai change",
                "messageBody": "Antigravity-Session-ID: 53ab9a5b-7ca6-4d25-9e39-21463c3bcd6b"
            }],
            "abc12345678"
        )
        mock_comments.return_value = []
        passed, msg, receipt, head = cli.verify_pr_telemetry(42)
        self.assertFalse(passed)
        self.assertIn("ANTIGRAVITY MERGE GUARD FAILED", msg)
        self.assertIsNone(receipt)

    @patch.object(cli, "get_all_pr_commits_and_head")
    @patch.object(cli, "get_pr_comments")
    def test_verify_incomplete_provenance_fails(self, mock_comments, mock_commits):
        mock_commits.return_value = (
            [
                {"oid": "111", "messageHeadline": "c1", "messageBody": "Antigravity-Session-ID: 53ab9a5b-7ca6-4d25-9e39-21463c3bcd6b"},
                {"oid": "222", "messageHeadline": "c2", "messageBody": "Antigravity-Session-ID: 00000000-0000-0000-0000-000000000000"},
            ],
            "22222222"
        )
        receipt_obj = {
            "covered_session_ids": ["53ab9a5b-7ca6-4d25-9e39-21463c3bcd6b"],
            "total_billed_tokens": 10000,
            "cache_hit_pct": 90.0
        }
        comment_body = f"<!-- ANTIGRAVITY-TELEMETRY-RECEIPT-START\n{json.dumps(receipt_obj)}\nANTIGRAVITY-TELEMETRY-RECEIPT-END -->"
        mock_comments.return_value = [{"body": comment_body, "authorAssociation": "OWNER"}]

        passed, msg, receipt, head = cli.verify_pr_telemetry(42)
        self.assertFalse(passed)
        self.assertIn("INCOMPLETE SESSION PROVENANCE", msg)
        self.assertIn("00000000-0000-0000-0000-000000000000", msg)

    @patch.object(cli, "get_all_pr_commits_and_head")
    @patch.object(cli, "get_pr_comments")
    def test_verify_complete_provenance_passes(self, mock_comments, mock_commits):
        mock_commits.return_value = (
            [
                {"oid": "111", "messageHeadline": "c1", "messageBody": "Antigravity-Session-ID: 53ab9a5b-7ca6-4d25-9e39-21463c3bcd6b"},
            ],
            "11111111"
        )
        receipt_obj = {
            "covered_session_ids": ["53ab9a5b-7ca6-4d25-9e39-21463c3bcd6b"],
            "total_billed_tokens": 18608875,
            "cache_hit_pct": 91.9
        }
        comment_body = f"<!-- ANTIGRAVITY-TELEMETRY-RECEIPT-START\n{json.dumps(receipt_obj)}\nANTIGRAVITY-TELEMETRY-RECEIPT-END -->"
        mock_comments.return_value = [{"body": comment_body, "authorAssociation": "OWNER"}]

        passed, msg, receipt, head = cli.verify_pr_telemetry(42)
        self.assertTrue(passed)
        self.assertIn("ANTIGRAVITY MERGE GUARD PASSED", msg)
        self.assertIn("18,608,875", msg)

    @patch.object(cli, "get_all_pr_commits_and_head")
    @patch.object(cli, "get_pr_comments")
    def test_untrusted_comment_ignored(self, mock_comments, mock_commits):
        mock_commits.return_value = (
            [{"oid": "111", "messageHeadline": "c1", "messageBody": "Antigravity-Session-ID: 53ab9a5b-7ca6-4d25-9e39-21463c3bcd6b"}],
            "11111111"
        )
        receipt_obj = {"covered_session_ids": ["53ab9a5b-7ca6-4d25-9e39-21463c3bcd6b"]}
        comment_body = f"<!-- ANTIGRAVITY-TELEMETRY-RECEIPT-START\n{json.dumps(receipt_obj)}\nANTIGRAVITY-TELEMETRY-RECEIPT-END -->"
        mock_comments.return_value = [{"body": comment_body, "authorAssociation": "NONE", "author": {"login": "random-user"}}]

        passed, msg, receipt, head = cli.verify_pr_telemetry(42)
        self.assertFalse(passed)
        self.assertIn("ANTIGRAVITY MERGE GUARD FAILED", msg)

    @patch.object(subprocess, "run")
    def test_post_commit_status(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0, stdout="{}", stderr="")
        ok, msg = cli.post_commit_status("1234567890abcdef", "success", "Verified telemetry", repo="test/repo")
        self.assertTrue(ok)
        mock_run.assert_called_once()
        cmd = mock_run.call_args[0][0]
        self.assertIn("repos/test/repo/statuses/1234567890abcdef", cmd)
        self.assertIn("state=success", cmd)

    def test_post_commit_status_invalid_sha(self):
        ok, msg = cli.post_commit_status("short", "success", "test")
        self.assertFalse(ok)
        self.assertIn("Invalid commit SHA", msg)

    @patch("sys.stdin", io.StringIO(json.dumps({
        "conversationId": "53ab9a5b-7ca6-4d25-9e39-21463c3bcd6b",
        "toolCall": {
            "name": "run_command",
            "args": {
                "CommandLine": "git " + "commit -m \"feat: initial\""
            }
        }
    })))
    @patch("sys.stdout", new_callable=io.StringIO)
    def test_handle_pre_tool_hook_commit_injection(self, mock_stdout):
        cli.handle_pre_tool_hook()
        output = json.loads(mock_stdout.getvalue())
        self.assertEqual(output["decision"], "allow")
        overwritten = output["overwrite"]["CommandLine"]
        self.assertIn("Antigravity-Session-ID: 53ab9a5b-7ca6-4d25-9e39-21463c3bcd6b", overwritten)

    @patch("sys.stdin", io.StringIO(json.dumps({
        "conversationId": "53ab9a5b-7ca6-4d25-9e39-21463c3bcd6b",
        "toolCall": {
            "name": "run_command",
            "args": {
                "CommandLine": "gh " + "pr " + "merge 15 --squash"
            }
        }
    })))
    @patch.object(cli, "verify_pr_telemetry")
    @patch("sys.stdout", new_callable=io.StringIO)
    def test_handle_pre_tool_hook_merge_blocking(self, mock_stdout, mock_verify):
        mock_verify.return_value = (False, "Missing receipt", None, "head123")
        cli.handle_pre_tool_hook()
        output = json.loads(mock_stdout.getvalue())
        self.assertEqual(output["decision"], "deny")
        self.assertIn("ANTIGRAVITY MERGE GUARD BLOCKED", output["reason"])

    @patch("subprocess.run")
    def test_prune_merged_branches_and_worktrees(self, mock_run):
        # Setup mock return values for sequence of git commands
        def side_effect(cmd, **kwargs):
            cmd_str = " ".join(cmd)
            mock = MagicMock(returncode=0, stderr="")
            if "fetch" in cmd_str:
                mock.stdout = ""
            elif "rev-parse --abbrev-ref HEAD" in cmd_str:
                mock.stdout = "main\n"
            elif "symbolic-ref" in cmd_str:
                mock.stdout = "origin/main\n"
            elif "worktree list --porcelain" in cmd_str:
                mock.stdout = (
                    "worktree /repo\nHEAD 111\nbranch refs/heads/main\n\n"
                    "worktree /repo/.worktrees/feat-merged\nHEAD 222\nbranch refs/heads/feat-merged\n\n"
                )
            elif "branch -vv" in cmd_str:
                mock.stdout = "  feat-merged 222 [origin/feat-merged: gone] feat\n* main 111 [origin/main] initial\n"
            elif "branch --merged" in cmd_str:
                mock.stdout = "  feat-merged\n* main\n"
            elif "worktree remove" in cmd_str or "branch -D" in cmd_str or "worktree prune" in cmd_str:
                mock.stdout = ""
            return mock

        mock_run.side_effect = side_effect
        res = cli.prune_merged_branches_and_worktrees("/repo", quiet=True)
        self.assertIn("feat-merged", res["pruned_branches"])
        self.assertEqual(len(res["pruned_worktrees"]), 1)
        self.assertEqual(res["pruned_worktrees"][0]["branch"], "feat-merged")

    @patch("sys.stdin", io.StringIO(json.dumps({
        "toolCall": {
            "name": "run_command",
            "args": {
                "CommandLine": "gh " + "pr " + "merge 10 --squash",
                "Cwd": "/repo"
            }
        }
    })))
    @patch.object(cli, "prune_merged_branches_and_worktrees")
    @patch("sys.stdout", new_callable=io.StringIO)
    def test_handle_post_tool_hook_on_merge(self, mock_stdout, mock_prune):
        mock_prune.return_value = {"pruned_branches": ["feat-done"], "pruned_worktrees": []}
        cli.handle_post_tool_hook()
        mock_prune.assert_called_once_with("/repo", quiet=True)


if __name__ == "__main__":
    unittest.main()
