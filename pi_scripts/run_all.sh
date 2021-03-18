#!/usr/bin/env bash

application=${1:-"heartbeat"}
config=${2:-"heartbeat"}
method=${3:-"wifi"}

clean_up() {
	$(dirname $0)/kill_all.sh "$method"
	exit
}

trap clean_up SIGHUP SIGINT SIGTERM

echo "Running..."
for host in alice bob; do
	command="$(tail -1 $(dirname $0)/run.sh | sed -e "s/\"\$application\"/$application/g" | sed -e "s/\"\$host\"/$host/g" | sed -e "s/\"\$config\"/$config/g")"
	ssh "$host"-"$method" "$command >> "~/ilnp-overlay-network/logs/$application"_"$host".log" &\
	echo $host
done

host=clare
command="$(tail -1 $(dirname $0)/run.sh | sed -e "s/\"\$application\"/$application/g" | sed -e "s/\"\$host\"/$host/g" | sed -e "s/\"\$config\"/$config/g")"
ssh "$host"-"$method" "$command >> "~/ilnp-overlay-network/logs/$application"_"$host".log" &

wait

clean_up
