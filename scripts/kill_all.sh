#!/usr/bin/env bash

method=${1:-"wifi"} 

echo "Killing..."
for host in alice bob; do
	ssh "$host"-"$method" pkill python3
    echo "$host"
done
