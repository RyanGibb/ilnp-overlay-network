import struct
import collections
import threading
import time

import network
from util import *

# TODO add port number for multiplexing
# TODO add socket object to keep track of state like port and buffers

next_header = 42

# IO circular queues
in_qs = {} # map of queues


class Socket:
    # remote addr and port
    def __init__(self, addr, port):
        # here addr represents a ILV (Identfier-Locator Vector)
        self.addr = addr
        self.port = port
        if (addr, port) in in_qs:
            raise NetworkException(
                "Socket to this remote [%s]:%d already exists" % (addr, port)
            )
        in_q = collections.deque(maxlen=None)
        in_qs[(addr, port)] = in_q
        self.in_q = in_q
        # UDP-like protocol, so no handshake
    
    def send(self, data):
        locator    = ":".join(self.addr.split(":")[:4])
        identifier = ":".join(self.addr.split(":")[4:])
        # Transport header is simply a 16bit port
        header = struct.pack("!2s", int_to_bytes(self.port, 2))
        message = header + data
        network.send(locator, identifier, message)

    def receive(self):
        try:
            return self.in_q.popleft()
        except IndexError:
            raise NetworkException(
                "No recived packets from [%s]:%d" % (self.addr, self.port)
            )


class ReceiveThread(threading.Thread):
    def run(self):
        # Queue by src addr and port
        while True:
            try:
                (
                    message, 
                    src_locator, src_identifier,
                    dst_locator, dst_identifier
                ) = network.receive(next_header)
            except NetworkException:
                # TODO wait here?
                time.sleep(1)
                continue
            header = message[:2]
            port_bytes = struct.unpack("!2s", header)[0]
            port = bytes_to_int(port_bytes)
            data = message[2:]
            # TODO make mcast not broadcast and horribly hacky
            if dst_identifier == network.MCAST_IDENTIFIER:
                src_addr = ":".join([dst_locator, dst_identifier])
            else:
                src_addr = ":".join([src_locator, src_identifier])
            # drop if not valid remote (i.e. there is no coresponding socket)
            if (src_addr, port) not in in_qs:
                continue
            # TODO do something with dst like support mcase
            in_qs.setdefault(
                (src_addr, port), collections.deque(maxlen=None)
            ).append(data)


def startup():
    receive_thread = ReceiveThread()
    receive_thread.start()


startup()
