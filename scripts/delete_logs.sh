#!/usr/bin/env bash

method=${1:-"eth"}

echo "Deleting logs..."
for host in alice bob; do
	ssh "$host"-"$method" "rm ~/ilnp-overlay-network/logs/*.log" &\
    echo "$host"
done

rm $(dirname $0)/../logs/*.log
