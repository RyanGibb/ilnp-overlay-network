import struct
import os
import secrets
import collections
import threading

import link
from util import *

CONFIG_FILENAME = "network_config.cnf"

VERSION_SHIFT       = 28
TRAFFIC_CLASS_SHIFT = 20
FLOW_LABEL_SHIFT    = 0

VERSION_MASK        = 0xf0000000
TRAFFIC_CLASS_MASK  = 0x0ff00000
FLOW_LABEL_MASK     = 0x000fffff

# static header fields
VERSION = 0         # not used
TRAFFIC_CLASS = 0   # not used
FLOW_LABEL = 0      # not used

STATIC_MASKS_FIELD = (
    VERSION         << VERSION_SHIFT        |
    TRAFFIC_CLASS   << TRAFFIC_CLASS_SHIFT  |
    FLOW_LABEL      << FLOW_LABEL_SHIFT
)

# nid used for multicasting over overlay network
MCAST_NID = 'ff12:0:0:0'

locs_joined = []

local_nid = None
local_loc = None

# IO circular queues
out_queue = collections.deque(maxlen=None)
in_queues = {} # map of queues


def _send(loc, nid, data):
    # TODO add address resolution and forwarding table
    # (loc -> interface, where an interface is a multicast group)
    interface = link.get_mcast_grp(loc, link.PackageType.DATA_PACKAGE)

    # ILNPv6 header is of the form:
    # +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
    # |Version| Traffic Class |           Flow Label                  |
    # +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
    # |         Payload Length        |  Next Header  |   Hop Limit   |
    # +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
    # |                                                               |
    # +                           Source Loc                          +
    # |                                                               |
    # +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
    # |                                                               |
    # +                           Source NID                          +
    # |                                                               |
    # +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
    # |                                                               |
    # +                        Destination Loc                        +
    # |                                                               |
    # +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
    # |                                                               |
    # +                        Destination NID                        +
    # |                                                               |
    # +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
    next_header = 42 # identifies skinny transport layer
    payload_length = len(data)
    hop_limit   = 0 # TODO set
    header = struct.pack("!4s2sss8s8s8s8s",
        STATIC_MASKS_FIELD.to_bytes(4, byteorder="big", signed=False),
        int_to_bytes(payload_length, 2),
        int_to_bytes(next_header,   1),
        int_to_bytes(hop_limit,     1),
        hex_to_bytes(local_loc,     8),
        hex_to_bytes(local_nid,      8),
        hex_to_bytes(loc,           8),
        hex_to_bytes(nid,            8),
    )

    message = header + data
    link.send(interface, message)


def _receive():
    package_type, message = link.receive()

    header = message[:40] # Header is 40 bytes
    (
        masked_bytes,
        payload_length_bytes,
        next_header_bytes,
        hop_limit_bytes,
        src_loc_bytes,
        src_nid_bytes,
        dst_loc_bytes,
        dst_nid_bytes,
    ) = struct.unpack("!4s2sss8s8s8s8s", header)
    
    # Not currently used
    #masked_fields = int.from_bytes(masked_bytes, byteorder="big", signed=False)
    #version       = (masked_fields & VERSION_MASK)       >> VERSION_SHIFT
    #traffic_class = (masked_fields & TRAFFIC_CLASS_MASK) >> TRAFFIC_CLASS_SHIFT
    #flow_label    = (masked_fields & FLOW_LABEL_MASK)    >> FLOW_LABEL_SHIFT

    dst_nid = bytes_to_hex(dst_nid_bytes)
    if (dst_nid != local_nid and
        dst_nid != MCAST_NID):
        return
    payload_length = bytes_to_int(payload_length_bytes)
    next_header    = bytes_to_int(next_header_bytes)
    hop_limit      = bytes_to_int(hop_limit_bytes)
    src_nid = bytes_to_hex(src_nid_bytes)
    src_loc    = bytes_to_hex(src_loc_bytes)
    dst_loc    = bytes_to_hex(dst_loc_bytes)
    data = message[40:]
    return next_header, package_type, (
        data, src_loc, src_nid, dst_loc, dst_nid
    )


class ReceiveThread(threading.Thread):
    def run(self):
        # Queues by next header
        while True:
            received = _receive()
            if received == None:
                continue
            next_header, package_type, result = received
            # TODO process control packages
            if package_type == link.PackageType.DATA_PACKAGE:
                in_queues.setdefault(
                    next_header, collections.deque(maxlen=None)
                ).append(result)


def receive(next_header):
    # Raises IndexError if no elements present
    try:
        return in_queues[next_header].popleft()
    except IndexError:
        raise NetworkException("Input queue empty for next header: %d" % next_header)
    except KeyError:
        raise NetworkException("Invalid next")


class SendThread(threading.Thread):
    def run(self):
        while True:
            try:
                _send(*out_queue.popleft())
            except IndexError:
                # TODO wait here?
                continue


def send(loc, nid, data):
    # note if maxlen set this will overwrite the oldest value
    return out_queue.append((loc, nid, data))


def startup():
    # Read configuration file
    global locs_joined, local_id, local_loc
    filepath = os.path.join(os.path.dirname(__file__), "..", CONFIG_FILENAME)
    config_file = open(filepath, "r")
    for line in config_file:
        line = line.strip()
        if len(line) == 0 or line[0] == '#':
            continue
        line_split = line.split(":", 1)
        if len(line_split) != 2:
            continue
        name, value = line_split
        value = value.split("#")[0].strip()
        if name == "LOCATOR":
            locs_joined.append(value)
        elif name == "LOCAL_NID":
            local_nid = value
    config_file.close()

    for loc in locs_joined:
        link.join(link.get_mcast_grp(loc, link.PackageType.CONTROL_PACKAGE))
        link.join(link.get_mcast_grp(loc, link.PackageType.DATA_PACKAGE))
    
    # TODO improve assignement
    if local_nid == None:
        local_nid = bytes_to_hex(secrets.token_bytes(8))
    # TODO add collision detection
    local_loc = locs_joined[0]
    receive_thread = ReceiveThread()
    receive_thread.start()
    send_thread = SendThread()
    send_thread.start()


startup()
