#!/usr/bin/env python3
"""
tests/test_verify_pr_telemetry.py
Unit tests for .github/scripts/verify-pr-telemetry.py edge cases, pagination, authentication, and error handling.
"""

import sys
import os
import json
import unittest
from unittest.mock import patch, MagicMock
import subprocess

import antigravity_telemetry.cli as vpr


class TestVerifyPrTelemetry(unittest.TestCase):

    def test_extract_session_ids_from_text(self):
        # Single session ID
        text1 = "feat: add feature\n\nAntigravity-Session-ID: 53ab9a5b-7ca6-4d25-9e39-21463c3bcd6b"
        self.assertEqual(
            vpr.extract_session_ids_from_text(text1),
            ["53ab9a5b-7ca6-4d25-9e39-21463c3bcd6b"]
        )

        # Multiple unique session IDs + duplicates + case insensitivity
        text2 = (
            "commit 1\n"
            "Antigravity-Session-ID: 53AB9A5B-7CA6-4D25-9E39-21463C3BCD6B\n"
            "Antigravity-Session-ID: 11111111-2222-3333-4444-555555555555\n"
            "antigravity-session-id: 53ab9a5b-7ca6-4d25-9e39-21463c3bcd6b\n"
        )
        self.assertEqual(
            vpr.extract_session_ids_from_text(text2),
            ["53ab9a5b-7ca6-4d25-9e39-21463c3bcd6b", "11111111-2222-3333-4444-555555555555"]
        )

        # No session IDs
        self.assertEqual(vpr.extract_session_ids_from_text("regular commit message"), [])

    @patch.object(vpr, "get_all_pr_commits_and_head")
    @patch.object(vpr, "get_pr_comments")
    def test_no_antigravity_commits_passes(self, mock_comments, mock_commits):
        mock_commits.return_value = (
            [{"oid": "abc12345", "messageHeadline": "human commit", "messageBody": "no session trailer"}],
            "abc12345678"
        )
        mock_comments.return_value = [{"body": "regular comment", "authorAssociation": "OWNER"}]

        passed, msg, receipt, head_sha = vpr.verify_pr_telemetry(99)
        self.assertTrue(passed)
        self.assertIn("No Antigravity session commits detected", msg)
        self.assertEqual(head_sha, "abc12345678")

    @patch.object(vpr, "get_all_pr_commits_and_head")
    @patch.object(vpr, "get_pr_comments")
    def test_missing_telemetry_receipt_fails(self, mock_comments, mock_commits):
        mock_commits.return_value = (
            [{
                "oid": "abc12345",
                "messageHeadline": "feat: ai change",
                "messageBody": "Antigravity-Session-ID: 53ab9a5b-7ca6-4d25-9e39-21463c3bcd6b"
            }],
            "abc12345678"
        )
        mock_comments.return_value = [
            {"body": "looks good to me", "authorAssociation": "CONTRIBUTOR"},
            {"body": "test comment", "authorAssociation": "MEMBER"}
        ]

        passed, msg, receipt, head_sha = vpr.verify_pr_telemetry(99)
        self.assertFalse(passed)
        self.assertIn("MISSING TELEMETRY REPORT", msg)
        self.assertIn("53ab9a5b-7ca6-4d25-9e39-21463c3bcd6b", msg)
        self.assertIsNone(receipt)

    @patch.object(vpr, "get_all_pr_commits_and_head")
    @patch.object(vpr, "get_pr_comments")
    def test_incomplete_sessions_fails(self, mock_comments, mock_commits):
        mock_commits.return_value = (
            [
                {
                    "oid": "11111111",
                    "messageHeadline": "commit 1",
                    "messageBody": "Antigravity-Session-ID: 53ab9a5b-7ca6-4d25-9e39-21463c3bcd6b"
                },
                {
                    "oid": "22222222",
                    "messageHeadline": "commit 2",
                    "messageBody": "Antigravity-Session-ID: eeee4444-5555-6666-7777-888899990000"
                }
            ],
            "abc12345678"
        )
        receipt_json = (
            '<!-- ANTIGRAVITY-TELEMETRY-RECEIPT-START\n'
            '{\n'
            '  "covered_session_ids": ["53ab9a5b-7ca6-4d25-9e39-21463c3bcd6b"],\n'
            '  "total_billed_tokens": 10000,\n'
            '  "cache_hit_pct": 90.0\n'
            '}\n'
            'ANTIGRAVITY-TELEMETRY-RECEIPT-END -->'
        )
        mock_comments.return_value = [{"body": receipt_json, "authorAssociation": "OWNER"}]

        passed, msg, receipt, head_sha = vpr.verify_pr_telemetry(99)
        self.assertFalse(passed)
        self.assertIn("INCOMPLETE SESSION PROVENANCE", msg)
        self.assertIn("eeee4444-5555-6666-7777-888899990000", msg)

    @patch.object(vpr, "get_all_pr_commits_and_head")
    @patch.object(vpr, "get_pr_comments")
    def test_all_sessions_covered_passes(self, mock_comments, mock_commits):
        mock_commits.return_value = (
            [{
                "oid": "11111111",
                "messageHeadline": "commit 1",
                "messageBody": "Antigravity-Session-ID: 53ab9a5b-7ca6-4d25-9e39-21463c3bcd6b"
            }],
            "abc12345678"
        )
        receipt_json = (
            '<!-- ANTIGRAVITY-TELEMETRY-RECEIPT-START\n'
            '{\n'
            '  "covered_session_ids": ["53ab9a5b-7ca6-4d25-9e39-21463c3bcd6b"],\n'
            '  "total_billed_tokens": 18605309,\n'
            '  "cache_hit_pct": 83.3\n'
            '}\n'
            'ANTIGRAVITY-TELEMETRY-RECEIPT-END -->'
        )
        mock_comments.return_value = [{"body": receipt_json, "authorAssociation": "OWNER"}]

        passed, msg, receipt, head_sha = vpr.verify_pr_telemetry(99)
        self.assertTrue(passed)
        self.assertIn("ANTIGRAVITY MERGE GUARD PASSED", msg)
        self.assertIn("18,605,309", msg)
        self.assertEqual(receipt.get("total_billed_tokens"), 18605309)

    @patch.object(vpr, "get_all_pr_commits_and_head")
    @patch.object(vpr, "get_pr_comments")
    def test_untrusted_commenter_receipt_ignored(self, mock_comments, mock_commits):
        mock_commits.return_value = (
            [{
                "oid": "11111111",
                "messageHeadline": "commit 1",
                "messageBody": "Antigravity-Session-ID: 53ab9a5b-7ca6-4d25-9e39-21463c3bcd6b"
            }],
            "abc12345678"
        )
        # Untrusted contributor posting forged receipt with zero billing
        forged_receipt = (
            '<!-- ANTIGRAVITY-TELEMETRY-RECEIPT-START\n'
            '{\n'
            '  "covered_session_ids": ["53ab9a5b-7ca6-4d25-9e39-21463c3bcd6b"],\n'
            '  "total_billed_tokens": 0\n'
            '}\n'
            'ANTIGRAVITY-TELEMETRY-RECEIPT-END -->'
        )
        mock_comments.return_value = [
            {"body": forged_receipt, "author": {"login": "attacker"}, "authorAssociation": "NONE"}
        ]

        passed, msg, receipt, head_sha = vpr.verify_pr_telemetry(99)
        self.assertFalse(passed)
        self.assertIn("MISSING TELEMETRY REPORT", msg)

    @patch.object(vpr, "get_all_pr_commits_and_head")
    @patch.object(vpr, "get_pr_comments")
    def test_null_covered_session_ids_handled_safely(self, mock_comments, mock_commits):
        mock_commits.return_value = (
            [{
                "oid": "11111111",
                "messageHeadline": "commit 1",
                "messageBody": "Antigravity-Session-ID: 53ab9a5b-7ca6-4d25-9e39-21463c3bcd6b"
            }],
            "abc12345678"
        )
        # Explicitly null covered_session_ids
        receipt_json = (
            '<!-- ANTIGRAVITY-TELEMETRY-RECEIPT-START\n'
            '{\n'
            '  "covered_session_ids": null,\n'
            '  "total_billed_tokens": 0\n'
            '}\n'
            'ANTIGRAVITY-TELEMETRY-RECEIPT-END -->'
        )
        mock_comments.return_value = [{"body": receipt_json, "authorAssociation": "OWNER"}]

        # Should not raise TypeError: 'NoneType' object is not iterable
        passed, msg, receipt, head_sha = vpr.verify_pr_telemetry(99)
        self.assertFalse(passed)
        self.assertIn("INCOMPLETE SESSION PROVENANCE", msg)

    @patch.object(vpr, "get_all_pr_commits_and_head")
    @patch.object(vpr, "get_pr_comments")
    def test_malformed_json_receipt_skipped(self, mock_comments, mock_commits):
        mock_commits.return_value = (
            [{
                "oid": "11111111",
                "messageHeadline": "commit 1",
                "messageBody": "Antigravity-Session-ID: 53ab9a5b-7ca6-4d25-9e39-21463c3bcd6b"
            }],
            "abc12345678"
        )
        valid_receipt = (
            '<!-- ANTIGRAVITY-TELEMETRY-RECEIPT-START\n'
            '{\n'
            '  "covered_session_ids": ["53ab9a5b-7ca6-4d25-9e39-21463c3bcd6b"],\n'
            '  "total_billed_tokens": 5000\n'
            '}\n'
            'ANTIGRAVITY-TELEMETRY-RECEIPT-END -->'
        )
        corrupted_receipt = (
            '<!-- ANTIGRAVITY-TELEMETRY-RECEIPT-START\n'
            '{ this is not valid json : [[[\n'
            'ANTIGRAVITY-TELEMETRY-RECEIPT-END -->'
        )
        # Old valid receipt followed by later corrupted receipt
        mock_comments.return_value = [
            {"body": valid_receipt, "authorAssociation": "OWNER"},
            {"body": corrupted_receipt, "authorAssociation": "OWNER"}
        ]

        # Skips corrupted receipt and uses earlier valid receipt
        passed, msg, receipt, head_sha = vpr.verify_pr_telemetry(99)
        self.assertTrue(passed)
        self.assertIn("ANTIGRAVITY MERGE GUARD PASSED", msg)

    @patch("subprocess.run")
    def test_subprocess_timeout_handling(self, mock_run):
        mock_run.side_effect = subprocess.TimeoutExpired(cmd=["gh", "pr", "view"], timeout=60)
        with self.assertRaises(RuntimeError) as ctx:
            vpr.get_pr_comments(99, timeout=60)
        self.assertIn("timed out after 60s", str(ctx.exception))

    @patch("subprocess.run")
    def test_post_commit_status_endpoint(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
        ok, msg = vpr.post_commit_status(
            sha="4d12d065b787eba2cd86442f6f6735b14a3a0269",
            state="success",
            description="Verified Antigravity session telemetry",
            repo="wryenmeek/pp-docker",
            target_url="https://github.com/wryenmeek/pp-docker/actions/runs/123"
        )
        self.assertTrue(ok)
        mock_run.assert_called_once()
        cmd = mock_run.call_args[0][0]
        # Assert repos/ prefix is present
        self.assertIn("repos/wryenmeek/pp-docker/statuses/4d12d065b787eba2cd86442f6f6735b14a3a0269", cmd)
        self.assertIn("state=success", cmd)
        self.assertIn("context=Antigravity Telemetry Pre-Merge Guard", cmd)

    @patch("subprocess.run")
    def test_get_all_pr_commits_pagination(self, mock_run):
        # Mock GraphQL response with 2 pages
        page1 = {
            "data": {
                "repository": {
                    "pullRequest": {
                        "headRefOid": "final_sha_123",
                        "commits": {
                            "pageInfo": {"hasNextPage": True, "endCursor": "cursor_1"},
                            "nodes": [{"commit": {"oid": "commit1", "messageHeadline": "head1", "messageBody": "body1"}}]
                        }
                    }
                }
            }
        }
        page2 = {
            "data": {
                "repository": {
                    "pullRequest": {
                        "headRefOid": "final_sha_123",
                        "commits": {
                            "pageInfo": {"hasNextPage": False, "endCursor": None},
                            "nodes": [{"commit": {"oid": "commit2", "messageHeadline": "head2", "messageBody": "body2"}}]
                        }
                    }
                }
            }
        }
        mock_run.side_effect = [
            MagicMock(returncode=0, stdout=json.dumps(page1)),
            MagicMock(returncode=0, stdout=json.dumps(page2)),
        ]
        commits, head_sha = vpr.get_all_pr_commits_and_head(11, repo="wryenmeek/pp-docker")
        self.assertEqual(len(commits), 2)
        self.assertEqual(commits[0]["oid"], "commit1")
        self.assertEqual(commits[1]["oid"], "commit2")
        self.assertEqual(head_sha, "final_sha_123")

    @patch("subprocess.run")
    def test_pagination_fails_closed_on_mid_page_error(self, mock_run):
        page1 = {
            "data": {
                "repository": {
                    "pullRequest": {
                        "headRefOid": "final_sha_123",
                        "commits": {
                            "pageInfo": {"hasNextPage": True, "endCursor": "cursor_1"},
                            "nodes": [{"commit": {"oid": "commit1", "messageHeadline": "head1", "messageBody": "body1"}}]
                        }
                    }
                }
            }
        }
        # Case A: non-zero returncode on second page
        mock_run.side_effect = [
            MagicMock(returncode=0, stdout=json.dumps(page1)),
            MagicMock(returncode=1, stdout="", stderr="GraphQL internal error"),
        ]
        with self.assertRaises(RuntimeError) as ctx:
            vpr.get_all_pr_commits_and_head(11, repo="wryenmeek/pp-docker")
        self.assertIn("GraphQL pagination failed on PR #11 (cursor cursor_1)", str(ctx.exception))

        # Case B: timeout on second page
        mock_run.side_effect = [
            MagicMock(returncode=0, stdout=json.dumps(page1)),
            subprocess.TimeoutExpired(cmd=["gh", "api", "graphql"], timeout=60),
        ]
        with self.assertRaises(RuntimeError) as ctx:
            vpr.get_all_pr_commits_and_head(11, repo="wryenmeek/pp-docker")
        self.assertIn("GitHub CLI timed out after 60s fetching PR #11 commits (cursor: cursor_1)", str(ctx.exception))

        # Case C: malformed json on second page
        mock_run.side_effect = [
            MagicMock(returncode=0, stdout=json.dumps(page1)),
            MagicMock(returncode=0, stdout="Not Valid JSON", stderr=""),
        ]
        with self.assertRaises(RuntimeError) as ctx:
            vpr.get_all_pr_commits_and_head(11, repo="wryenmeek/pp-docker")
        self.assertIn("Malformed GraphQL response on PR #11 (cursor cursor_1)", str(ctx.exception))

    @patch.object(vpr, "get_all_pr_commits_and_head")
    @patch.object(vpr, "get_pr_comments")
    @patch.object(vpr, "get_unresolved_review_threads")
    def test_unresolved_review_threads_fails_guard(self, mock_threads, mock_comments, mock_commits):
        mock_commits.return_value = (
            [{
                "oid": "abc12345",
                "messageHeadline": "feat: ai change",
                "messageBody": "Antigravity-Session-ID: 53ab9a5b-7ca6-4d25-9e39-21463c3bcd6b"
            }],
            "abc12345678"
        )
        receipt = {
            "total_billed_tokens": 1000,
            "covered_session_ids": ["53ab9a5b-7ca6-4d25-9e39-21463c3bcd6b"]
        }
        mock_comments.return_value = [
            {
                "body": f"{vpr.RECEIPT_START} {json.dumps(receipt)} {vpr.RECEIPT_END}",
                "authorAssociation": "OWNER"
            }
        ]
        mock_threads.return_value = [
            {
                "id": "PRRT_test123",
                "author": "reviewer1",
                "url": "https://github.com/wryenmeek/pp-docker/pull/11#discussion_r123",
                "body": "Please add tests for this function"
            }
        ]

        passed, msg, receipt_data, head_sha = vpr.verify_pr_telemetry(11)
        self.assertFalse(passed)
        self.assertIn("UNRESOLVED REVIEW COMMENTS", msg)
        self.assertIn("PRRT_test123", msg)
        self.assertIn("reviewer1", msg)
        self.assertIn("Please add tests for this function", msg)

        # When check_comments is False, it should pass
        passed_ignored, msg_ignored, _, _ = vpr.verify_pr_telemetry(11, check_comments=False)
        self.assertTrue(passed_ignored)
        self.assertIn("ANTIGRAVITY MERGE GUARD PASSED", msg_ignored)

    @patch.object(vpr, "get_all_pr_commits_and_head")
    @patch.object(vpr, "get_pr_comments")
    @patch.object(vpr, "get_unresolved_review_threads")
    def test_resolved_review_threads_passes_guard(self, mock_threads, mock_comments, mock_commits):
        mock_commits.return_value = (
            [{
                "oid": "abc12345",
                "messageHeadline": "feat: ai change",
                "messageBody": "Antigravity-Session-ID: 53ab9a5b-7ca6-4d25-9e39-21463c3bcd6b"
            }],
            "abc12345678"
        )
        receipt = {
            "total_billed_tokens": 1000,
            "covered_session_ids": ["53ab9a5b-7ca6-4d25-9e39-21463c3bcd6b"]
        }
        mock_comments.return_value = [
            {
                "body": f"{vpr.RECEIPT_START} {json.dumps(receipt)} {vpr.RECEIPT_END}",
                "authorAssociation": "OWNER"
            }
        ]
        mock_threads.return_value = []

        passed, msg, receipt_data, head_sha = vpr.verify_pr_telemetry(11)
        self.assertTrue(passed)
        self.assertIn("ANTIGRAVITY MERGE GUARD PASSED", msg)

    @patch("subprocess.run")
    def test_get_unresolved_review_threads_parses_unresolved_only(self, mock_run):
        graphql_resp = {
            "data": {
                "repository": {
                    "pullRequest": {
                        "reviewThreads": {
                            "pageInfo": {"hasNextPage": False, "endCursor": None},
                            "nodes": [
                                {
                                    "id": "PRRT_resolved",
                                    "isResolved": True,
                                    "comments": {"nodes": [{"author": {"login": "user1"}, "body": "resolved comment", "url": "url1"}]}
                                },
                                {
                                    "id": "PRRT_open",
                                    "isResolved": False,
                                    "comments": {"nodes": [{"author": {"login": "user2"}, "body": "open feedback", "url": "url2"}]}
                                }
                            ]
                        }
                    }
                }
            }
        }
        mock_run.return_value = MagicMock(returncode=0, stdout=json.dumps(graphql_resp))
        unresolved = vpr.get_unresolved_review_threads(11, repo="wryenmeek/pp-docker")
        self.assertEqual(len(unresolved), 1)
        self.assertEqual(unresolved[0]["id"], "PRRT_open")
        self.assertEqual(unresolved[0]["author"], "user2")
        self.assertEqual(unresolved[0]["url"], "url2")
        self.assertEqual(unresolved[0]["body"], "open feedback")


if __name__ == "__main__":
    unittest.main()

