#!/usr/bin/env python3
"""
read_mavlink_gps.py
Connects to a MAVLink endpoint (UDP or serial) and prints GPS-related messages to console.

Usage:
  # If using mavlink-router UDP endpoint:
  python3 read_mavlink_gps.py --source udpin:127.0.0.1:14560

  # If reading serial (may conflict with mavlink-router):
  python3 read_mavlink_gps.py --source serial:/dev/ttyAMA2:57600
"""

import argparse
from pymavlink import mavutil
import time

def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--source", required=True, help="mavlink source string, e.g. udpin:127.0.0.1:14560 OR serial:/dev/ttyAMA2:57600")
    return p.parse_args()

def main():
    args = parse_args()
    print(f"Connecting to MAVLink source: {args.source} ...")
    m = mavutil.mavlink_connection(args.source, autoreconnect=True)
    print("Waiting for messages... (Ctrl-C to quit)")
    while True:
        try:
            msg = m.recv_match(blocking=True, timeout=5)
            if msg is None:
                # no message in timeout window -- continue waiting
                continue
            # Check message type names that include GPS info
            mt = msg.get_type()
            if mt in ("GPS_RAW_INT", "GPS_RAW_INT2", "GPS2_RAW", "GLOBAL_POSITION_INT", "ATT_POS_MOCAP"):
                # handle common fields safely
                try:
                    if mt == "GLOBAL_POSITION_INT":
                        lat = msg.lat / 1e7
                        lon = msg.lon / 1e7
                        alt = msg.relative_alt / 1000.0  # meters
                        print(f"[{mt}] lat={lat:.7f} lon={lon:.7f} rel_alt={alt:.3f} m")
                    else:
                        # GPS_RAW_INT and friends: lat/lon are in 1e7, alt in mm
                        lat = getattr(msg, 'lat', None)
                        lon = getattr(msg, 'lon', None)
                        alt = getattr(msg, 'alt', None)
                        fix_type = getattr(msg, 'fix_type', None)
                        satellites_visible = getattr(msg, 'satellites_visible', None)
                        if lat is not None and lon is not None:
                            print(f"[{mt}] lat={lat/1e7:.7f} lon={lon/1e7:.7f} alt={(alt/1000.0) if alt is not None else 'N/A'} m fix={fix_type} sats={satellites_visible}")
                except Exception as e:
                    print("Error parsing message:", e)
            # you can uncomment this to see other messages
            # else:
            #     print(f"Other message: {mt}")
        except KeyboardInterrupt:
            print("Exiting.")
            break
        except Exception as e:
            print("Connection error or parse failure:", e)
            time.sleep(1)

if __name__ == "__main__":
    main()
