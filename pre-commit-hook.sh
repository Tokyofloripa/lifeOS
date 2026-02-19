#!/bin/bash
# Pre-commit hook: scan staged files for secrets using protected-patterns.json
# Install: cp ~/.claude/pre-commit-hook.sh .git/hooks/pre-commit && chmod +x .git/hooks/pre-commit
# Or symlink: ln -sf ~/.claude/pre-commit-hook.sh .git/hooks/pre-commit

set -e

PATTERNS_FILE="$HOME/.claude/protected-patterns.json"

# Skip if no patterns file
if [ ! -f "$PATTERNS_FILE" ]; then
    echo "Warning: $PATTERNS_FILE not found, skipping secret scan" >&2
    exit 0
fi

# Skip in CI (CI has its own scanning)
[ -n "$CI" ] && exit 0

# Get staged files (only added/modified, not deleted)
STAGED=$(git diff --cached --name-only --diff-filter=ACM 2>/dev/null)
[ -z "$STAGED" ] && exit 0

# Extract secret patterns from JSON
PATTERNS=$(python3 -c "
import json, sys
try:
    d = json.load(open('$PATTERNS_FILE'))
    for p in d.get('secret_patterns', []):
        print(p)
except Exception:
    sys.exit(0)
" 2>/dev/null)

[ -z "$PATTERNS" ] && exit 0

FOUND=0

for file in $STAGED; do
    # Skip binary files
    if file "$file" 2>/dev/null | grep -q "binary"; then
        continue
    fi

    while IFS= read -r pattern; do
        if git show ":$file" 2>/dev/null | grep -qE "$pattern"; then
            echo "SECRET DETECTED in $file: matches pattern '$pattern'" >&2
            FOUND=$((FOUND + 1))
        fi
    done <<< "$PATTERNS"
done

if [ $FOUND -gt 0 ]; then
    echo "" >&2
    echo "BLOCKED: $FOUND secret pattern(s) found in staged files." >&2
    echo "Remove secrets before committing. See ~/.claude/protected-patterns.json for patterns." >&2
    exit 1
fi

exit 0
