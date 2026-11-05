#!/usr/bin/env bash
# One-command demo. Live public data by default; `./demo.sh replay` runs offline from the recorded real snapshot.
set -e; cd "$(dirname "$0")"
if [ "$1" = "replay" ]; then
  python3 agent.py --replay fixtures/snapshot_2026-11-05.json --bankroll 1000 --min-edge 0.05 --top 5 --out proposals.json
else
  python3 agent.py --bankroll 1000 --min-edge 0.05 --top 5 --out proposals.json
fi
python3 paper.py open proposals.json
python3 paper.py mark
