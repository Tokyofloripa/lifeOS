#!/bin/bash
# install.sh — Verify and finalize Claude Code configuration
# Run after cloning lifeOS or on a new machine
# Usage: ~/.claude/install.sh

set -e

CLAUDE_DIR="$HOME/.claude"

echo "=== lifeOS Claude Config — Setup ==="
echo ""

# --- Check prerequisites ---
echo "--- Prerequisites ---"
MISSING=0
for cmd in git gh python3 jq; do
    if command -v "$cmd" > /dev/null 2>&1; then
        echo "  ✓ $cmd: $(command -v "$cmd")"
    else
        echo "  ✗ $cmd: NOT FOUND"
        MISSING=$((MISSING + 1))
    fi
done

if command -v claude > /dev/null 2>&1; then
    echo "  ✓ claude: $(claude --version 2>/dev/null || echo 'installed')"
else
    echo "  ⚠ claude: not in PATH (install: npm install -g @anthropic-ai/claude-code)"
fi

if [ $MISSING -gt 0 ]; then
    echo ""
    echo "Install missing prerequisites before continuing."
    exit 1
fi
echo ""

# --- Install pre-commit hook ---
echo "--- Pre-commit Hook ---"
if [ -d "$CLAUDE_DIR/.git" ]; then
    ln -sf "$CLAUDE_DIR/pre-commit-hook.sh" "$CLAUDE_DIR/.git/hooks/pre-commit"
    echo "  ✓ Pre-commit hook installed (symlinked)"
else
    echo "  ⚠ ~/.claude is not a git repo — run 'cd ~/.claude && git init' first"
fi
echo ""

# --- Check secrets setup ---
echo "--- API Keys ---"
ENV_FILE="$HOME/.config/last30days/.env"
if [ -f "$ENV_FILE" ]; then
    echo "  ✓ .env exists at $ENV_FILE"
    # Check required keys without printing values
    for key in OPENAI_API_KEY XAI_API_KEY; do
        if grep -q "^${key}=." "$ENV_FILE" 2>/dev/null; then
            echo "  ✓ $key is set"
        else
            echo "  ⚠ $key is empty or missing"
        fi
    done
else
    echo "  ⚠ No .env found. Set up:"
    echo "    mkdir -p ~/.config/last30days"
    echo "    cp $CLAUDE_DIR/.env.template ~/.config/last30days/.env"
    echo "    # Then fill in your API keys"
fi
echo ""

# --- Check MCP ---
echo "--- MCP Servers ---"
if [ -f "$HOME/.claude.json" ]; then
    MCP_OK=$(python3 -c "import json; print('github' in json.load(open('$HOME/.claude.json')).get('mcpServers',{}))" 2>/dev/null)
    if [ "$MCP_OK" = "True" ]; then
        echo "  ✓ GitHub MCP configured at user scope"
    else
        echo "  ⚠ GitHub MCP not configured. Run:"
        echo "    claude mcp add github --scope user"
    fi
else
    echo "  ⚠ ~/.claude.json not found"
fi
echo ""

# --- Run verification ---
echo "--- Running Full Verification ---"
echo ""
if [ -x "$CLAUDE_DIR/verify.sh" ]; then
    "$CLAUDE_DIR/verify.sh"
else
    echo "  ⚠ verify.sh not found or not executable"
fi

echo ""
echo "=== Setup Complete ==="
echo ""
echo "Next steps (if any warnings above):"
echo "  1. Fill in API keys: edit ~/.config/last30days/.env"
echo "  2. Configure MCP: claude mcp add github --scope user"
echo "  3. Install Superpowers: /plugin marketplace add obra/superpowers-marketplace"
echo "  4. Fill in identity: edit ~/.claude/rules/identity.md"
