#!/usr/bin/env bash

method=${1:-"eth"} 

echo "Deploying..."
for host in alice bob; do
    rsync --inplace -r $(dirname $0)/../src    "$host"-"$method":~/ilnp-overlay-network
    rsync --inplace -r $(dirname $0)/../config "$host"-"$method":~/ilnp-overlay-network
    echo "$host"
done
