#!/usr/bin/env bash

METHOD=${1:-"wifi"} 

pis_addrs=("alice-$METHOD" "bob-$METHOD")

for pi_addr in "${pis_addrs[@]}"; do
    echo "$pi_addr"
    rsync -r src "$pi_addr":~/ilnp-overlay-network
done
