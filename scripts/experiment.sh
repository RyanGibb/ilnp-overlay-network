#!/usr/bin/env bash

$(dirname $0)/delete_logs.sh
$(dirname $0)/all_run_and_deploy.sh experiment
$(dirname $0)/retrieve_logs.sh
