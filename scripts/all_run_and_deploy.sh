#!/usr/bin/env bash

mode=$1

$(dirname $0)/deploy.sh
$(dirname $0)/run_all.sh "$mode"
