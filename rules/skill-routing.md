---
globs: ["**/*"]
---
# Skill Routing Table

When the user's intent matches a pattern below, invoke the corresponding skill BEFORE any other action. This is a PROMPT-level guide (see Enforcement Hierarchy in CLAUDE.md). The skill-forced-eval hook provides CODE-level enforcement in the cc/ project.

## Priority 1 — Process Skills (determine HOW to approach)

| User Intent | Skill/Command | Trigger Words |
|------------|---------------|---------------|
| Research a topic (ultra-comprehensive) | last60days | "research", "what are people saying", "last 60 days", "trending", "deep research", "comprehensive search" |
| Creating features, adding functionality | superpowers:brainstorming | "add", "create", "build", "implement" (new things) |
| Bug, test failure, unexpected behavior | superpowers:systematic-debugging | "bug", "failing", "broken", "error", "doesn't work" |
| Writing implementation plans | superpowers:writing-plans | "plan", "design", "architect" (before coding) |

## Priority 2 — Execution Skills + GSD Pipeline

| User Intent | Skill/Command | Trigger Words |
|------------|---------------|---------------|
| Executing a written plan (this session) | superpowers:subagent-driven-development | "implement these tasks", "execute in parallel" |
| Executing a written plan (separate session) | superpowers:executing-plans | "execute the plan", "implement the plan" |
| Feature work needing isolation | superpowers:using-git-worktrees | "worktree", "isolated branch" |
| Implementing any feature (TDD) | superpowers:test-driven-development | (after brainstorming, during implementation) |
| Initialize new multi-phase project | /gsd:new-project | "new project", "start project", "initialize GSD" |
| Map existing codebase | /gsd:map-codebase | "map codebase", "analyze codebase", "brownfield" |
| Plan a phase | /gsd:plan-phase | "plan phase", "create phase plan" |
| Execute a phase | /gsd:execute-phase | "execute phase", "run phase", "build phase" |
| Quick structured task | /gsd:quick | "quick task", "fast fix with tracking" |

## Priority 3 — Verification + Workflow Commands

| User Intent | Skill/Command | Trigger Words |
|------------|---------------|---------------|
| Verify phase work | /gsd:verify-work | "verify work", "check phase", "UAT" |
| Debug persistent issue | /gsd:debug | "debug", "persistent bug", "root cause" (after 2 failed fix cycles) |
| Read + fix Copilot review | fix-pr-feedback | "fix PR feedback", "Copilot comments", "review comments" |
| Commit changes | commit | "commit", "/commit" |
| Create pull request | pr | "create PR", "pull request", "/pr" |
| Push to remote | push | "push", "/push" |
| Create branch | branch | "new branch", "/branch" |

## Priority 4 — Completion + Milestone Commands

| User Intent | Skill/Command | Trigger Words |
|------------|---------------|---------------|
| Work is done, verify before claiming | superpowers:verification-before-completion | "done", "finished", "complete" (before committing) |
| Request code review | superpowers:requesting-code-review | "review my code", "check my work" |
| Branch ready to merge | superpowers:finishing-a-development-branch | "ready to merge", "finish this branch" |
| Audit milestone completion | /gsd:audit-milestone | "audit milestone", "check milestone" |
| Archive and complete milestone | /gsd:complete-milestone | "complete milestone", "archive milestone", "ship milestone" |
| Discuss next milestone | /gsd:new-milestone | "next milestone", "new milestone", "what's next" |
| Check project progress | /gsd:progress | "progress", "where are we", "project status" |
| Context feels bloated | /clear + resume via .planning/ | "bloated", "context is large", "need to clear" |

## Routing Rules

1. If the user explicitly names a skill or command, use that — don't second-guess.
2. If the intent is ambiguous, ask for clarification rather than guessing wrong.
3. Skills can chain: a "fix PR feedback" session may end with /commit and /push.
4. When no skill matches, proceed normally — not every task needs routing.
5. This table is PROMPT-level guidance. The PreToolUse hook (CODE-level) overrides if there's a conflict.
6. **Mode auto-detection:** For multi-phase work, suggest Combined mode. For single-session features, suggest Superpowers + /gsd:quick. For quick fixes, suggest Superpowers-only.
7. **GSD → Superpowers handoff:** After `/brainstorm` produces a design doc, transition to GSD with: "Use docs/plans/<date>-design.md as the spec."

## ISC Templates (verification criteria)

| Skill/Command | Success Criteria (binary-testable) |
|---------------|-----------------------------------|
| last60days | Research output contains three or more sources |
| superpowers:brainstorming | Brainstorm produced three or more distinct approaches |
| fix-pr-feedback | All Copilot review comments addressed with changes |
| /commit | Commit message follows conventional commit format |
| /pr | PR created with description and Copilot review requested |
| /gsd:plan-phase | Phase plan created with atomic tasks in .planning/ |
| /gsd:execute-phase | All plans executed, tests pass |
| /gsd:verify-work | Verification checklist completed, gaps identified or zero |
