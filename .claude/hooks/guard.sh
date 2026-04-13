#!/usr/bin/env bash
# Claude Code PreToolUse safety guard
# Reads Bash tool input JSON from stdin, blocks destructive commands.
# Exit 0 = allow, Exit 2 = block (with reason on stderr)

INPUT=$(cat)

# Extract the command from JSON — try jq first, fall back to grep
if command -v jq &>/dev/null; then
    COMMAND=$(echo "$INPUT" | jq -r '.tool_input.command // empty')
else
    COMMAND=$(echo "$INPUT" | grep -oP '"command"\s*:\s*"\K[^"]*' 2>/dev/null || echo "")
fi

[ -z "$COMMAND" ] && exit 0

# Destructive patterns to block
BLOCKED_PATTERNS=(
    'rm\s+-[a-zA-Z]*r[a-zA-Z]*f'
    'rm\s+-[a-zA-Z]*f[a-zA-Z]*r'
    'mkfs'
    'dd\s+.*of=/dev/'
    '>\s*/dev/[sh]d'
    'git\s+push\s+.*(-f|--force)'
    'git\s+reset\s+--hard'
    'git\s+clean\s+-[a-zA-Z]*f'
    'git\s+checkout\s+--\s+\.'
    'git\s+restore\s+\.'
    'curl\s+.*\|\s*(ba)?sh'
    'wget\s+.*\|\s*(ba)?sh'
    ':\(\)\s*\{.*\}'
    'shutdown'
    'reboot'
    'init\s+[06]'
)

for pattern in "${BLOCKED_PATTERNS[@]}"; do
    if echo "$COMMAND" | grep -qPi "$pattern"; then
        echo "BLOCKED by safety guard: command matches destructive pattern" >&2
        exit 2
    fi
done

exit 0
