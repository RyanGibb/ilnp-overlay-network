#!/usr/bin/env bash

log_dir=${1:-"$(dirname $0)"/../../logs}
method=${2:-"wifi"}

echo "Retrieving logs to $log_dir ..."
for host in alice bob; do
    rsync --inplace -r "$host"-"$method":~/ilnp-overlay-network/logs/ "$log_dir"
    echo "$host"
done

mv "$(dirname $0)"/../../logs/* "$log_dir"
