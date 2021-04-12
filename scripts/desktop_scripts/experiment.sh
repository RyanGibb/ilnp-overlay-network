#!/usr/bin/env bash

config=${1:-"experiment1"}

log_dir="$(dirname $0)"/../../data_processing/"$config"

$(dirname $0)/delete_logs.sh
rm "$log_dir"/*
$(dirname $0)/deploy.sh
$(dirname $0)/run_all.sh experiment "$config"
$(dirname $0)/retrieve_logs.sh "$log_dir"
