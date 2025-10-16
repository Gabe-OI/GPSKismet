#!/bin/bash
set -e
set -x

IFACE="wlxa0d768212c6d" # Replace with Wifi adapter interface id
SCRIPT="/home/droneman/GPSKismet/mavlink-to-kismet.py" # Replace droneman with your username (if applicable)
PTY_FILE="/tmp/mavlink_pty_path"

# Clean up old PTY file if it exists
rm -f "$PTY_FILE"

# Set up Wifi interface for monitor mode
nmcli device set "$IFACE" managed no
ip link set "$IFACE" down
iw dev "$IFACE" set type monitor
ip link set "$IFACE" up

# Launch the Python bridge in the background
"$SCRIPT" &
MAV_PID=$!

# Wait for the PTY file to appear
TIMEOUT=10
while [ $TIMEOUT -gt 0 ]; do
    if [ -s "$PTY_FILE" ]; then
        PTY=$(cat "$PTY_FILE")
        echo "Detected PTY: $PTY"
        break
    fi
    sleep 1
    TIMEOUT=$((TIMEOUT - 1))
done

if [ -z "${PTY:-}" ]; then
    echo "Error: PTY not created by Python script within timeout"
    kill "$MAV_PID" || true
    exit 1
fi

# Start gpsd on the PTY in the background
exec gpsd -N -D 2 "$PTY" -F /tmp/gpsd.sock &
GPSD_PID=$!

# Launch Kismet in the foreground
exec kismet -c "$IFACE"

# Cleanup on exit
kill "$GPSD_PID" "$MAV_PID" 2>/dev/null || true
