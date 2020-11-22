import time
from datetime import datetime

import transport

LOCATOR = "0:0:0:1"
ADDR    = ":".join([LOCATOR, transport.network.MCAST_IDENTIFIER])
PORT    = 1000

def heartbeat():
    sock = transport.Socket(ADDR, PORT)
    remote_string = "[%s]:%d" % (ADDR, PORT)
    while True:
        message = "%s | %s" % (str(datetime.now()), transport.network.local_identifier)
        try:
            sock.send(message.encode('utf-8'))
        except transport.NetworkException as e:
            print("Network Exception: %s" % e.message)
        print("%-60s <- %s" % (remote_string, message))
        while True:
            try:
                message = sock.receive()
                print("%-60s -> %s" % (remote_string, message.decode('utf-8')))
            except transport.NetworkException as e:
                print("Network Exception: %s" % e.message)
                break
        time.sleep(1)

if __name__ == "__main__":
    heartbeat()
