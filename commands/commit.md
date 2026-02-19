Review all changes in the current git repo and create a conventional commit.

## Steps

1. Run `git status` to see all modified, staged, and untracked files.
2. Run `git diff` to see unstaged changes and `git diff --cached` to see staged changes.
3. Run `git log --oneline -5` to see recent commit style.
4. Analyze the changes and draft a conventional commit message:
   - Prefix: feat|fix|docs|chore|refactor|test|perf
   - Include scope when relevant: `feat(youtube): add transcript extraction`
   - Subject under 72 characters
   - Body explains WHY, not WHAT
5. Stage relevant files by name — NEVER use `git add -A` or `git add .`
   - Do NOT stage .env files, credentials, or secrets
6. Create the commit.
7. Do NOT push. Only commit locally.

$ARGUMENTS
