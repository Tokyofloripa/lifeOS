Create a pull request from the current branch to main.

## Steps

1. Run `git branch --show-current` to confirm you're NOT on main.
   - If on main, STOP and warn: "Create a feature branch first with /branch"
2. Run `git log --oneline main..HEAD` to see all commits that will be in the PR.
3. Run `git diff main...HEAD --stat` to see changed files summary.
4. Check if remote tracking exists: `git rev-parse --abbrev-ref @{upstream} 2>/dev/null`
   - If no upstream, push first: `git push -u origin $(git branch --show-current)`
5. Check for PR template at `.github/pull_request_template.md` — use it if found.
6. Create the PR with `gh pr create`:
   - Title: conventional format matching the primary change (feat/fix/docs/etc), under 70 chars
   - Body: summary bullets + test plan
7. Report the PR URL.
8. Remind: "Copilot will auto-review this PR. After review, use `/fix-pr-feedback` to address any issues."

$ARGUMENTS
