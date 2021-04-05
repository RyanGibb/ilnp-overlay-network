#!/usr/bin/env bash

method=${1:-"wifi"} 

echo "Deploying..."
for host in alice bob clare; do
    rsync --inplace -r $(dirname $0)/../src    "$host"-"$method":~/ilnp-overlay-network
    rsync --inplace -r $(dirname $0)/../config "$host"-"$method":~/ilnp-overlay-network
    rsync --inplace -r $(dirname $0)/../scripts "$host"-"$method":~/ilnp-overlay-network
    echo "$host"
done
