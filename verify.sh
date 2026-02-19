#!/bin/bash
# verify.sh — Validate entire Claude Code configuration integrity
# Run after installation, after upgrades, or when something seems wrong

PASS=0
FAIL=0
WARN=0

pass() { echo "  ✓ $1"; ((PASS++)); }
fail() { echo "  ✗ $1"; ((FAIL++)); }
warn() { echo "  ⚠ $1"; ((WARN++)); }

check() {
    if eval "$2" > /dev/null 2>&1; then
        pass "$1"
    else
        fail "$1"
    fi
}

echo "=== Claude Code Configuration Verification ==="
echo "Date: $(date)"
echo ""

echo "--- Core Files ---"
check "CLAUDE.md exists" "test -f $HOME/.claude/CLAUDE.md"
check "CLAUDE.md under 50 lines" "[ \$(wc -l < $HOME/.claude/CLAUDE.md) -lt 50 ]"
check "CLAUDE.md has Dual-Model section" "grep -q 'Dual-Model' $HOME/.claude/CLAUDE.md"
check "CLAUDE.md has Enforcement Hierarchy" "grep -q 'Enforcement Hierarchy' $HOME/.claude/CLAUDE.md"
check "settings.json valid JSON" "python3 -c \"import json; json.load(open('$HOME/.claude/settings.json'))\""

echo ""
echo "--- Hooks (settings.json) ---"
check "PreToolUse hooks present" "python3 -c \"import json; assert 'PreToolUse' in json.load(open('$HOME/.claude/settings.json'))['hooks']\""
check "PostToolUse hooks present" "python3 -c \"import json; assert 'PostToolUse' in json.load(open('$HOME/.claude/settings.json'))['hooks']\""
check "Stop hook present" "python3 -c \"import json; assert 'Stop' in json.load(open('$HOME/.claude/settings.json'))['hooks']\""
check "SessionStart hook present" "python3 -c \"import json; assert 'SessionStart' in json.load(open('$HOME/.claude/settings.json'))['hooks']\""
check "SessionEnd hook present" "python3 -c \"import json; assert 'SessionEnd' in json.load(open('$HOME/.claude/settings.json'))['hooks']\""
check "TaskCompleted hook present" "python3 -c \"import json; assert 'TaskCompleted' in json.load(open('$HOME/.claude/settings.json'))['hooks']\""
check "PreCompact hook present" "python3 -c \"import json; assert 'PreCompact' in json.load(open('$HOME/.claude/settings.json'))['hooks']\""
check "7+ event types covered" "python3 -c \"import json; assert len(json.load(open('$HOME/.claude/settings.json'))['hooks']) >= 7\""

echo ""
echo "--- Commands ---"
for cmd in commit pr branch push fix-pr-feedback; do
    check "/$cmd command exists" "test -f $HOME/.claude/commands/$cmd.md"
done
check "Commands README exists" "test -f $HOME/.claude/commands/README.md"

echo ""
echo "--- Security ---"
check "protected-patterns.json exists" "test -f $HOME/.claude/protected-patterns.json"
check "protected-patterns.json valid JSON" "python3 -c \"import json; json.load(open('$HOME/.claude/protected-patterns.json'))\""
check "12+ secret patterns defined" "python3 -c \"import json; assert len(json.load(open('$HOME/.claude/protected-patterns.json'))['secret_patterns']) >= 12\""
check "pre-commit-hook.sh exists" "test -f $HOME/.claude/pre-commit-hook.sh"
check "pre-commit-hook.sh executable" "test -x $HOME/.claude/pre-commit-hook.sh"

echo ""
echo "--- Infrastructure ---"
check "MCP github at user scope" "python3 -c \"import json; assert 'github' in json.load(open('$HOME/.claude.json')).get('mcpServers',{})\""
check "gh CLI authenticated" "gh auth status"
check ".env.template exists" "test -f $HOME/.claude/.env.template"
check "MANIFEST.md exists" "test -f $HOME/.claude/MANIFEST.md"
check "CHANGELOG.md exists" "test -f $HOME/.claude/CHANGELOG.md"
check "Skill routing table exists" "test -f $HOME/.claude/rules/skill-routing.md"

echo ""
echo "--- Environment ---"
check "git available" "which git"
check "gh available" "which gh"
check "python3 available" "which python3"
check "jq available" "which jq"
check "claude available" "which claude"

echo ""
echo "=== Results ==="
echo "Passed: $PASS"
echo "Failed: $FAIL"
echo "Warnings: $WARN"
echo ""

if [ $FAIL -eq 0 ]; then
    echo "All checks passed!"
    exit 0
else
    echo "Fix $FAIL failure(s) above."
    exit 1
fi
