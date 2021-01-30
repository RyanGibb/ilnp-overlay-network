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
    while True:
        message = "%s | %s" % (str(datetime.now()), HOSTNAME)
        try:
            if REMOTE_HOSTNAME != None and REMOTE_HOSTNAME != "":
                remote_addr = discovery.getaddrinfo(REMOTE_HOSTNAME, REMOTE_PORT)
                sock.send(remote_addr, message.encode('utf-8'))
                print("%-30s <- %s" % ("[%s]:%d" % remote_addr, message))
        except transport.NetworkException as e:
            print("Network Exception: %s" % e.message)
        while True:
            try:
                message, src_addr = sock.receive()
                print("%-30s -> %s" % ("[%s]:%d" % src_addr, message.decode('utf-8')))
            except transport.NetworkException as e:
                break
        time.sleep(1)

if __name__ == "__main__":
    if REMOTE_HOSTNAME != "":
        print("Starting heartbeat...")
        heartbeat()
