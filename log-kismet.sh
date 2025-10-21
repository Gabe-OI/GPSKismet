#!/bin/bash

WORK_DIR="/home/droneman/GPSKismet" #Replace droneman with your username (if applicable)
FINAL_CSV="$WORK_DIR/GPSKismet.csv"
LOG_SCRIPT="$WORK_DIR/kismet-to-csv.py"

sleep 3

# Run log formatting Python script, if not present then exit
if [[ -f "$LOG_SCRIPT" ]]; then
    echo "[INFO] Running log formatting script..."
    python3 "$LOG_SCRIPT" *.kismet "$FINAL_CSV"
else
    echo "[ERROR] Log script not found: $LOG_SCRIPT"
    exit 1
fi

# Check for GPSKismet.csv and display corresponding message
if [ -e "$FINAL_CSV" ]; then
    echo "[SUCCESS] $FINAL_CSV created."
    exit 0
else
    echo "[ERROR] $FINAL_CSV could not be made."
    exit 1
fi
