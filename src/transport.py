import struct
import collections
import threading
import time
import os

import network
import util
from util import NetworkException

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
        self.receive_cv = None
    
    def set_receive_block(self, receive_block):
        if self.port == None:
            raise NetworkException("Socket not bound")
        if receive_block:
            global receive_cvs
            receive_cvs[self.port] = threading.Condition()
            self.receive_cv = receive_cvs[self.port]
        else:
            if self.port in receive_cvs:
                del receive_cvs[self.port]
            self.receive_cv = None
    
    def send(self, remote, data):
        remote_ilv, remote_port = remote
        remote_loc = ":".join(remote_ilv.split(":")[:4])
        remote_nid = ":".join(remote_ilv.split(":")[4:])
        # Transport header is just 16 bit source and destination ports
        header = struct.pack("!2s2s",
            util.int_to_bytes(self.port, 2),
            util.int_to_bytes(remote_port, 2)
        )
        message = header + data
        interface = network.send(remote_loc, remote_nid, message, PROTOCOL_NEXT_HEADER)
        if log_file != None:
            util.write_log(log_file, "%-30s <- %-30s %s" % (
                "[%s:%s%%%s]:%d" % (remote_loc, remote_nid, interface, remote_port),
                "[%s:%s]:%d" % (interface, network.local_nid, self.port),
                (str(data[:29]) + '...') if len(data) > 32 else data
            ))
        return interface

    def receive(self):
        try:
            if len(self.in_queue) > 0:
                return self.in_queue.popleft()
            elif self.receive_cv != None:
                with self.receive_cv:
                    self.receive_cv.wait()
                return self.in_queue.popleft()
            else:
                raise NetworkException("No packets for port %d" % self.port)
        except AttributeError:
            raise NetworkException("Socket is not bound to a port.")


class ReceiveThread(threading.Thread):
    def run(self):
        global receive_cvs
        while True:
            try:
                message, src_loc, src_nid, dst_loc, dst_nid, interface = network.receive(PROTOCOL_NEXT_HEADER)
            # Input queue empty (or non-existant) for next header PROTOCOL_NEXT_HEADER
            except (IndexError, KeyError):
                with network.receive_cvs[PROTOCOL_NEXT_HEADER]:
                    network.receive_cvs[PROTOCOL_NEXT_HEADER].wait()
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
                (":".join([src_loc, src_nid]), src_port),
                (":".join([dst_loc, dst_nid]), dst_port),
                interface
            ))

            if dst_port in receive_cvs:
                with receive_cvs[dst_port]:
                    receive_cvs[dst_port].notify()

            if log_file != None:
                util.write_log(log_file, "%-30s -> %-30s %s" % (
                    "[%s:%s%%%s]:%d" % (src_loc, src_nid, interface, src_port),
                    "[%s:%s]:%d" % (dst_loc, dst_nid, dst_port),
                    (str(data[:29]) + '...') if len(data) > 32 else data
                ))


def startup():
    global log_file
    log_file = util.get_log_file("transport")

    # cv = conditional value
    global receive_cvs
    receive_cvs = {}
    ReceiveThread().start()


startup()
