Push the current branch to origin.

## Steps

1. Run `git branch --show-current` to get current branch name.
2. If on main or master, STOP and warn: "You are on main. Do NOT push directly. Create a feature branch with /branch."
3. Check for unpushed commits: `git log @{upstream}..HEAD --oneline 2>/dev/null`
   - If no upstream, this is the first push.
4. NEVER use `--force` or `-f` flags.
5. Push:
   - First push: `git push -u origin $(git branch --show-current)`
   - Subsequent: `git push`
6. Report what was pushed.

$ARGUMENTS
