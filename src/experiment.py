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
    
    if REMOTE_HOSTNAME != None and REMOTE_HOSTNAME != "":
        remote = (REMOTE_HOSTNAME, REMOTE_PORT)
    else:
        remote = None
    
    f = open("/dev/urandom", "rb")

    while True:
        try:
            if remote != None:
                remote_addr = discovery.getaddrinfo(remote)
                data=f.read(32*1024)
                print("%-30s <- %s" % ("%s:%d" % remote, len(data)))
                sock.send(remote_addr, data)
        except transport.NetworkException as e:
            print("Network Exception: %s" % e.message)
        
        while True:
            try:
                data, src_addr = sock.receive()
                print("%-30s -> %s" % (
                        "%s:%d" % discovery.gethostbyaddr(src_addr),
                        len(data)
                ))
            except transport.NetworkException as e:
                break
        time.sleep(1)

if __name__ == "__main__":
    heartbeat()
