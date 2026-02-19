#!/bin/bash
# install.sh — Complete lifeOS bootstrap for Claude Code
# Run after cloning lifeOS or on a new machine
# Usage: git clone --recursive git@github.com:Tokyofloripa/lifeOS.git ~/.claude && ~/.claude/install.sh
# Re-run anytime to update SYSTEM components (idempotent)

set -e

CLAUDE_DIR="$HOME/.claude"

echo "=== lifeOS — Complete Claude Code Bootstrap ==="
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

# --- Initialize submodules (skills) ---
echo "--- Skills (submodules) ---"
if [ -f "$CLAUDE_DIR/.gitmodules" ]; then
    cd "$CLAUDE_DIR"
    git submodule update --init --recursive
    echo "  ✓ Submodules initialized"
    git submodule foreach --quiet 'echo "  ✓ $name: $(git log --oneline -1)"'
    cd - > /dev/null
else
    echo "  ⚠ No .gitmodules found — no skill submodules to initialize"
fi
echo ""

# --- Install pre-commit hook ---
echo "--- Pre-commit Hook ---"
if [ -d "$CLAUDE_DIR/.git" ]; then
    ln -sf "$CLAUDE_DIR/pre-commit-hook.sh" "$CLAUDE_DIR/.git/hooks/pre-commit"
    echo "  ✓ Pre-commit hook installed (symlinked)"
else
    echo "  ⚠ ~/.claude is not a git repo"
fi
echo ""

# --- Install Superpowers plugin ---
echo "--- Superpowers Plugin ---"
SP_DIR=$(ls -d "$CLAUDE_DIR"/plugins/cache/claude-plugins-official/superpowers/*/ 2>/dev/null | head -1)
if [ -n "$SP_DIR" ]; then
    SP_VER=$(basename "$SP_DIR")
    echo "  ✓ Superpowers already installed: v$SP_VER"
else
    echo "  ⚠ Superpowers not installed."
    echo "    Install inside Claude Code: /plugin marketplace add obra/superpowers-marketplace"
fi
echo ""

# --- Configure GitHub MCP ---
echo "--- GitHub MCP ---"
if [ -f "$HOME/.claude.json" ]; then
    MCP_OK=$(python3 -c "import json; print('github' in json.load(open('$HOME/.claude.json')).get('mcpServers',{}))" 2>/dev/null)
    if [ "$MCP_OK" = "True" ]; then
        echo "  ✓ GitHub MCP configured at user scope"
    else
        echo "  ⚠ GitHub MCP not configured. Run inside Claude Code:"
        echo "    claude mcp add github --scope user"
    fi
else
    echo "  ⚠ ~/.claude.json not found — start Claude Code once first"
fi
echo ""

# --- Check secrets setup ---
echo "--- API Keys ---"
ENV_FILE="$HOME/.config/last30days/.env"
if [ -f "$ENV_FILE" ]; then
    echo "  ✓ .env exists at $ENV_FILE"
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

# --- Shell integration ---
echo "--- Shell Integration ---"
ALIASES_FILE="$CLAUDE_DIR/shell/aliases.zsh"
if [ -f "$ALIASES_FILE" ]; then
    if grep -q "source.*aliases.zsh" "$HOME/.zshrc" 2>/dev/null; then
        echo "  ✓ aliases.zsh sourced in ~/.zshrc"
    else
        echo "  Adding source line to ~/.zshrc..."
        echo "" >> "$HOME/.zshrc"
        echo "# Claude Code — lifeOS shell integration" >> "$HOME/.zshrc"
        echo "source $ALIASES_FILE" >> "$HOME/.zshrc"
        echo "  ✓ Added source line to ~/.zshrc"
    fi
else
    echo "  ⚠ shell/aliases.zsh not found"
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
echo "=== Bootstrap Complete ==="
echo ""
echo "Remaining manual steps (if any warnings above):"
echo "  1. Fill in API keys: edit ~/.config/last30days/.env"
echo "  2. Inside Claude Code: /plugin marketplace add obra/superpowers-marketplace"
echo "  3. Inside Claude Code: claude mcp add github --scope user"
echo "  4. Re-run anytime to update: ~/.claude/install.sh (or: lifeos-update)"
