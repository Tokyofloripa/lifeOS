---
globs: ["**/*"]
---
# GSD + Superpowers Treaty (Backup Enforcement)

These rules coordinate GSD (macro orchestration) and Superpowers (micro discipline). They apply to ALL projects.

## The 5 Non-Negotiable Rules

1. **One ideation source:** Superpowers brainstorming is the ONLY ideation phase. After brainstorming, treat the design doc (`docs/plans/*-design.md`) as the input spec for GSD. Do NOT re-interview.
2. **One planner:** GSD phase plans are the execution plan of record. Do NOT create parallel Superpowers implementation plans unless user explicitly asks.
3. **One state store:** `.planning/` is canonical. Design docs are references, not project state.
4. **Worktree-first:** Create worktree BEFORE implementation. Use `.worktrees/` directory, gitignored.
5. **Quality gates during GSD execution:** TDD (red → green → refactor) + two-stage review (spec compliance → code quality) + evidence-before-claims. Exception: docs/config only with user approval.

## Mode Auto-Detection

Choose the lightest mode that protects quality:
- Single-file fix (<20 lines) → Superpowers-only
- Multi-file feature (1 session) → Superpowers + /gsd:quick
- Multi-phase work (days) → Full Combined (brainstorm → GSD pipeline)
- Pure docs/config → Lightweight (skip TDD with approval)

## Recovery Protocol

When GSD verification finds gaps:
1. `/gsd:plan-phase N --gaps` → `/gsd:execute-phase N --gaps-only` → `/gsd:verify-work N`
2. After 2 failed cycles, escalate: use `superpowers:systematic-debugging` then `/gsd:debug`

## Context Discipline

- At 50%+ context: write state to `.planning/`, then `/clear` and continue
- `.planning/` is durable memory — `/clear` freely

## Adversarial Loop

After pushing: wait for Copilot auto-review → `/fix-pr-feedback` → fix → push → Copilot re-reviews → human merges.

## Subagent Discipline (Issue #237 mitigation)

When spawning Task agents for implementation, include in the prompt: "Follow TDD discipline (red → green → refactor). Write failing test FIRST. Provide evidence (test output) before claiming completion. Do not skip tests."

## Parallel Execution (Worktree Isolation)

The subagent-driven-dev rule "don't dispatch multiple implementation subagents in parallel" is **LIFTED** when each agent gets its own git worktree. Worktree isolation eliminates file conflicts — the original reason for the restriction.

**Parallel implementation is the DEFAULT** when:
1. Tasks are independent (no data dependencies between them)
2. Each agent has its own worktree + branch
3. Implementation cap: 3 concurrent agents (throttling)

**Merge protocol after parallel agents complete:**
1. Merge each agent's branch into the feature branch sequentially
2. Run full test suite after each merge
3. If merge conflict: stop, report which branches conflict, ask human
4. If tests fail after merge: stop, report which merge broke tests, ask human

**Research, review, and debug agents** do not need worktrees (read-only). Dispatch these with no concurrency limit alongside implementation agents.
