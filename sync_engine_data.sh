#!/bin/bash
# Sync engine data to data repository

echo "🔄 Syncing engine data to data repository..."

# Copy both team files
cp /opt/highspeed/pux-engine/realeTeams_live.py /opt/highspeed/data/engine/
cp /opt/highspeed/pux-engine/realeTeams_web.py /opt/highspeed/data/engine/

# Go to data repo and commit if changed
cd /opt/highspeed/data

CHANGED=false
for file in engine/realeTeams_live.py engine/realeTeams_web.py; do
    if ! git diff --quiet "$file"; then
        CHANGED=true
        break
    fi
done

if [ "$CHANGED" = true ]; then
    echo "📝 Changes detected, committing..."
    git add engine/realeTeams_live.py engine/realeTeams_web.py
    git commit -m "Sync engine teams data - $(date '+%Y-%m-%d %H:%M')"
    git push origin dev
    echo "✅ Engine data synced and pushed"
else
    echo "✅ No changes to sync"
fi
