import os
import sys
import time
from datetime import datetime

import transport
import util
import discovery

if "application" in util.config:
    config_section = util.config["application"]
else:
    config_section = {}

if "port" in config_section:
    PORT = config_section.getint("port")
else:
    PORT = None

if "remote_hostname" in config_section:
    REMOTE_HOSTNAME = config_section["remote_hostname"]
else:
    REMOTE_HOSTNAME = None

if "remote_port" in config_section:
    REMOTE_PORT = config_section.getint("remote_port")
else:
    REMOTE_PORT = None

if "run_time" in config_section:
    RUN_TIME = config_section.getfloat("run_time")
else:
    RUN_TIME = None

if "wait_time" in config_section:
    WAIT_TIME = config_section.getfloat("wait_time")
else:
    # 100ms
    WAIT_TIME = 0.1


def experiment():
    # If no local port, return.
    # Node will still run network code and forward packets
    if PORT == None:
        return
    sock = transport.Socket()
    sock.bind(PORT)
    
    if REMOTE_HOSTNAME != None and REMOTE_HOSTNAME != "":
        remote = (REMOTE_HOSTNAME, REMOTE_PORT)
    else:
        remote = None
    
    print(datetime.now(), " Started")
    for k in config_section:
        print("\t%s = %s" % (k, config_section[k]))

    f = open("/dev/urandom", "rb")
    
    total_bytes = 0

    start = None

    i = 1
    sequence_number = None
    # keep track of how many seconds behind we are,
    # to avoid spiking to catch up after intermitened connectivity
    slow = 0
    while True:
        try:
            if remote != None:
                remote_addrinfo = discovery.getaddrinfo(remote)
                # MTU - header size = 1440 - 44 = 1396
                # 1396 - 8 = 1388
                data=util.int_to_bytes(i, 8) + f.read(1388)
                print("%s %-20s/%-30s <- %d %d" % (
                    datetime.now(),
                    "%s:%d" % remote,
                    "[ %s : %s ]:%d" % remote_addrinfo,
                    len(data),
                    i
                ))
                sock.send(remote_addrinfo, data)
                i+=1
                if start == None:
                    start=time.time()
                else:
                    sleep_time = (i * WAIT_TIME) - (time.time() - start) + slow
                    if sleep_time > 0:
                        time.sleep(sleep_time)
                    else:
                        slow += -sleep_time
                        print("WARN %f slow" % -sleep_time, file=sys.stderr)
                total_bytes+=len(data)
        except transport.NetworkException as e:
            print("Network Exception: %s" % e.message, file=sys.stderr)
        
        while True:
            try:
                data, src_addrinfo = sock.receive()
                sequence_number=util.bytes_to_int(data[:8])
                if start == None:
                    start=time.time()
                print("%s %-20s/%-30s -> %d %d" % (
                        datetime.now(),
                        "%s:%d" % discovery.gethostbyaddr(src_addrinfo),
                        "[ %s : %s ]:%d" % src_addrinfo,
                        len(data),
                        sequence_number
                ))
                total_bytes+=len(data)
            except transport.NetworkException as e:
                # Allow context switching
                time.sleep(0)
                break

        now = time.time()

        if sequence_number == 0:
            break

        if RUN_TIME != None and start != None and now - start > RUN_TIME:
            if remote != None:
                remote_addr = discovery.getaddrinfo(remote)
                data=util.int_to_bytes(0, 8)
                sock.send(remote_addr, data)
                print("%s %-30s <- %d %d" % (
                    datetime.now(),
                    "%s:%d" % remote,
                    len(data),
                    0
                ))
            break
    print("Total bytes: %d" % total_bytes)
    print("Bytes/sec: %d" % (total_bytes / (now - start)))


if __name__ == "__main__":
    experiment()
