#!/usr/bin/env bash

mode=${1:-"heartbeat"}
method=${2:-"wifi"}

clean_up() {
	$(dirname $0)/kill_all.sh "$method"
	exit
}

trap clean_up SIGHUP SIGINT SIGTERM

echo "Running..."
for host in alice bob; do
	command="$(tail -1 $(dirname $0)/run.sh | sed -e "s/\"\$mode\"/$mode/g" | sed -e "s/\"\$host\"/$host/g")"
	ssh "$host"-"$method" "$command >> "~/ilnp-overlay-network/logs/$mode"_"$host".log" &\
	echo $host
done

python3 "$(dirname $0)"/../src/"$mode".py "$(dirname $0)"/../config/"$mode"/config.ini >> "$(dirname $0)"/../logs/experiment_desktop.log
echo "Exited desktop"
read

clean_up
