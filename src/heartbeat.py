import time
from datetime import datetime

import transport

LOCATOR = "0:0:0:1"
ADDR    = ":".join([LOCATOR, transport.network.MCAST_IDENTIFIER])

def heartbeat():
    while True:
        message = "%s | %s" % (str(datetime.now()), transport.network.local_identifier)
        transport.send(ADDR, message)
        print("%-50s <- %s" % (ADDR, message))
        while True: 
            try:
                message, src_addr, dst_addr = transport.receive()
                print("%-50s -> %s" % (src_addr, message))
            except BlockingIOError:
                break
        time.sleep(1)

if __name__ == "__main__":
    heartbeat()
