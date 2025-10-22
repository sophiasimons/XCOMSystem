#!/usr/bin/env zsh
# Simple helper to package the Electron app on macOS using electron-packager
set -euo pipefail
DIR=$(cd "$(dirname "$0")/.." && pwd)
cd "$DIR/desktop-electron"

# Ensure electron-packager is installed (global or local)
if ! command -v npx >/dev/null 2>&1; then
  echo "npx is required (install Node.js/npm)" >&2
  exit 1
fi

npx electron-packager . xcom-desktop --platform=darwin --arch=x64 --overwrite
echo "Packaged app in current folder"
