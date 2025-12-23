#!/usr/bin/env bash
set -euo pipefail

cd /opt/highspeed/pux-engine

git fetch origin Staffel1V3
git reset --hard origin/Staffel1V3

/opt/highspeed/pux-engine/.venv/bin/pip install -U streamlit pillow numpy pandas matplotlib requests

sudo systemctl restart highspeed-pux-engine
