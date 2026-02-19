#!/bin/bash
# verify.sh — Validate entire Claude Code configuration integrity (v2)
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

check_warn() {
    if eval "$2" > /dev/null 2>&1; then
        pass "$1"
    else
        warn "$1"
    fi
}

echo "=== Claude Code Configuration Verification (v2) ==="
echo "Date: $(date)"
echo ""

echo "--- Core Files ---"
check "CLAUDE.md exists" "test -f $HOME/.claude/CLAUDE.md"
check "CLAUDE.md under 50 lines" "[ \$(wc -l < $HOME/.claude/CLAUDE.md) -lt 50 ]"
check "CLAUDE.md has Dual-Model section" "grep -q 'Dual-Model' $HOME/.claude/CLAUDE.md"
check "CLAUDE.md has Enforcement Hierarchy" "grep -q 'Enforcement Hierarchy' $HOME/.claude/CLAUDE.md"
check "CLAUDE.md has SKILL level" "grep -q 'SKILL.*skills/' $HOME/.claude/CLAUDE.md"
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
echo "--- Rules ---"
check "Skill routing table exists" "test -f $HOME/.claude/rules/skill-routing.md"
check "CI environment rules exist" "test -f $HOME/.claude/rules/ci-environment.md"
check_warn "Identity rules exist" "test -f $HOME/.claude/rules/identity.md"

echo ""
echo "--- Skills ---"
check "skills/last30days/ submodule exists" "test -d $HOME/.claude/skills/last30days/.git || test -f $HOME/.claude/skills/last30days/.git"
check "skills/last30days/SKILL.md exists" "test -f $HOME/.claude/skills/last30days/SKILL.md"
check "skills/last30days/scripts/last30days.py exists" "test -f $HOME/.claude/skills/last30days/scripts/last30days.py"
check "skills/last30dayshigh/SKILL.md exists" "test -f $HOME/.claude/skills/last30dayshigh/SKILL.md"
SP_DIR=$(ls -d $HOME/.claude/plugins/cache/claude-plugins-official/superpowers/*/ 2>/dev/null | head -1)
if [ -n "$SP_DIR" ]; then pass "Superpowers plugin installed"; else fail "Superpowers plugin not installed"; fi
check "shell/aliases.zsh exists" "test -f $HOME/.claude/shell/aliases.zsh"

echo ""
echo "--- Security (v2 schema) ---"
check "protected-patterns.json exists" "test -f $HOME/.claude/protected-patterns.json"
check "protected-patterns.json valid JSON" "python3 -c \"import json; json.load(open('$HOME/.claude/protected-patterns.json'))\""
check "Schema version is 2.0.0" "python3 -c \"import json; assert json.load(open('$HOME/.claude/protected-patterns.json'))['_schema_version'] == '2.0.0'\""
check "All regex patterns compile" "python3 -c \"
import json, re
d = json.load(open('$HOME/.claude/protected-patterns.json'))
for section in ['secrets', 'pii', 'blocked_paths', 'blocked_commands']:
    for p in d.get(section, {}).get('patterns', []):
        re.compile(p['regex'])
\""
check "15+ secret patterns" "python3 -c \"import json; assert len(json.load(open('$HOME/.claude/protected-patterns.json'))['secrets']['patterns']) >= 15\""
check "PII patterns present" "python3 -c \"import json; assert len(json.load(open('$HOME/.claude/protected-patterns.json'))['pii']['patterns']) >= 3\""
check "pre-commit-hook.sh exists" "test -f $HOME/.claude/pre-commit-hook.sh"
check "pre-commit-hook.sh executable" "test -x $HOME/.claude/pre-commit-hook.sh"

echo ""
echo "--- Infrastructure ---"
check "MCP github at user scope" "python3 -c \"import json; assert 'github' in json.load(open('$HOME/.claude.json')).get('mcpServers',{})\""
check "gh CLI authenticated" "gh auth status"
check ".env.template exists" "test -f $HOME/.claude/.env.template"
check "MANIFEST.md exists" "test -f $HOME/.claude/MANIFEST.md"
check "CHANGELOG.md exists" "test -f $HOME/.claude/CHANGELOG.md"
check "install.sh exists" "test -f $HOME/.claude/install.sh"
check "install.sh executable" "test -x $HOME/.claude/install.sh"

echo ""
echo "--- Environment ---"
check "git available" "which git"
check "gh available" "which gh"
check "python3 available" "which python3"
check "jq available" "which jq"
check "claude available" "which claude"

echo ""
echo "--- Environment Variables ---"
ENV_FILE="$HOME/.config/last30days/.env"
if [ -f "$ENV_FILE" ]; then
    check_warn "OPENAI_API_KEY set" "grep -q '^OPENAI_API_KEY=.' '$ENV_FILE'"
    check_warn "XAI_API_KEY set" "grep -q '^XAI_API_KEY=.' '$ENV_FILE'"
else
    warn "~/.config/last30days/.env not found"
fi

echo ""
echo "--- File Health ---"
for f in CLAUDE.md settings.json MANIFEST.md protected-patterns.json .env.template CHANGELOG.md; do
    target="$HOME/.claude/$f"
    if [ -L "$target" ]; then
        if [ -e "$target" ]; then
            pass "$f symlink valid"
        else
            fail "$f is a dangling symlink"
        fi
    elif [ -f "$target" ]; then
        pass "$f exists (regular file)"
    else
        fail "$f missing"
    fi
done

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
