# LifeOS Changelog

All notable changes to the Claude Code global configuration.

## 2026-02-19 — PAI-Inspired Improvements

- Added: MANIFEST.md (USER/SYSTEM file separation)
- Added: protected-patterns.json (12 secret patterns, 7 blocked paths, 10 blocked commands)
- Added: Enforcement Hierarchy section in CLAUDE.md
- Added: commands/README.md (command index with versions)
- Added: pre-commit-hook.sh (stdlib-only secret scanner)
- Added: .env.template (environment variables documentation)
- Added: rules/skill-routing.md (intent → skill routing table)
- Added: upgrade.sh (SYSTEM component update checker)
- Added: verify.sh (configuration integrity verification)
- Added: CI environment detection in SessionStart and Stop hooks
- Added: This CHANGELOG.md

## 2026-02-19 — Comprehensive Hook System

- Expanded: settings.json from 2 to 8 hook entries (7 event types)
- Added: PreToolUse/Bash — 12-pattern blocker (destructive + secrets + curl|bash)
- Added: PreToolUse/Write|Edit — secret file write blocker
- Added: PostToolUse/Bash — post-push Copilot reminder + post-commit summary
- Added: SessionStart/startup — git context injection
- Added: SessionEnd — temp file cleanup + worktree prune
- Added: TaskCompleted — verification reminder
- Added: PreCompact — context save before compaction

## 2026-02-19 — Fork Keeper v4 Complete (Priorities 1-6)

- Added: /fix-pr-feedback — dual-model adversarial bridge (interactive + --auto)
- Added: /commit, /pr, /branch, /push — global git workflow commands
- Added: MCP promoted to user scope (available from any directory)
- Added: Dual-Model Adversarial Architecture section in CLAUDE.md
- Added: Stop hook (auto-checkpoint on session end)
- Added: PreToolUse expanded destructive blocker
- Added: Merge strategy table in skill-repo CLAUDE.md
- Added: .claudeignore in skill repo
- Added: /sync-check, /sync-merge, /sync-pr, /validate-sync — project sync commands
- Added: upstream-sync.yml — daily upstream monitoring workflow
- Added: claude-review.yml — @claude mention review workflow
- Added: Worktree shell helpers (claude-wt, wt-list, wt-clean)
- Added: Fork registry (~/.config/fork-keeper/forks.json)
- Merged: Dependabot PRs #6-#8 (actions v4→v6)
- Enabled: Vulnerability alerts, upstream-sync label
- Verified: E2E adversarial loop (PR #11 — 3 planted bugs, Copilot found all 3 + 8 more)

## 2026-02-18 — Initial Setup

- Created: ~/.claude/CLAUDE.md (global conventions)
- Created: ~/.claude/settings.json (force-push blocker)
- Setup: gh auth, Git identity, Superpowers plugin
- Created: TokyoFloripa/uptodate repo (fork of mvanhorn/last30days-skill)
- Created: Rulesets, CODEOWNERS, CI workflows, Copilot auto-review
