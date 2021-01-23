#!/usr/bin/env bash

METHOD=${1:-"wifi"} 

pis_addrs=("alice-$METHOD" "bob-$METHOD")

for pi_addr in "${pis_addrs[@]}"; do
    echo "$pi_addr"
    rsync -r "$pi_addr":~/ilnp-overlay-network/logs/ $(dirname $0)/logs
done
