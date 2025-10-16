#!/usr/bin/env python3
"""
MAVLink to NMEA GPS Bridge
-Configures Mavlink for communication with CubePilot
-Launches PTY for gpsd transmission
-Converts raw data from MAVLink into gpsd-readable format
-Sends formatted messages through gpsd to be read by Kismet
"""

import os
import pty
import time
from pymavlink import mavutil

# --------------------------------
# Network Setup
# --------------------------------

# MAVLink connection string
MAVLINK_SOURCE = "udpin:127.0.0.1:14560"  # Adjust to IP & port in MAVLink config

# Serial speed (for PTY emulation)
SERIAL_BAUD = 4800

# Create a PTY for gpsd
master_fd, slave_fd = pty.openpty()
slave_name = os.ttyname(slave_fd)
print(f"PTY created: {slave_name}")

# Write PTY path to a temp file for wrapper
with open("/tmp/mavlink_pty_path", "w") as f:
    f.write(slave_name)

# Make it readable/writable by gpsd for running as root
os.chmod(slave_name, 0o666)

# Connect to MAVLink
print(f"Connecting to MAVLink source: {MAVLINK_SOURCE} ...")
mav = mavutil.mavlink_connection(MAVLINK_SOURCE)

# Wait for heartbeat to confirm connection
mav.wait_heartbeat()
print("MAVLink heartbeat received!")

# --------------------------------
# Convert Raw Data to NMEA GGA/RMC
# --------------------------------
_speed_ema = 0.0

def gps_raw_to_nmea(msg):
    global _speed_ema

    # Latitude/longitude in degrees
    lat = msg.lat / 1e7
    lon = msg.lon / 1e7
    alt = msg.alt / 1000.0  # mm -> m

    # UTC timestamp
    t = time.gmtime()

    # Speed smoothing
    raw_ms = getattr(msg, "vel", 0) / 100.0  # cm/s → m/s
    if raw_ms < 0.2:  # Eliminate tiny jitter
        raw_ms = 0.0

    alpha = 0.25  # Smoothing factor (0-1); higher = more responsive
    _speed_ema = alpha * raw_ms + (1 - alpha) * _speed_ema
    smooth_knots = _speed_ema * 1.94384  # m/s -> kts

    # Build GPGGA
    gga = (
        f"$GPGGA,{t.tm_hour:02}{t.tm_min:02}{t.tm_sec:02},"
        f"{abs(lat):02.5f},{'N' if lat >= 0 else 'S'},"
        f"{abs(lon):03.5f},{'E' if lon >= 0 else 'W'},"
        f"1,08,0.9,{alt:.1f},M,0.0,M,,"
    )
    gga += f"*{calculate_nmea_checksum(gga)}\r\n"

    # Build GPRMC
    rmc = (
        f"$GPRMC,{t.tm_hour:02}{t.tm_min:02}{t.tm_sec:02},A,"
        f"{abs(lat):02.5f},{'N' if lat >= 0 else 'S'},"
        f"{abs(lon):03.5f},{'E' if lon >= 0 else 'W'},"
        f"{smooth_knots:.1f},0.0,"
        f"{t.tm_mday:02}{t.tm_mon:02}{t.tm_year%100:02},,,A"
    )
    rmc += f"*{calculate_nmea_checksum(rmc)}\r\n"

    return gga, rmc

# --------------------------------
# NMEA Checksum Helper
# --------------------------------
def calculate_nmea_checksum(sentence):
    cksum = 0
    for c in sentence[1:]:
        cksum ^= ord(c)
    return f"{cksum:02X}"

# --------------------------------
# Main Loop
# --------------------------
print("Starting MAVLink -> NMEA bridge loop...")
while True:
    msg = mav.recv_match(type=["GPS_RAW_INT", "GLOBAL_POSITION_INT"], blocking=True)
    if msg:
        gga, rmc = gps_raw_to_nmea(msg)
        os.write(master_fd, gga.encode("ascii"))
        os.write(master_fd, rmc.encode("ascii"))
    time.sleep(0.1)
