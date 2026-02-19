Read Copilot review comments on the current PR and fix issues. This is the dual-model bridge: Claude writes code, Copilot reviews it, Claude fixes the feedback.

## Mode

Check `$ARGUMENTS` for flags:
- Default (no flags): **Interactive** — present findings, ask approval before fixing
- `--auto`: **Automatic** — fix functional+quality issues, commit, push without asking
- A PR number can also be passed: `/fix-pr-feedback 42` or `/fix-pr-feedback 42 --auto`

## Steps

1. **Identify the PR:**
   - If a number is in `$ARGUMENTS`, use that PR number.
   - Otherwise, find the PR for current branch: `gh pr list --head $(git branch --show-current) --json number,title --jq '.[0]'`
   - If no PR found, STOP: "No PR found for this branch. Create one with /pr first."

2. **Read review comments:**
   - Use MCP tool `pull_request_read` with method `get_review_comments` to get all review threads.
   - Also use `pull_request_read` with method `get_reviews` to get overall review summaries.
   - Focus on comments from `copilot[bot]` or `github-actions[bot]`.

3. **Categorize each comment:**
   - **Functional** (MUST FIX): bugs, logic errors, missing edge cases, security issues, incorrect behavior
   - **Quality** (SHOULD FIX): poor naming, missing error handling, missing tests, unclear code, structural issues
   - **Style** (SKIP): formatting preferences, comment style, import ordering, subjective choices

4. **Present findings** (interactive mode):
   - Show a summary table: file, line, category, issue description
   - Show count: "X functional, Y quality, Z style (skipping style)"
   - Ask: "Fix these N issues? (Y/n)"
   - If user says no, stop.

5. **Fix issues:**
   - Read each file mentioned in functional + quality comments.
   - Apply fixes addressing the specific feedback.
   - If a comment is unclear or wrong, note it and skip.

6. **Commit and push:**
   - Stage changed files by name.
   - Commit: `fix: address Copilot review feedback`
   - Push to the same branch.
   - Copilot will automatically re-review the new push.

7. **Report:**
   - "Fixed N issues (X functional, Y quality). Z style comments skipped."
   - "Pushed to branch. Copilot will re-review automatically."
   - If any comments were skipped as unclear: "Skipped N unclear comments — review manually."

$ARGUMENTS
