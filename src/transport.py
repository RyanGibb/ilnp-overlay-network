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
        remote_nid, remote_port = remote
        # Transport header is just 16 bit source and destination ports
        header = struct.pack("!2s2s",
            util.int_to_bytes(self.port, 2),
            util.int_to_bytes(remote_port, 2)
        )
        message = header + data
        if log_file != None:
            util.write_log(log_file, "%-30s <- %-30s %s" % (
                "[%s]:%d" % remote,
                "[%s]:%d" % (network.local_nid, self.port),
                data
            ))
        network.send(remote_nid, message, PROTOCOL_NEXT_HEADER)
        

    def receive(self):
        try:
            return self.in_queue.popleft()
        except IndexError:
            raise NetworkException("No packets for port %d" % self.port)


class ReceiveThread(threading.Thread):
    def run(self):
        while True:
            try:
                message, src_nid, dst_nid = network.receive(PROTOCOL_NEXT_HEADER)
            # Input queue empty (or non-existant) for next header PROTOCOL_NEXT_HEADER
            except (IndexError, KeyError):
                # TODO wait?
                time.sleep(1)
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
            ).append((data, (src_nid, src_port)))

            if log_file != None:
                util.write_log(log_file, "%-30s -> %-30s %s" % (
                    "[%s]:%d" % (src_nid, src_port),
                    "[%s]:%d" % (dst_nid, dst_port),
                    data
                ))


def startup():
    config_section = util.config["transport"]
    global log_file
    if "log" in config_section and config_section.getboolean("log"):
        log_filepath = util.get_log_file_path("transport")
        log_file = open(log_filepath, "a")
        util.write_log(log_file, "Started")
        for k in config_section:
            util.write_log(log_file, "\t%s = %s" % (k, config_section[k]))
    else:
        log_file = None
    
    ReceiveThread().start()


startup()
