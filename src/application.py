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
        try:
            remote_addr = discovery.getaddrinfo(REMOTE_HOSTNAME, REMOTE_PORT)
            break
        except transport.NetworkException as e:
            time.sleep(1)
    remote_string = "[%s]:%d" % remote_addr
    while True:
        message = "%s | %s" % (str(datetime.now()), HOSTNAME)
        try:
            sock.send(remote_addr, message.encode('utf-8'))
        except transport.NetworkException as e:
            print("Network Exception: %s" % e.message)
        print("%-60s <- %s" % (remote_string, message))
        while True:
            try:
                message = sock.receive()
                print("%-60s -> %s" % (remote_string, message.decode('utf-8')))
            except transport.NetworkException as e:
                break
        time.sleep(1)

if __name__ == "__main__":
    if REMOTE_HOSTNAME != "":
        print("Starting heartbeat...")
        heartbeat()
