#!/usr/bin/env bash
set -euo pipefail

cd /opt/highspeed/pux-engine

BRANCH="Staffel1V3"
FLAG="/tmp/pux_engine_updated.flag"
rm -f "$FLAG"

git fetch origin "$BRANCH" --quiet

LOCAL="$(git rev-parse HEAD)"
REMOTE="$(git rev-parse origin/$BRANCH)"

if [[ "$LOCAL" == "$REMOTE" ]]; then
  echo "✅ No update needed ($LOCAL)"
  exit 0
fi

echo "🔄 Updating PUX Engine $LOCAL -> $REMOTE"
git checkout "$BRANCH" --quiet
git reset --hard "origin/$BRANCH" --quiet

touch "$FLAG"
echo "✅ Updated to $(git rev-parse --short HEAD)"
