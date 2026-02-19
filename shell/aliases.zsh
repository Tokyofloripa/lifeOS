# Claude Code shell integration
# Source from ~/.zshrc:  source ~/.claude/shell/aliases.zsh

# Quick aliases
alias cc='claude'
alias ccp='claude --print'
alias ccr='claude --resume'

# last60days skill shortcuts
alias l60test='python3 ~/.claude/skills/last60days/scripts/last30days.py "test" --mock --emit=compact'
alias l60diag='python3 ~/.claude/skills/last60days/scripts/last30days.py --diagnose'
alias l60tests='python3 -m pytest ~/.claude/skills/last60days/tests/ -q'

# Worktree helpers
claude-wt() {
  local branch="${1:?Usage: claude-wt <branch-name>}"
  local repo="${2:-$(git rev-parse --show-toplevel 2>/dev/null)}"
  [ -z "$repo" ] && echo "Not in a git repo" && return 1
  local wt_dir="$repo/.worktrees/$branch"
  mkdir -p "$(dirname "$wt_dir")"
  git worktree add "$wt_dir" -b "$branch" 2>/dev/null || git worktree add "$wt_dir" "$branch"
  echo "Worktree ready: $wt_dir"
  echo "  cd $wt_dir && claude"
}

wt-list() {
  git worktree list
}

wt-clean() {
  git worktree prune
  echo "Pruned stale worktrees"
  git worktree list
}

# lifeOS update helper
alias lifeos-update='~/.claude/install.sh'
