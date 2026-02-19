#!/bin/bash
# Pre-commit hook: scan staged files against protected-patterns.json v2 schema
# Install: ln -sf ~/.claude/pre-commit-hook.sh .git/hooks/pre-commit

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

FOUND=0

# Extract patterns from v2 schema using python3 (stdlib-only)
SCAN_RESULT=$(python3 -c "
import json, re, subprocess, sys

patterns_file = '$PATTERNS_FILE'
data = json.load(open(patterns_file))

# Get staged file contents via git show
def get_staged_content(filepath):
    try:
        result = subprocess.run(['git', 'show', ':' + filepath],
                              capture_output=True, text=True, timeout=5)
        return result.stdout if result.returncode == 0 else ''
    except Exception:
        return ''

def is_binary(filepath):
    try:
        result = subprocess.run(['file', filepath],
                              capture_output=True, text=True, timeout=5)
        return 'binary' in result.stdout.lower()
    except Exception:
        return False

staged_files = '''$STAGED'''.strip().split('\n')
found = 0

# Check blocked paths
for f in staged_files:
    for p in data.get('blocked_paths', {}).get('patterns', []):
        if re.search(p['regex'], f):
            print(f'BLOCKED PATH: {f} matches \"{p[\"name\"]}\"', file=sys.stderr)
            found += 1

# Check secrets and PII in file contents
for section_name in ['secrets', 'pii']:
    section = data.get(section_name, {})
    label = 'SECRET' if section_name == 'secrets' else 'PII'
    for f in staged_files:
        if is_binary(f):
            continue
        content = get_staged_content(f)
        if not content:
            continue
        for p in section.get('patterns', []):
            try:
                if re.search(p['regex'], content):
                    print(f'{label} DETECTED in {f}: matches \"{p[\"name\"]}\" [{p.get(\"severity\", \"unknown\")}]', file=sys.stderr)
                    found += 1
            except re.error:
                pass

print(found)
" 2>&1)

# The last line of output is the count; everything before goes to stderr
FOUND=$(echo "$SCAN_RESULT" | tail -1)
MESSAGES=$(echo "$SCAN_RESULT" | sed '$d')

if [ -n "$MESSAGES" ]; then
    echo "$MESSAGES" >&2
fi

if [ "$FOUND" -gt 0 ] 2>/dev/null; then
    echo "" >&2
    echo "BLOCKED: $FOUND security issue(s) found in staged files." >&2
    echo "Remove secrets/PII before committing. See ~/.claude/protected-patterns.json for patterns." >&2
    echo "To bypass (NOT RECOMMENDED): git commit --no-verify" >&2
    exit 1
fi

exit 0
