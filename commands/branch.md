Create a feature branch from main.

## Steps

1. Parse `$ARGUMENTS` for the branch description.
   - If no arguments, ask the user what they're working on.
2. Determine the branch type from the description:
   - New feature → `feat/`
   - Bug fix → `fix/`
   - Documentation → `docs/`
   - Chore/config → `chore/`
   - Refactor → `refactor/`
3. Generate branch name: `<type>/<short-kebab-description>` (e.g., `feat/add-search-filter`)
4. Ensure main is up to date: `git fetch origin main`
5. Create and switch: `git checkout -b <branch-name> origin/main`
6. Confirm: "Created branch `<branch-name>` from main. Ready to work."

$ARGUMENTS
