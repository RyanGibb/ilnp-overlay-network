import struct
import os
import secrets
import collections
import threading
import os

import link
import util
from util import NetworkException

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

# IO circular queues
out_queue = collections.deque(maxlen=None)
in_queues = {} # map of queues


class PackageType():
    DATA_PACKAGE = 0
    CONTROL_PACKAGE = 1


# package_type should be PackageType.DATA_PACKAGE or PackageType.CONTROL_PACKAGE
# loc should be a 64 bit hex string
def get_mcast_grp(loc, package_type):
    # 16 bit hex representation of package type (modulo 2^16)
    package_type_hex = format(package_type % 65536, "x")
    
    # 32 bit hex representation of user ID (modulo 2^16)
    uid_hex = format(os.getuid() % 65536, "x")

    # Must have prefix ff00::/8 for multicast.
    # The next 4 bits are flags. Transient/non-perminant is denoted by 1.
    # The final 4 bits are for the scope. Link-local is denoted by 2.
    mcast_prefix = "ff12"

    # Multicast group address is of the form:
    # +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
    # |        Multicast Prefix       |             UNUSED            |
    # +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
    # |         Package Type          |            User ID            |
    # +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
    # |                                                               |
    # +                              Loc                              +
    # |                                                               |
    # +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
    return "%s:0:%s:%s:%s%%%s" % (
        mcast_prefix,
        package_type_hex,
        uid_hex,
        loc,
        link.mcast_interface
    )


def _send(loc, nid, data):
    # TODO add address resolution and forwarding table
    # (loc -> interface, where an interface is a multicast group)
    interface = get_mcast_grp(loc, PackageType.DATA_PACKAGE)

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
        util.int_to_bytes(payload_length, 2),
        util.int_to_bytes(next_header,   1),
        util.int_to_bytes(hop_limit,     1),
        util.hex_to_bytes(local_loc,     8),
        util.hex_to_bytes(local_nid,      8),
        util.hex_to_bytes(loc,           8),
        util.hex_to_bytes(nid,            8),
    )

    message = header + data
    link.send(interface, message)


def _receive():
    to_address, message = link.receive()

    # Exctract packet type from multicast group
    package_type = int.from_bytes(to_address[2:4], byteorder="big")

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

    dst_nid = util.bytes_to_hex(dst_nid_bytes)
    if (dst_nid != local_nid and
        dst_nid != MCAST_NID):
        return
    payload_length = util.bytes_to_int(payload_length_bytes)
    next_header    = util.bytes_to_int(next_header_bytes)
    hop_limit      = util.bytes_to_int(hop_limit_bytes)
    src_nid        = util.bytes_to_hex(src_nid_bytes)
    src_loc        = util.bytes_to_hex(src_loc_bytes)
    dst_loc        = util.bytes_to_hex(dst_loc_bytes)
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
            if package_type == PackageType.DATA_PACKAGE:
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
    config_section = util.config["network"]
    
    global locs_joined, local_loc
    locs_joined = [loc.strip() for loc in config_section["locators"].split(",")]
    for loc in locs_joined:
        link.join(get_mcast_grp(loc, PackageType.CONTROL_PACKAGE))
        link.join(get_mcast_grp(loc, PackageType.DATA_PACKAGE))
    local_loc = locs_joined[0]

    global local_nid
    if "local_nid" in config_section:
        local_nid = config_section["local_nid"]
    else:
        # TODO improve assignement
        local_nid = util.bytes_to_hex(secrets.token_bytes(8))
    # TODO add collision detection

    global log_file
    if "log" in config_section and config_section.getboolean("log"):
        log_filepath = util.get_log_file_path("network")
        log_file = open(log_filepath, "a")
    else:
        log_file = None
    
    ReceiveThread().start()
    SendThread().start()


startup()






    