#!/usr/bin/env bash
set -euo pipefail
REPO_URL=${1:-https://github.com/ahnerjack/nw-api-stack.git}
TARGET=${2:-/opt/nw-api-stack}
if [ -d "$TARGET/.git" ]; then
  git -C "$TARGET" pull --ff-only
else
  git clone "$REPO_URL" "$TARGET"
fi
