import struct
import collections
import threading
import time
import os

import network
import util
from util import NetworkException
import discovery

PROTOCOL_NEXT_HEADER = 42

# Map of input circular queues indexed by local port
in_queues = {}


class Socket:
    # Bind the socket to a port to receive 
    def bind(self, port):
        if port in in_queues:
            raise NetworkException("Port %d already bound" % port)
        in_queue = collections.deque(maxlen=None)
        in_queues[port] = in_queue
        self.port = port
        self.in_queue = in_queue
    
    def send(self, remote, data):
        remote_loc, remote_nid, remote_port = remote
        # Transport header is just 16 bit source and destination ports
        header = struct.pack("!2s2s",
            util.int_to_bytes(self.port, 2),
            util.int_to_bytes(remote_port, 2)
        )
        message = header + data
        if log_file != None:
            util.write_log(log_file, "%-30s <- %-30s %s" % (
                "[%s:%s]:%d" % remote,
                "[localhost]:%d" % self.port,
                (str(data[:29]) + '...') if len(data) > 32 else data
            ))
        network.send(remote_loc, remote_nid, message, PROTOCOL_NEXT_HEADER)
        with network.send_cv:
            network.send_cv.notify()        

    def receive(self):
        try:
            return self.in_queue.popleft()
        except IndexError:
            raise NetworkException("No packets for port %d" % self.port)
        except AttributeError:
            raise NetworkException("Socket is not bound to a port.")


class ReceiveThread(threading.Thread):
    def run(self):
        while True:
            try:
                message, src_loc, src_nid, dst_loc, dst_nid = network.receive(PROTOCOL_NEXT_HEADER)
            # Input queue empty (or non-existant) for next header PROTOCOL_NEXT_HEADER
            except (IndexError, KeyError):
                with network.receive_cv[PROTOCOL_NEXT_HEADER]:
                    network.receive_cv[PROTOCOL_NEXT_HEADER].wait()
                continue
            except :
                raise NetworkException("Invalid next header: %d" % PROTOCOL_NEXT_HEADER)
            header = message[:4]
            sre_port_bytes, dst_port_bytes = struct.unpack("!2s2s", header)
            src_port = util.bytes_to_int(sre_port_bytes)
            dst_port = util.bytes_to_int(dst_port_bytes)
            data = message[4:]
            # drop if not valid port (if there's no socket bound to this port)
            if dst_port not in in_queues:
                continue
            in_queues.setdefault(
                dst_port, collections.deque(maxlen=None)
            ).append((
                data,
                (src_loc, src_nid, src_port),
                (dst_loc, dst_nid, dst_port)
            ))

            if log_file != None:
                util.write_log(log_file, "%-30s -> %-30s %s" % (
                    "[%s:%s]:%d" % (src_loc, src_nid, src_port),
                    "[%s:%s]:%d" % (dst_loc, dst_nid, dst_port),
                    (str(data[:29]) + '...') if len(data) > 32 else data
                ))


def startup():
    global log_file
    log_file = util.get_log_file("transport")
    
    ReceiveThread().start()


startup()
