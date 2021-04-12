# ILNP Overlay Network

## Running

The only dependency of this program is Python3. Python version 3.8.5 was used for testing and experiments.

To run the heartbeat program, from the root directory of the project run:
```
$ python3 src/heartbeat.py <config file>
```

Similarly to run the experiment program, from the root directory of the project run:
```
$ python3 src/experiment.py <config file>
```

Note that this will require setting up the configuration files as described in the config files section. The `<config file>` command line parameter is an optional command line parameter to specify the configuration file. If it's not specified then `./config/config.ini` will be used, path relative to the root directory of the project.

## Config files

The program is configured through `.ini` files. Here is an example:

```
[link]
log = true

# Local UDP multicast link layer emulation configuration
mcast_port      = 10000
mcast_interface = eth0
# MTU = 1440
buffer_size     = 1440

[network]
log = true

# Locators to join (which correspond to multicast addresses)
# Comma separated for joining multiple
# Hyphen separated for moving through
locators = 0:0:0:a,0:0:0:b,0:0:0:c

# Identifier of node
nid = ffff:0:0:a

# Optional, default value provided below
default_hop_limit = 3

# Time in seconds that backwards learning mappings will persist
# Note this is related to discovery.wait_time
# Optional, default value provided below
backwards_learning_ttl = 30

# Time in seconds that nodes will be considered
# to be in an active unicast session for after
# receiving or sending a packet to a node
# Used for sending locator updates
# Optional, default value provided below
active_unicast_session_ttl = 30

# Time between node moving locators in seconds
# Only used if there are hyphen separated sets of locators
# Optional, default value provided below
move_time = 20

# Soft handoff duration in seconds during which
# the node will be connected to both the old and new locators
# Only used if there are hyphen separated sets of locators
# Optional, default value provided below
handoff_time = 10

# Number of seconds to wait for a locator acknowledgement
# after sending a locator update
# Optional, default value provided below
loc_update_retry_wait_time = 1

# Number of times to retry sending a locator update
# Optional, default value provided below
loc_update_retries = 3

[transport]
log = true

[discovery]
log = true

hostname = alice
wait_time = 30

[application]
port = 1000
run_time = 510
```

Note:
* `link.mcast_interface` must match the interface on which the program is to communicate with IP multicast.

* `link.mcast_port` is the UDP port used and must be the same on all running instances of the programs.

* `link.buffer_size` is the maximum size of packets sent via our emulated link layer. If this is larger than the MTU UDP may split our packets up into multiple IP packets resulting in undesirable behaviour like higher loss, as if any IP packet is lost the entire UDP packet is lost.

* `network.locators` specifies the locators the nodes should join. This is parsed by splitting on hyphens (`-`) which the node will cycle through based on `network.move_time` and `network.handoff_time`. If there are comma-separated locators the node will join all these locators.
    
    With `locators = 0:0:0:a,0:0:0:f-0:0:0:b-0:0:0:c` the node will:
	* at T=0s join `0:0:0:a` **and** `0:0:0:f`
	* at T=20s join `0:0:0:b`
	* at T=30s leave `0:0:0:a` **and** `0:0:0:b`
	* at T=40s join `0:0:0:c`
	* at T=50s leave `0:0:0:b`
	* at T=60s join `0:0:0:a` **and** `0:0:0:f`
	* at T=70s leave `0:0:0:c`
    
    The cycle will then repeat.
    
* `discovery.hostname` is the name of the host in the overlay network.
    
* `discovery.wait_time` determines the time between discovery messages and has a default value of 30 seconds.
    
* `application.port` port is the port used in the overlay network for the STP.
    
* `application.run_time` is used by `experiment.py` to terminate after the given number of seconds.
    
* The log flag for each layer determines if logs are taken at that layer. See the logging section.

## Logging

Logs can be configured to be taken for each layer as shown in the config file section. Logs are saved to `logs/<hostname>_<layer>.log`.

The format of the log depends on the layer. See examples of logs in `heartbeat_logs`. The logs from the experiment are parsed by `python3 data_processing/process.py <log dir>` to create graphs.

## Scripts

Numerous scripts were created to automate the testing and experimental processes.
See the `scripts` directory for scripts for the Pis, and `scripts/desktop_scripts` for scripts using the workstation PC as a router.
This includes deploying code to the Pis over with `rsync`, removing logs on the Pis, running processes, killing processes, and retrieving logs.
These were run from a workstation and can use either Ethernet or Wifi.

## Hardware Setup

The process for configuring the Pis was:

* Flash SD card with Ubuntu Server LTS 20.04.2 On first login set password to `<PASSWORD>`
* Change hostname with `hostnamectl set-hostname <NAME>`
* Configure network
	* `echo "network: {config: disabled}" > /etc/cloud/cloud.cfg.d/99-disable-network-config.cfg`
	* Assign static ethernet IP address:\\ \href{https://www.linuxtechi.com/assign-static-ip-address-ubuntu-20-04-lts/}{https://www.linuxtechi.com/assign-static-ip-address-ubuntu-20-04-lts/}
	* Configure wifi connection\\ (\href{https://itsfoss.com/connect-wifi-terminal-ubuntu/}{https://itsfoss.com/connect-wifi-terminal-ubuntu/})\\ with IPv6 disabled\\ (\href{https://pscl4rke.wordpress.com/2019/10/01/disabling-ipv6-on-ubuntu-18-04-the-netplan-version/}{Disabling IPv6 on Ubuntu 18.04: The Netplan Version})
	* `/etc/netplan/50-cloud-init.yaml`:
```
    network:
        ethernets:
            eth0:
                dhcp4: false
                optional: true
                addresses: [ETH_IPv6_ADDR/64]
        wifis:
            wlan0:
                    # disable IPv6
                    link-local: []
                    dhcp4: true
                    optional: true
                    access-points:
                        "***REMOVED***":
                            password: "***REMOVED***"
        version: 2
```
*	* `systemctl start avahi-daemon.service`
* `sudo reboot`
* `echo "ETH\_IPv6\_ADDR NAME" >> /etc/hosts` (on all machines)
* Add `<NAME>` to list of hostnames in `~/.ssh/config` to config ssh user as ubuntu
* `ssh-copy-id -i ~/.ssh/id\_rsa.pub NAME`


On the workspace, `etc/hosts` contained:
```
	fe80::dea6:32ff:fec4:67d5 alice-eth
	fe80::dea6:32ff:fec4:6719 bob-eth
	fe80::dea6:32ff:fec4:6799 clare-eth fe80::82ee:73ff:fe4a:393f base-station-eth
	192.168.0.117             alice-wifi
	192.168.0.118             bob-wifi
	192.168.0.134             clare-wifi
```

And `~/.ssh/config` contained:
```
	# applies to mDNS hostname resolutions (e.g. alice)
	# and manually configured ethernet connections (e.g. alice-eth)
	Host alice* bob* clare*
			User ubuntu
	Host base-station*
			User root
	Host *eth
		BindInterface enp3s0
	Host base-station-luci-tunnel-eth
		Hostname base-station-eth
		LocalForward 127.0.0.1:8000 127.0.0.1:80

	Host alice-eth
	Host bob-eth
	Host clare-eth

```

Note that base-station machine was unused for the experiments.
