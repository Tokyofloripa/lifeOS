# Global Slash Commands

Available from any directory in Claude Code. These are USER files (never overwritten by upgrades).

| Command | Version | Purpose | Dependencies | Determinism |
|---------|---------|---------|-------------|-------------|
| `/commit` | 1.0 | Review changes, conventional commit, stage by name, never push | git | CLI |
| `/pr` | 1.0 | Create PR from branch to main, check template, Copilot reminder | git, gh | CLI |
| `/branch` | 1.0 | Create feature branch from main with naming conventions | git | CLI |
| `/push` | 1.0 | Push current branch, set upstream, warn on main, never force | git | CLI |
| `/fix-pr-feedback` | 1.0 | Read Copilot review via MCP, categorize, fix functional+quality, skip style | git, gh, MCP (github) | CLI + SKILL |

## Modes

- `/fix-pr-feedback` — default: interactive. `--auto`: unattended fix+push.
- `/fix-pr-feedback 42` — target specific PR number.
- `/branch add search filter` — accepts description as argument.

## Adding New Commands

1. Create `~/.claude/commands/{name}.md`
2. Add entry to the table above
3. Add check to `verify.sh`
4. Commit via PR — Copilot reviews the command content
5. Test: run `/{name}` in a Claude Code session

## Command Design Rules

- Commands are CLI-level in the enforcement hierarchy
- Commands should be idempotent where possible
- Commands should never contain secrets (use $ENV_VAR references)
- Commands should fail loudly rather than silently succeed

## Enforcement Hierarchy

These commands are CLI-level (structured workflows). For enforcement, see hooks in `settings.json`. For guidance, see `CLAUDE.md`.
