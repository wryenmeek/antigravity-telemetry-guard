---
name: antigravity-telemetry
description: Generate, post, and verify Antigravity session token spend telemetry reports and pre-merge receipts across pull requests.
---

# Antigravity Telemetry & Pre-Merge Guard

Use this skill to inspect session token expenditure, publish verified PR telemetry reports factoring Antigravity's multi-turn session prompt caching, and verify pre-merge guards.

## Commands

### 1. Post or Refresh PR Telemetry Report
```bash
antigravity-telemetry post --pr <PR_NUMBER>
```
- Extracts all `Antigravity-Session-ID` trailers from PR commits.
- Queries Antigravity session SQLite databases (`~/.gemini/antigravity/conversations/<id>.db`).
- Calculates uncached prompt, cached prompt hits, thinking, candidate tokens, net billed tokens, and estimated cost.
- Validates 100% session provenance.
- Posts/updates the report comment on GitHub with an embedded verification receipt.

### 2. Verify PR Pre-Merge Guard
```bash
antigravity-telemetry verify --pr <PR_NUMBER>
```
- Validates that a verified telemetry receipt exists on the PR.
- Verifies that all committed session IDs on the PR are present in the receipt.
- Returns exit code `0` if passed; exits `1` if blocked.
