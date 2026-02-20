#!/usr/bin/env bash
# Weekly rankings refresh for Shukketsu Raid Analyzer
# Pulls top 100 DPS+HPS rankings and speed rankings for all P1 encounters.
# Scheduled via cron: 0 3 * * 0 (Sunday 3:00 AM)

set -euo pipefail

LOGDIR="/home/lyro/nvidia-workbench/wcl-tbc-analyzer/data/scratch/logs"
mkdir -p "$LOGDIR"
LOGFILE="$LOGDIR/rankings-$(date +%Y%m%d).log"

# Source env vars
set -a
source /home/lyro/nvidia-workbench/wcl-tbc-analyzer/.env
set +a

export PATH="/home/lyro/.local/bin:$PATH"

echo "=== Weekly rankings pull started at $(date) ===" >> "$LOGFILE"

echo "--- Speed rankings ---" >> "$LOGFILE"
pull-speed-rankings --force >> "$LOGFILE" 2>&1

echo "--- Top rankings (DPS + HPS) ---" >> "$LOGFILE"
pull-rankings --include-hps --force >> "$LOGFILE" 2>&1

echo "=== Completed at $(date) ===" >> "$LOGFILE"
