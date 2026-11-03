#!/usr/bin/env bash
# One-command demo: dry-run scan with a $1,000 paper bankroll.
set -e; cd "$(dirname "$0")"
python3 agent.py --bankroll 1000 --min-edge 0.05 --top 5 --out proposals.json
