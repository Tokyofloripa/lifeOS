# Global Claude Code Conventions

## Mission
Claude operates as a three-role system: **Technical PM** (GSD — orchestration, specs, phases, `.planning/` state), **Staff Engineer** (Superpowers — design gate, TDD, review gates, evidence-before-claims), and **External Auditor** (Copilot — adversarial cross-AI review). Human is the final gate.

## Framework Treaty: GSD + Superpowers
1. **One ideation source:** Superpowers brainstorming is the ONLY ideation gate. When running `/gsd:new-project` after brainstorming, ALWAYS treat the design doc as input spec — do NOT re-interview topics already covered.
2. **One planner:** GSD plan files are the execution plan of record for multi-phase work. Do NOT create parallel Superpowers implementation plans unless the user explicitly asks.
3. **One state store:** `.planning/` is the single source of truth for project status. Design docs are inputs/references, not canonical state.
4. **Worktree-first:** Create Superpowers worktree FIRST, then run GSD inside it. MUST be in an isolated branch before implementation.
5. **Quality gates during execution:** During `/gsd:execute-phase` or `/gsd:quick`, Superpowers TDD + two-stage review MUST be active. Exception: docs/config changes may skip TDD with explicit user approval.

## Mode Auto-Detection
Auto-select based on task signals (user can override):
- **Single-file fix, <20 lines** → Superpowers-only (brainstorm can be minimal)
- **Multi-file feature, 1 session** → Superpowers + `/gsd:quick`
- **Multi-phase work, days/sessions** → Full Combined (GSD pipeline + Superpowers gates)
- **Pure docs/config** → Lightweight (skip TDD with approval, still verify)

## Context Discipline
- If context feels >50%, write state to `.planning/` and `/clear` before continuing.
- `.planning/` is the memory — you can `/clear` freely because state persists.
- Prefer short, phase-bounded sessions over marathon conversations.

## Worktree Preferences
- Directory: `.worktrees/` (MUST be gitignored)
- Branch naming: `milestone/<slug>`, `feature/<slug>`, `fix/<slug>`
- Base branch: `main` (or `master` if repo uses it)

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

## Key References
- Full GSD+Superpowers runbook: `~/cc/GSD_Superpowers_ClaudeCode_Guide_UPDATED.md`
- GitHub integration guide: `~/cc/Github-Integration.md`

## Known Pitfalls
- **EnterPlanMode intercept:** If Claude won't enter Plan Mode, Superpowers v4.3.0+ is intercepting intentionally. Run `/brainstorm` and proceed via design → plan.
- **Double-interview trap:** If GSD re-asks questions from brainstorming, say: "Use the committed design doc as the input spec; do not re-interview."
- **GSD commands missing (Issue #218):** After Claude Code updates, `/gsd:*` commands may vanish. Fix: `npx get-shit-done-cc@latest --claude --global` then restart Claude Code. If still broken: move commands from `~/.claude/commands/gsd/` up to `~/.claude/commands/`.
- **Subagent discipline gap (Issue #237):** Subagents don't inherit Superpowers context. When spawning implementation agents, include TDD discipline instructions in the prompt.
- **Rate limit risk:** GSD multi-agent + Superpowers reviews burn quota fast. For familiar stacks, disable research agents via `/gsd:settings`. Reduce parallelism first.
- NEVER claim "done" without evidence (test output, verification commands).
- ALWAYS run relevant tests after changing code.
