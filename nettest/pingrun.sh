#!/bin/sh
# Timestamped pings (5/s) to the default gateway and the game host for N seconds into OUTDIR.
secs=${1:-3600}; out=${2:-.}
gw=$(route -n get default | awk '/gateway/{print $2}')
n=$((secs*5))
ping --apple-time -c $n -i 0.2 "$gw" > "$out/ping_gateway.txt" 2>&1 &
ping --apple-time -c $n -i 0.2 regattatron.com > "$out/ping_host.txt" 2>&1 &
wait
