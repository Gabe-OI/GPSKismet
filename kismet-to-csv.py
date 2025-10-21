#!/usr/bin/env python3
import sqlite3
import pandas as pd
from datetime import datetime, timedelta
import sys
import os
import json

# Usage instructions
if len(sys.argv) != 3:
    print("Usage: python3 kismet-db-to-csv.py <input.kismet> <output.csv>")
    sys.exit(1)

# Arguments
db_file = sys.argv[1]
output_csv = sys.argv[2]

# Fileread error handling
if not os.path.exists(db_file):
    print(f"Error: database '{db_file}' not found.")
    sys.exit(1)

print(f"Reading from database: {db_file}")

# Load relevant packet data
query = """
SELECT ts_sec, sourcemac, frequency, signal, lat, lon, alt, heading
FROM packets
WHERE ts_sec IS NOT NULL AND sourcemac IS NOT NULL
"""
conn = sqlite3.connect(db_file)
packets = pd.read_sql_query(query, conn)
conn.close()

# ...or exit if not present
if packets.empty:
    print("No packet data found in database.")
    sys.exit(1)

print(f"Loaded {len(packets):,} packets from database")

# Convert coordinates to degrees
packets['lat'] *= 60
packets['lon'] *= 60

# Load MAC-to-SSID mapping from devices table
print("Extracting SSIDs from devices table...")

try:
    conn = sqlite3.connect(db_file)
    ssid_query = "SELECT devmac, CAST(device AS TEXT) AS device_json FROM devices"
    devices_df = pd.read_sql_query(ssid_query, conn)
    conn.close()
except Exception as e:
    print(f"Warning: Could not read SSIDs: {e}")
    devices_df = pd.DataFrame(columns=["devmac", "device_json"])

# Parse JSON blobs safely
mac_to_ssid = {}
for _, row in devices_df.iterrows():
    mac = row["devmac"]
    try:
        data = json.loads(row["device_json"])
        ssid = (
            data.get("kismet.device.base.name")
            or "NaN"
        )
        mac_to_ssid[mac] = ssid
    except Exception:
        mac_to_ssid[mac] = "NaN"

print(f"Loaded {len(mac_to_ssid)} SSID mappings.")

# Build base timestamp dataframe (1 row per second)
packets['Timestamp'] = pd.to_datetime(packets['ts_sec'], unit='s')
packets.sort_values('Timestamp', inplace=True)

# Group by timestamp
gps_grouped = (
    packets.groupby('ts_sec')
    .agg({
        'lat': 'last', # Option C: last valid per second
        'lon': 'last',
        'alt': 'last',
        'heading': 'last'
    })
    .reset_index()
)

# Create Date and Time columns
gps_grouped['Date'] = pd.to_datetime(gps_grouped['ts_sec'], unit='s').dt.date
gps_grouped['Time'] = pd.to_datetime(gps_grouped['ts_sec'], unit='s').dt.strftime('%H:%M:%S')

# Reorder columns
gps_grouped = gps_grouped[['Date', 'Time', 'lat', 'lon', 'alt', 'heading', 'ts_sec']]
gps_grouped.rename(columns={
    'lat': 'Latitude',
    'lon': 'Longitude',
    'alt': 'Altitude',
    'heading': 'Heading'
}, inplace=True)

# Pivot MAC/frequency/signal values
print("Building signal strength matrix (this may take a while)...")

# Convert frequency to channel
def freq_to_channel(freq):
    try:
        f = float(freq)
        if 2412000 <= f <= 2472000: # 2.4 GHz
            return int((f - 2407000) / 5000)
        elif 5180000 <= f <= 5825000: # 5 GHz
            return int((f - 5000000) / 5000)
        elif 5955000 <= f <= 7115000: # 6 GHz
            return int((f - 5950000) / 5000)
        else:
            return str(int(f)) # Fallback: raw frequency
    except:
        return str(freq)

packets['Channel'] = packets['frequency'].apply(freq_to_channel)

# Combine SSID, MAC, channel, and frequency to form unique identifier
packets['SSID'] = packets['sourcemac'].map(mac_to_ssid).fillna("NaN")
packets['MAC_CH'] = packets['SSID'] + ' | ' + packets['sourcemac'] + ' @ CH' + packets['Channel'].astype(str) + ' (' + (packets['frequency'] / 1000).astype(str) + 'MHz)'

# Group by second + MAC@CH and take max signal
signal_grouped = (
    packets.groupby(['ts_sec', 'MAC_CH'])['signal']
    .max()
    .reset_index()
)

# Pivot: timestamps as rows, MAC@CH as columns, signal as values
pivot_signals = signal_grouped.pivot(index='ts_sec', columns='MAC_CH', values='signal')

# Group by second + MAC@CH and take max signal
signal_grouped = (
    packets.groupby(['ts_sec', 'MAC_CH'])['signal']
    .max()
    .reset_index()
)

# Pivot timestamps as rows, MAC@CH as columns, signal as values
pivot_signals = signal_grouped.pivot(index='ts_sec', columns='MAC_CH', values='signal')

# Compute the first timestamp where each MAC@CH was seen
first_seen = (
    signal_grouped
    .groupby('MAC_CH')['ts_sec']
    .min()
    .sort_values()
)

# Reorder signal columns by the timestamp of their first detection
print("Reordering signal columns by first detection time...")

ordered_cols = [col for col in first_seen.index if col in pivot_signals.columns]
pivot_signals = pivot_signals[ordered_cols]

# Merge GPS and signal data
merged = pd.merge(gps_grouped, pivot_signals, on='ts_sec', how='left')

# Forward-fill GPS data for missing seconds
merged[['Latitude', 'Longitude', 'Altitude', 'Heading']] = merged[['Latitude', 'Longitude', 'Altitude', 'Heading']].ffill()

# Drop internal ts_sec column and save
merged.drop(columns=['ts_sec'], inplace=True)
merged.to_csv(output_csv, index=False)

print(f"Saved {len(merged):,} rows and {len(merged.columns):,} columns to {output_csv}")
