import time
from datetime import datetime

import transport
import util
import discovery

HOSTNAME        = util.config["discovery"]["hostname"]
PORT            = util.config["application"].getint("port")
REMOTE_HOSTNAME = util.config["application"]["remote_hostname"]
REMOTE_PORT     = util.config["application"].getint("remote_port")

def heartbeat():
    sock = transport.Socket()
    sock.bind(PORT)
    
    local = (HOSTNAME, PORT)

    if REMOTE_HOSTNAME != None and REMOTE_HOSTNAME != "":
        remote = (REMOTE_HOSTNAME, REMOTE_PORT)
    else:
        remote = None

    while True:
        try:
            if remote != None:
                message = "%s | %s" % (str(datetime.now()), HOSTNAME)
                remote_addrinfo = discovery.getaddrinfo(remote)
                local_addrinfo = discovery.getaddrinfo(local)
                interface = sock.send(remote_addrinfo, message.encode('utf-8'))
                print("%s %-40s <- %-40s %s" % (
                    datetime.now(),
                    "[%s/%s%%%s]:%d" % (
                        remote[0],
                        remote_addrinfo[0], # ilv
                        interface,
                        remote_addrinfo[1]  # port
                    ),
                    "[%s/%s]:%d" % (HOSTNAME, *local_addrinfo),
                    message
                ))
        except transport.NetworkException as e:
            print("Network Exception: %s" % e.message)
        
        while True:
            try:
                message, src_addrinfo, dst_addrinfo, interface = sock.receive()
                src_host, _ = discovery.gethostbyaddr(src_addrinfo)
                dst_host, _ = discovery.gethostbyaddr(dst_addrinfo)
                print("%s %-40s -> %-40s %s" % (
                        datetime.now(),
                        "[%s/%s%%%s]:%d" % (
                            src_host,
                            src_addrinfo[0], # ilv
                            interface,
                            src_addrinfo[1]  # port
                        ),
                        "[%s/%s]:%d" % (dst_host, *dst_addrinfo),
                        message.decode('utf-8')
                ))
            except transport.NetworkException as e:
                break
        time.sleep(1)

if __name__ == "__main__":
    heartbeat()
