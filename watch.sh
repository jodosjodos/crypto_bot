#!/bin/bash
# Live bot monitor — refreshes every 15 seconds
# Run: bash watch.sh

cd /Users/jodos/Documents/codes/EXPERIMENTS/bots
source venv/bin/activate

while true; do
    clear
    echo "  Last updated: $(date '+%H:%M:%S')  (refreshes every 15s — press Ctrl+C to stop)"
    echo ""
    python3 status.py
    echo ""
    echo "  ── Recent activity ──────────────────────────────────"
    tail -6 trades.log | grep -v "^$" | sed 's/^/  /'
    sleep 15
done
