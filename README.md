# Antigravity Telemetry Guard

[![CI](https://github.com/wryenmeek/antigravity-telemetry-guard/actions/workflows/ci.yml/badge.svg)](https://github.com/wryenmeek/antigravity-telemetry-guard/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)

> **Deterministic AI agent token spend telemetry, session prompt caching receipts, and pre-merge guards for Google Antigravity and Compound Engineering pipelines.**

---

## Overview

When running autonomous AI coding agent fleets (such as Google Antigravity, Compound Engineering `lfg`, or multi-agent orchestrators), tracking accurate token consumption and costs is essential. 

Modern foundation models like **Gemini 3.8 Flash** heavily utilize **session prompt context caching** (>90% cache hit rates on multi-turn conversations), providing up to a 75% discount on cached input tokens. Standard un-cached API metrics or static character counts drastically miscalculate actual spend.

`antigravity-telemetry-guard` provides a complete, deterministic, zero-dependency closed loop:
1. **Deterministic Commit Receipts**: Automatically injects `Antigravity-Session-ID: <uuid>` git trailers into all commits made by agents.
2. **True Ground-Truth Telemetry**: Extracts raw protobuf varint execution metadata directly from local Antigravity conversation databases (`~/.gemini/antigravity/conversations/*.db`), measuring uncached prompt, cached prompt hits, thinking tokens, and candidate output.
3. **Automated PR Telemetry Comments**: Publishes comprehensive billing reports directly onto GitHub Pull Requests with embedded cryptographic receipts.
4. **Pre-Merge Validation Gate**: Hard-blocks `gh pr merge` and `git merge` commands (both locally via lifecycle harness hooks and remotely via GitHub Actions) until 100% of committed agent sessions have verified token telemetry receipts.

---

## Architecture

```
       [ Antigravity Agent Session ]
                    │
       (run_command: git commit)
                    ▼
     [ PreToolUse Harness Hook ] ───► Auto-injects trailer:
                    │                  "Antigravity-Session-ID: <session-id>"
                    ▼
          [ Git Commit in Repo ]
                    │
                    ▼
       (ce-commit-push-pr / lfg) ────► Pushes branch & opens PR
                    │
                    ▼
   [ antigravity-telemetry post --pr <N> ]
                    │
     1. Queries git trailers for all session IDs in PR
     2. Decodes protobuf varints directly from ~/.gemini/antigravity/conversations/*.db
     3. Asserts 100% session provenance (all committed sessions accounted for)
     4. Posts/updates PR telemetry comment with embedded cryptographic receipt:
        <!-- ANTIGRAVITY-TELEMETRY-RECEIPT-START ... END -->
                    │
     ┌──────────────┴──────────────┐
     ▼                             ▼
[ Local PreToolUse Hook ]     [ Remote GitHub Actions CI ]
(intercepts gh/git merge)     (action.yml)
     │                             │
     ▼                             ▼
   [ antigravity-telemetry verify --pr <N> --post-status ]
     │
     ├─► Passes: Exits 0, commit status green, merge proceeds
     └─► Fails / Missing: Exits 1, hard-blocks merge with remediation prompt
```

---

## Features

- **Zero External Dependencies**: Built strictly using Python's standard library (`sqlite3`, `json`, `subprocess`, `argparse`).
- **Prompt Cache Accounting**: Correctly factors Gemini tiered caching discounts (`Uncached + 0.25 × Cached + Output`).
- **Cryptographic Receipts**: Embeds tamper-evident machine-readable JSON blocks into PR comments.
- **Comment Provenance Authentication**: Ignores forged comments from untrusted users; validates against `OWNER`, `MEMBER`, `COLLABORATOR`, or verified bot authors.
- **Fail-Closed Pagination**: Recursive GraphQL commit pagination guaranteed to evaluate 100% of PR commits across large pull requests (>100 commits).
- **Commit Status Check Bridge**: Posts commit status checks directly to `headRefOid` via the GitHub REST API, satisfying required branch protections immediately upon comment publication.
- **Antigravity Harness Integration**: Seamlessly hooks into Antigravity's tool lifecycle (`PreToolUse`, `PostToolUse`).

---

## Installation

### 1. Standalone Python CLI
```bash
pip install git+https://github.com/wryenmeek/antigravity-telemetry-guard.git
```
Or install locally in editable mode:
```bash
git clone https://github.com/wryenmeek/antigravity-telemetry-guard.git
cd antigravity-telemetry-guard
pip install -e .
```

### 2. Antigravity Agent Plugin
To enable automatic commit trailer injection and local merge guards in Antigravity:
```bash
mkdir -p ~/.gemini/config/plugins/
cp -r plugin ~/.gemini/config/plugins/antigravity-telemetry-guard
```

---

## GitHub Actions CI Integration

Add the pre-merge guard workflow to your repository at `.github/workflows/antigravity-telemetry-guard.yml`:

```yaml
name: Antigravity Telemetry Pre-Merge Guard

on:
  pull_request:
    branches: [ main ]
    types: [ opened, synchronize, reopened, ready_for_review ]
  issue_comment:
    types: [ created, edited ]
  workflow_dispatch:
    inputs:
      pr_number:
        description: "Pull Request number to verify"
        required: true
        type: string

permissions:
  contents: read
  pull-requests: read
  issues: read
  statuses: write

jobs:
  verify-telemetry-receipts:
    name: Verify Antigravity Session Telemetry
    runs-on: ubuntu-latest
    if: github.event_name == 'pull_request' || (github.event_name == 'issue_comment' && github.event.issue.pull_request) || github.event_name == 'workflow_dispatch'
    steps:
      - name: Checkout Code
        uses: actions/checkout@v4
        with:
          fetch-depth: 0

      - name: Run Antigravity Telemetry Guard
        uses: wryenmeek/antigravity-telemetry-guard@v1
        with:
          pr-number: ${{ github.event.pull_request.number || github.event.issue.number || inputs.pr_number }}
          post-status: 'true'
          github-token: ${{ secrets.GITHUB_TOKEN }}
```

---

## CLI Usage

### Post or Refresh PR Telemetry
Calculates token usage from local Antigravity SQLite databases and posts a verified report comment:
```bash
antigravity-telemetry post --pr <PR_NUMBER> [--repo owner/repo]
```

### Verify PR Pre-Merge Guard
Validates that all commit session trailers are accounted for by an authenticated receipt comment:
```bash
antigravity-telemetry verify --pr <PR_NUMBER> [--post-status] [--repo owner/repo]
```

### Version Check
```bash
antigravity-telemetry version
```

---

## Development & Testing

Run unit tests across all test suites:
```bash
python3 -m unittest discover -s tests -p 'test_*.py' -v
```

---

## License

[MIT](LICENSE) © 2026 Wryen Meek
