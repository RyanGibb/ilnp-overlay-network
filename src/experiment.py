import os
import sys
import time
from datetime import datetime

import transport
import util
import discovery

def experiment(port, remote, run_time, wait_time):
    sock = transport.Socket()
    if port != None:
        sock.bind(port)
    
    hostname = util.config["discovery"]["hostname"]

    f = open("/dev/urandom", "rb")
    
    total_bytes = 0

    if port == None and remote == None:
        start = time.time()
    else:
        start = None
    
    # keep track of how many seconds behind we are,
    # to avoid spiking to catch up after intermitened connectivity
    slow = 0

    i = 1
    sequence_number = None
    while True:
        try:
            if remote != None:
                remote_addrinfo = discovery.getaddrinfo(remote)
                # MTU - header size = 1440 - 44 = 1396
                # 1396 - 8 = 1388
                data=util.int_to_bytes(i, 8) + f.read(1388)
                print("%s %-40s <- %-40s  %d %d" % (
                    datetime.now(),
                    "[%s/%s:%s]:%d" % (remote[0], *remote_addrinfo),
                    "[%s]:%d" % (hostname, port),
                    len(data),
                    i
                ))
                sock.send(remote_addrinfo, data)
                i+=1
                if start == None:
                    start=time.time()
                else:
                    sleep_time = (i * wait_time) - (time.time() - start) + slow
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
                data, src_addrinfo, dst_addrinfo = sock.receive()
                sequence_number=util.bytes_to_int(data[:8])
                src_host, _ = discovery.gethostbyaddr(src_addrinfo)
                dst_host, _ = discovery.gethostbyaddr(dst_addrinfo)
                if start == None:
                    start=time.time()
                print("%s %-40s -> %-40s %d %d" % (
                        datetime.now(),
                        "[%s/%s:%s]:%d" % (src_host, *src_addrinfo),
                        "[%s/%s:%s]:%d" % (dst_host, *dst_addrinfo),
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

        if run_time != None and start != None and now - start > run_time:
            if remote != None:
                remote_addrinfo = discovery.getaddrinfo(remote)
                data=util.int_to_bytes(0, 8)
                sock.send(remote_addrinfo, data)
                print("%s %-20s/%-30s <- %d %d" % (
                    datetime.now(),
                    "[%s/%s:%s]:%d" % (remote[0], *remote_addrinfo),
                    "[%s]:%d" % (util.config["discovery"]["hostname"], port),
                    len(data),
                    0
                ))
            break
        
        # If socket not bound to any port, and remote is not set,
        # (i.e. are acting as a router)
        if port == None and remote == None:
            # sleep for wait time
            time.sleep(wait_time)
        
    print("Total bytes: %d" % total_bytes)
    print("Bytes/sec: %d" % (total_bytes / (now - start)))
    os._exit(0)


if __name__ == "__main__":
    # If no application config section, return.
    # Node will still run network code and forward packets
    if "application" not in util.config:
        exit(0)
    
    config_section = util.config["application"]

    if "port" in config_section:
        port = config_section.getint("port")
    else:
        port = None

    if "remote_hostname" in config_section:
        remote_hostname = config_section["remote_hostname"]
    else:
        remote_hostname = None

    if "remote_port" in config_section:
        remote_port = config_section.getint("remote_port")
    else:
        remote_port = None

    if "run_time" in config_section:
        run_time = config_section.getfloat("run_time")
    else:
        run_time = None

    if "wait_time" in config_section:
        wait_time = config_section.getfloat("wait_time")
    else:
        # 100ms
        wait_time = 0.1

    if remote_hostname != None and remote_hostname != "":
        remote = (remote_hostname, remote_port)
    else:
        remote = None
    
    print(datetime.now(), " Started")
    for k in config_section:
        print("\t%s = %s" % (k, config_section[k]))
    
    experiment(port, remote, run_time, wait_time)
