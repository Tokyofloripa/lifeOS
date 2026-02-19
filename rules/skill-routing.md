---
globs: ["**/*"]
---
# Skill Routing Table

When the user's intent matches a pattern below, invoke the corresponding skill BEFORE any other action. This is a PROMPT-level guide (see Enforcement Hierarchy in CLAUDE.md). The skill-forced-eval hook provides CODE-level enforcement in the cc/ project.

## Priority 1 — Process Skills (determine HOW to approach)

| User Intent | Skill to Invoke | Trigger Words |
|------------|----------------|---------------|
| Research a topic (ultra-comprehensive by default) | last30days | "research", "what are people saying", "last 30 days", "trending", "deep research", "comprehensive search" |
| Creating features, adding functionality | superpowers:brainstorming | "add", "create", "build", "implement" (new things) |
| Bug, test failure, unexpected behavior | superpowers:systematic-debugging | "bug", "failing", "broken", "error", "doesn't work" |
| Writing implementation plans | superpowers:writing-plans | "plan", "design", "architect" (before coding) |

## Priority 2 — Implementation Skills (guide execution)

| User Intent | Skill to Invoke | Trigger Words |
|------------|----------------|---------------|
| Executing a written plan | superpowers:executing-plans | "execute the plan", "implement the plan" |
| Multiple independent tasks in this session | superpowers:subagent-driven-development | "implement these tasks", "execute in parallel" |
| Feature work needing isolation | superpowers:using-git-worktrees | "worktree", "isolated branch" |
| Implementing any feature (TDD) | superpowers:test-driven-development | (after brainstorming, during implementation) |

## Priority 3 — Workflow Commands (structured operations)

| User Intent | Skill to Invoke | Trigger Words |
|------------|----------------|---------------|
| Read + fix Copilot review | fix-pr-feedback | "fix PR feedback", "Copilot comments", "review comments" |
| Commit changes | commit | "commit", "/commit" |
| Create pull request | pr | "create PR", "pull request", "/pr" |
| Push to remote | push | "push", "/push" |
| Create branch | branch | "new branch", "/branch" |

## Priority 4 — Completion Skills (quality gates)

| User Intent | Skill to Invoke | Trigger Words |
|------------|----------------|---------------|
| Work is done, verify before claiming complete | superpowers:verification-before-completion | "done", "finished", "complete" (before committing) |
| Request code review | superpowers:requesting-code-review | "review my code", "check my work" |
| Branch ready to merge | superpowers:finishing-a-development-branch | "ready to merge", "finish this branch" |

## Routing Rules

1. If the user explicitly names a skill or command, use that — don't second-guess.
2. If the intent is ambiguous, ask for clarification rather than guessing wrong.
3. Skills can chain: a "fix PR feedback" session may end with /commit and /push.
4. When no skill matches, proceed normally — not every task needs routing.
5. This table is PROMPT-level guidance. The PreToolUse hook (CODE-level) overrides if there's a conflict.

## ISC Templates (verification criteria)

| Skill | Success Criteria (binary-testable) |
|-------|-----------------------------------|
| last30days | Research output contains three or more sources |
| superpowers:brainstorming | Brainstorm produced three or more distinct approaches |
| fix-pr-feedback | All Copilot review comments addressed with changes |
| /commit | Commit message follows conventional commit format |
| /pr | PR created with description and Copilot review requested |
