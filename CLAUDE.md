# Global Claude Code Conventions

## Commit Messages
- Use conventional commits: `feat:`, `fix:`, `docs:`, `chore:`, `refactor:`, `test:`, `perf:`
- Subject line under 72 characters
- Body explains WHY, not WHAT
- Include scope when relevant: `feat(youtube): add transcript extraction`

## Branch Naming
- Feature branches: `feat/short-description`
- Bug fixes: `fix/short-description`
- Documentation: `docs/short-description`
- Always branch from `main`, merge back via PR

## Git Safety
- NEVER force-push to main/master
- NEVER commit .env files or API keys
- Stage specific files by name, not `git add -A`
- Create feature branches for all non-trivial changes

## Workflow
- Use Plan Mode (Shift+Tab) before multi-file changes
- Run tests before committing
- Verify changes work before declaring done
- Use `--mock` mode for development when available

## Code Style
- Python: stdlib only unless project explicitly allows pip deps
- Keep solutions simple — YAGNI
- Fix root causes, not symptoms

## Dual-Model Adversarial Architecture
- Claude (Anthropic) writes code locally. GitHub Copilot (OpenAI/GPT) reviews remotely.
- After pushing a PR, Copilot auto-reviews within minutes. Wait for it.
- Use `/fix-pr-feedback` to read Copilot's comments and fix issues. Use `--auto` for unattended mode.
- Two different AI families checking each other = genuine second opinion.
- Copilot leaves "Comment" reviews only — never approves or blocks. Human is the final gate.

## Enforcement Hierarchy
- **CODE** (hooks in settings.json): deterministic, always fires, can block. Use for: safety, secrets, destructive ops.
- **CLI** (slash commands in commands/): structured workflows, consistent behavior. Use for: git operations, PR workflow, sync.
- **PROMPT** (CLAUDE.md + rules/): probabilistic guidance, degrades at scale. Use for: conventions, preferences, style.
- **SKILL** (skills/*/SKILL.md): AI reasoning with structured workflow. Use for: research, complex multi-step tasks.
- When in doubt: if it MUST happen → hook. If it SHOULD happen → command. If it's preferred → CLAUDE.md. If it needs AI judgment → skill.
