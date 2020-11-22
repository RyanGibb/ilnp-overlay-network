import time
from datetime import datetime

import transport

LOC  = "0:0:0:1"
ADDR = ":".join([LOC, transport.network.MCAST_NID])
PORT = 1000

def heartbeat():
    sock = transport.Socket()
    sock.bind(PORT)
    remote_string = "[%s]:%d" % (ADDR, PORT)
    while True:
        message = "%s | %s" % (str(datetime.now()), transport.network.local_nid)
        try:
            sock.send((ADDR, PORT), message.encode('utf-8'))
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
    heartbeat()
