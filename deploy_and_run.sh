#!/usr/bin/env bash

clean_up() {
	echo "Cleanup..."
	ssh alice-wifi pkill python3 &\
	ssh bob-wifi pkill python3
	exit
}

trap clean_up SIGHUP SIGINT SIGTERM

echo "Deploying..."
$(dirname $0)/deploy_to_pis.sh eth

echo "Running.."
ssh alice-wifi "ilnp-overlay-network/run.sh > alice.txt" &\
ssh bob-wifi "ilnp-overlay-network/run.sh > bob.txt" &

python3 src/application.py config/config.ini
echo "Exited desktop"
read

clean_up
