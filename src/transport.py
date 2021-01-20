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
        # remote_addr is an ILV (Identfier-Locator Vector)
        remote_nid, remote_port = remote
        
        # TODO multiple locs
        #remote_loc = discovery.get_locs(remote_nid)[0]
        remote_loc = network.local_loc # TODO once discovery is out of band update to use one of the locators that the advertisement was router through
        
        # Transport header is just a 16 bit port
        header = struct.pack("!2s", util.int_to_bytes(remote_port, 2))
        message = header + data
        network.send(remote_loc, remote_nid, message)
        if log_file != None:
            util.write_log(log_file, "%-60s <- %-60s %s" % (
                "[%s]:%d" % remote,
                "%s:%s" % (network.local_loc, network.local_nid),
                data
            ))

    def receive(self):
        try:
            return self.in_queue.popleft()
        except IndexError:
            raise NetworkException("No packets for port %d" % self.port)


class ReceiveThread(threading.Thread):
    def run(self):
        while True:
            try:
                (
                    message, 
                    src_loc, src_nid,
                    dst_loc, dst_nid
                ) = network.receive(PROTOCOL_NEXT_HEADER)
            except NetworkException:
                # TODO wait?
                time.sleep(1)
                continue
            header = message[:2]
            port_bytes = struct.unpack("!2s", header)[0]
            port = util.bytes_to_int(port_bytes)
            data = message[2:]
            # drop if not valid port (if there's no socket bound to this port)
            if port not in in_queues:
                continue
            # TODO do something with dst like support mcast
            in_queues.setdefault(
                port, collections.deque(maxlen=None)
            ).append(data)

            if log_file != None:
                util.write_log(log_file, "%-60s -> %-60s %s" % (
                    ":".join([src_loc, src_nid]),
                    "[%s:%s]:%d" % (dst_loc, dst_nid, port),
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
