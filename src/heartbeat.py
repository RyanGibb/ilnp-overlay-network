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

    while True:
        try:
            if remote != None:
                message = "%s | %s" % (str(datetime.now()), HOSTNAME)
                remote_addr = discovery.getaddrinfo(remote)
                print("%-30s <- %s" % ("%s:%d" % remote, message))
                sock.send(remote_addr, message.encode('utf-8'))
        except transport.NetworkException as e:
            print("Network Exception: %s" % e.message)
        
        while True:
            try:
                message, src_addr = sock.receive()
                print("%-30s -> %s" % (
                        "%s:%d" % discovery.gethostbyaddr(src_addr),
                        message.decode('utf-8')
                ))
            except transport.NetworkException as e:
                break
        time.sleep(1)

if __name__ == "__main__":
    heartbeat()