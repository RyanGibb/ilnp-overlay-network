#!/usr/bin/env bash

pis_addrs=(alice-wifi bob-wifi)

for pi_addr in "${pis_addrs[@]}"; do
    echo "$pi_addr"
    rsync -r src "$pi_addr":~/ilnp-overlay-network
done
