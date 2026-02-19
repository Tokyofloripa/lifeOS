#!/bin/bash
# upgrade.sh — Check SYSTEM components for updates and show USER/SYSTEM status
# Run periodically or after Claude Code updates

echo "=== Claude Code Infrastructure Status ==="
echo "Date: $(date)"
echo ""

echo "--- SYSTEM Components (safe to update) ---"

# Superpowers version
SP_DIR=$(ls -d ~/.claude/plugins/cache/claude-plugins-official/superpowers/*/ 2>/dev/null | head -1)
if [ -n "$SP_DIR" ]; then
    SP_VER=$(basename "$SP_DIR")
    echo "  Superpowers: v$SP_VER"
    echo "  Update: /plugin update superpowers"
else
    echo "  Superpowers: NOT INSTALLED"
    echo "  Install: /plugin marketplace add obra/superpowers-marketplace"
fi

# Claude Code version
echo "  Claude Code: $(claude --version 2>/dev/null || echo 'not in PATH')"
echo "  Update: claude update"

# GitHub MCP
MCP_OK=$(python3 -c "import json; c=json.load(open('$HOME/.claude.json')); print('github' in c.get('mcpServers',{}))" 2>/dev/null)
echo "  GitHub MCP: $( [ "$MCP_OK" = "True" ] && echo 'configured (user scope)' || echo 'NOT CONFIGURED' )"

echo ""
echo "--- USER Components (yours, never overwritten) ---"
echo "  CLAUDE.md: $(wc -l < ~/.claude/CLAUDE.md 2>/dev/null || echo 'MISSING') lines"
echo "  settings.json hooks: $(python3 -c "import json; print(len(json.load(open('$HOME/.claude/settings.json'))['hooks']))" 2>/dev/null || echo 'ERROR') event types"
echo "  Commands: $(ls ~/.claude/commands/*.md 2>/dev/null | wc -l | tr -d ' ') files"
echo "  Rules: $(ls ~/.claude/rules/*.md 2>/dev/null | wc -l | tr -d ' ') files"

echo ""
echo "--- Environment ---"
echo "  gh CLI: $(gh --version 2>/dev/null | head -1 || echo 'not installed')"
echo "  git: $(git --version 2>/dev/null || echo 'not installed')"
echo "  python3: $(python3 --version 2>/dev/null || echo 'not installed')"
echo "  jq: $(jq --version 2>/dev/null || echo 'not installed')"

echo ""
echo "--- Recommendations ---"
if [ "$(python3 -c "import json; print(len(json.load(open('$HOME/.claude/settings.json'))['hooks']))" 2>/dev/null)" -lt 7 ]; then
    echo "  ⚠ Less than 7 hook event types. Run verify.sh to check."
fi
if [ ! -f ~/.claude/protected-patterns.json ]; then
    echo "  ⚠ protected-patterns.json missing. Security patterns not declarative."
fi
if [ ! -f ~/.claude/.env.template ]; then
    echo "  ⚠ .env.template missing. Environment variables not documented."
fi

# Check for unclassified files
MANIFEST="$HOME/.claude/MANIFEST.md"
if [ -f "$MANIFEST" ]; then
    UNCLASSIFIED=0
    for f in "$HOME"/.claude/*; do
        bname=$(basename "$f")
        case "$bname" in
            projects|backups|statsig|*.log|cache|debug|file-history|history.jsonl|ide|paste-cache|plans|shell-snapshots|skills|stats-cache.json|statusline-command.sh|tasks|todos|usage-data|.git|.gitignore|.DS_Store) continue ;;
        esac
        if ! grep -q "$bname" "$MANIFEST" 2>/dev/null; then
            echo "  ⚠ Unclassified file: $bname"
            UNCLASSIFIED=$((UNCLASSIFIED + 1))
        fi
    done
    [ $UNCLASSIFIED -eq 0 ] && echo "  All files classified in MANIFEST.md"
fi

echo ""
echo "Run ~/.claude/verify.sh for full integrity check."
