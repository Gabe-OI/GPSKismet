#!/bin/bash
set -e
set -x

IFACE="wlxa0d768212c6d" # Replace with Wifi adapter interface ID
WORK_DIR="/home/droneman/GPSKismet" # Replace droneman with your username (if applicable)
BRIDGE_SCRIPT="$WORK_DIR/mavlink-to-kismet.py"
PTY_FILE="/tmp/mavlink_pty_path"

# Clean up old PTY file if it exists
rm -f "$PTY_FILE"

# Clean up old logs if they exist
rm -f "$WORK_DIR"/*.kismet "$WORK_DIR"/*.csv

# Launch the bridge script in the background
"$BRIDGE_SCRIPT" &
BRIDGE_PID=$!

# Wait for the PTY file to appear
TIMEOUT=10
while [ $TIMEOUT -gt 0 ]; do
    if [ -s "$PTY_FILE" ]; then
        PTY=$(cat "$PTY_FILE")
        echo "[INFO] Detected PTY: $PTY"
        break
    fi
    sleep 1
    TIMEOUT=$((TIMEOUT - 1))
done

if [ -z "${PTY:-}" ]; then
    echo "[ERROR] PTY not created by Python script within timeout."
    kill "$MAV_PID" || true
    exit 1
fi

# Start gpsd on the PTY in the background
exec gpsd -N -D 2 "$PTY" -F /tmp/gpsd.sock &
GPSD_PID=$!

# Launch Kismet in the foreground
exec kismet -c "$IFACE" --config /etc/kismet/kismet.conf &
KISMET_PID=$!

# Wait for Kismet to exit
wait "$KISMET_PID"

# Cleanup on exit
kill "$GPSD_PID" "$BRIDGE_PID" 2>/dev/null || true
