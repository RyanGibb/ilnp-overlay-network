#!/usr/bin/env bash

method=${1:-"wifi"}

echo "Deleting logs..."
for host in alice bob clare; do
	ssh "$host"-"$method" "rm ~/ilnp-overlay-network/logs/*.log" &\
    echo "$host"
done

rm $(dirname $0)/../logs/*.log
