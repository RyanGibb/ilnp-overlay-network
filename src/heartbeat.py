import transport
import time
from datetime import datetime

# Must have prefix ff00::/8 for multicast
# Also note ffx1::/16 is interface local and ffx2::/12 is link-local
# Indexed by channel ID
LOCATORS = [
    '6465:6d6f:6d63:6173', 
    '0:0:0:1',
    '0:0:0:2',
    '0:0:0:3'
]


def heartbeat():
    while True:
        for channel_id in range(len(LOCATORS)):
            message = "%s | %s" % (str(datetime.now()), LOCATORS[channel_id])
            transport.send(LOCATORS[channel_id], message)
            print("%-30s Channel %d <- %s" % 
                (LOCATORS[channel_id], channel_id, message)
            )
        while True:
            try:
                message = transport.receive()
                print("-> %s" % message)
            except BlockingIOError:
                break
        time.sleep(1)

if __name__ == "__main__":
    heartbeat()
