#!/usr/bin/env bash
# Installer for the Sequent pre-commit hook.
#
# Usage:
#   bash hooks/install.sh              # install the hook
#   bash hooks/install.sh --uninstall  # remove the hook

set -euo pipefail

HOOK_SRC="$(cd "$(dirname "$0")" && pwd)/pre-commit"
GIT_DIR="$(git rev-parse --git-dir 2>/dev/null)"

if [ -z "$GIT_DIR" ]; then
    echo "Error: not inside a Git repository." >&2
    exit 1
fi

HOOK_DST="${GIT_DIR}/hooks/pre-commit"

if [ "${1:-}" = "--uninstall" ]; then
    if [ -f "$HOOK_DST" ]; then
        rm "$HOOK_DST"
        echo "Sequent pre-commit hook removed."
    else
        echo "No pre-commit hook found — nothing to remove."
    fi
    exit 0
fi

if [ ! -f "$HOOK_SRC" ]; then
    echo "Error: source hook not found at ${HOOK_SRC}" >&2
    exit 1
fi

mkdir -p "${GIT_DIR}/hooks"
cp "$HOOK_SRC" "$HOOK_DST"
chmod +x "$HOOK_DST"
echo "Sequent pre-commit hook installed to ${HOOK_DST}"
