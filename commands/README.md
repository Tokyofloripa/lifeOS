# Global Slash Commands

Available from any directory in Claude Code. These are USER files (never overwritten by upgrades).

| Command | Version | Purpose | Dependencies |
|---------|---------|---------|-------------|
| `/commit` | 1.0 | Review changes, conventional commit, stage by name, never push | git |
| `/pr` | 1.0 | Create PR from branch to main, check template, Copilot reminder | git, gh |
| `/branch` | 1.0 | Create feature branch from main with naming conventions | git |
| `/push` | 1.0 | Push current branch, set upstream, warn on main, never force | git |
| `/fix-pr-feedback` | 1.0 | Read Copilot review via MCP, categorize, fix functional+quality, skip style | git, gh, MCP (github) |

## Modes

- `/fix-pr-feedback` — default: interactive. `--auto`: unattended fix+push.
- `/fix-pr-feedback 42` — target specific PR number.
- `/branch add search filter` — accepts description as argument.

## Enforcement Hierarchy

These commands are CLI-level (structured workflows). For enforcement, see hooks in `settings.json`. For guidance, see `CLAUDE.md`.
