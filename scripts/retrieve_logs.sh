#!/usr/bin/env bash

method=${1:-"eth"} 

echo "Retrieving logs..."
for host in alice bob; do
    rsync --inplace -r "$host"-"$method":~/ilnp-overlay-network/logs/ $(dirname $0)/../logs
    echo "$host"
done
