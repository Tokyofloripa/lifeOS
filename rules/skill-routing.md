---
globs: ["**/*"]
---
# Skill Routing Table

When the user's intent matches a pattern below, invoke the corresponding skill BEFORE any other action. This is a PROMPT-level guide (see Enforcement Hierarchy in CLAUDE.md). The skill-forced-eval hook provides CODE-level enforcement in the cc/ project.

## Priority 1 — Process Skills (determine HOW to approach)

| User Intent | Skill to Invoke | Trigger Words |
|------------|----------------|---------------|
| Research a topic from recent discussions | last30days | "research", "what are people saying", "last 30 days", "trending" |
| Ultra-comprehensive multi-source research | last30dayshigh | "deep research", "comprehensive search", "exhaustive", "/last30dayshigh" |
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
