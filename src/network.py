import struct
import os
import secrets
import collections
import threading
import os
import time

import link
import discovery
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

ALL_NODES_LOC = 'ff02:0:0:1'

# Output circular queues
out_queue = collections.deque(maxlen=None)
# Map of input circular queues indexed by next header
in_queues = {}

# Map of locators to interfaces and their timestamp (seconds since epoch).
# Note that interfaces are locators themselves,
# but represent the network to forward the packet to,
# to rather than the desination network.
# Populated by backwards learning.
loc_to_interface = {}


def get_interface(loc):
    # Interface is a locator that identifies the network to foward the packet to.
    entry = loc_to_interface.get(loc)
    if entry != None:
        interface, timestamp = entry
    else:
        return None
    # If mapping expired (timestamp == None means this is a non-expiring mapping)
    if interface != None and timestamp != None and time.time() - timestamp > backwards_learning_ttl:
        loc_to_interface[loc] = None
        return None
    else:
        return interface


class PackageType():
    DATA_PACKAGE = 0
    CONTROL_PACKAGE = 1


# Send now, to specific interface.
def send_interface(nid, loc, interface, data, pkg_type=PackageType.DATA_PACKAGE):
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
    next_header    = 42 # identifies skinny transport layer
    payload_length = len(data)
    hop_limit      = default_hop_limit
    header = struct.pack("!4s2sss8s8s8s8s",
        STATIC_MASKS_FIELD.to_bytes(4, byteorder="big", signed=False),
        util.int_to_bytes(payload_length, 2),
        util.int_to_bytes(next_header,    1),
        util.int_to_bytes(hop_limit,      1),
        util.hex_to_bytes(local_loc,      8),
        util.hex_to_bytes(local_nid,      8),
        util.hex_to_bytes(loc,            8),
        util.hex_to_bytes(nid,            8),
    )

    message = header + data
    link.send(interface, pkg_type, message)

    if log_file != None:
        util.write_log(log_file, "%-4s %-90s <- %-60s %s" % (
            "(%d)" % header[7], # hop limit
            ":".join([loc, nid]) + "%" + interface,
            ":".join([local_loc, local_nid]),
            data
        ))


# Send now, mapping nid to locator, and locator to interface.
def _send(nid, data, pkg_type=PackageType.DATA_PACKAGE):
    # TODO multiple locs
    loc = discovery.get_locs(nid)[0]
    interface = get_interface(loc)
    if interface not in locs_joined:
        raise NetworkException("No interface to loctor: %s" % loc)
    send_interface(nid, loc, interface, data, pkg_type)


# Add to send queue.
# Only sends data package types.
def send(nid, data):
    # note if maxlen set this will overwrite the oldest value
    return out_queue.append((nid, data))


# Sends messages in send queue
class SendThread(threading.Thread):
    def run(self):
        while True:
            try:
                _send(*out_queue.popleft())
            except NetworkException as e:
                print("Error sending: %s" % e)
            except IndexError:
                # TODO wait here?
                continue


# Recieve now
def _receive():
    message, pkg_type, recieved_interface, from_ip = link.receive()

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
    # masked_fields = int.from_bytes(masked_bytes, byteorder="big", signed=False)
    # version       = (masked_fields & VERSION_MASK)       >> VERSION_SHIFT
    # traffic_class = (masked_fields & TRAFFIC_CLASS_MASK) >> TRAFFIC_CLASS_SHIFT
    # flow_label    = (masked_fields & FLOW_LABEL_MASK)    >> FLOW_LABEL_SHIFT
    payload_length = util.bytes_to_int(payload_length_bytes)
    next_header    = util.bytes_to_int(next_header_bytes)
    hop_limit      = util.bytes_to_int(hop_limit_bytes)
    dst_nid        = util.bytes_to_hex(dst_nid_bytes)
    src_nid        = util.bytes_to_hex(src_nid_bytes)
    src_loc        = util.bytes_to_hex(src_loc_bytes)
    dst_loc        = util.bytes_to_hex(dst_loc_bytes)

    # Ignore own messages, if they aren't to us
    if from_ip == link.local_addr and dst_nid != local_nid:
        return
    
    # Add mapping from source locator to the interface the packet was recieved on
    loc_to_interface[src_loc] = recieved_interface, time.time()

    # If not for us, try to forward
    if dst_nid != local_nid and dst_loc != ALL_NODES_LOC:
        interface = get_interface(dst_loc)
        if interface != None:
            mutable_message = bytearray(message)
            if mutable_message[7] > 0:
                # Decrement hop limit
                mutable_message[7] -= 1
                link.send(interface, pkg_type, bytes(mutable_message))
        return

    data = message[40:]
    if log_file != None:
        util.write_log(log_file, "%-4s %-90s -> %-60s %s" % (
            "(%d)" % header[7], # hop limit
            ":".join([src_loc, src_nid]) + "%" + recieved_interface,
            ":".join([dst_loc, dst_nid]),
            data
        ))

    if pkg_type == PackageType.DATA_PACKAGE:
        in_queues.setdefault(
                next_header, collections.deque(maxlen=None)
        ).append((
            data, src_loc, src_nid, dst_loc, dst_nid
        ))
    elif pkg_type == PackageType.CONTROL_PACKAGE:
        response = discovery.process_message(data, recieved_interface)
        if response != None:
            send_interface("0:0:0:0", ALL_NODES_LOC, recieved_interface, response, PackageType.CONTROL_PACKAGE)
        # Forward discovery message to other interfaces
        for interface in locs_joined:
            if interface == recieved_interface:
                continue
            mutable_message = bytearray(message)
            if mutable_message[7] > 0:
                # Decrement hop limit
                mutable_message[7] -= 1
                link.send(interface, PackageType.CONTROL_PACKAGE, bytes(mutable_message))


# Receive from queue
def receive(next_header):
    # Raises IndexError if no elements present, or KeyError if no queue exists
    return in_queues[next_header].popleft()


# Recieves messages and adds them to recieve queue
class ReceiveThread(threading.Thread):
    def run(self):
        # Queues by next header
        while True:
            try:
                _receive()
            except NetworkException as e:
                print("Error recieving: %s" % e)


class SolititationThread(threading.Thread):
    def run(self):
        while True:
            try:
                for interface in locs_joined:
                    # TODO don't send solititation if solititation received from interface in passed discovery.wait_time
                    # nid doesn't matter for ALL_NODES_LOC
                    send_interface("0:0:0:0", ALL_NODES_LOC, interface, discovery.get_solititation(interface), PackageType.CONTROL_PACKAGE)
            except NetworkException as e:
                print("Error sending solicitation message: %s" % e)
            time.sleep(discovery.wait_time)


def startup():
    config_section = util.config["network"]
    
    global locs_joined, local_loc
    locs_joined = [loc.strip() for loc in config_section["locators"].split(",")]
    for loc in locs_joined:
        link.join(loc, PackageType.CONTROL_PACKAGE)
        link.join(loc, PackageType.DATA_PACKAGE)
        # For locs joined, send to own interface
        # Timestamp of None indicates that this is a non-expiring mapping
        loc_to_interface[loc] = loc, None
    local_loc = locs_joined[0]

    global local_nid
    if "nid" in config_section:
        local_nid = config_section["nid"]
    else:
        # TODO improve assignement
        local_nid = util.bytes_to_hex(secrets.token_bytes(8))
    # TODO add collision detection

    global default_hop_limit
    if "default_hop_limit" in config_section:
        default_hop_limit = config_section["default_hop_limit"]
    else:
        default_hop_limit = 3
    
    # Time that locator to interface mappings learnt by backwards learning will be valid
    global backwards_learning_ttl
    if "backwards_learning_ttl" in config_section:
        backwards_learning_ttl = config_section["backwards_learning_ttl"]
    else:
        backwards_learning_ttl = 20

    global log_file
    if "log" in config_section and config_section.getboolean("log"):
        log_filepath = util.get_log_file_path("network")
        log_file = open(log_filepath, "a")
        util.write_log(log_file, "Started")
        for k in config_section:
            util.write_log(log_file, "\t%s = %s" % (k, config_section[k]))
    else:
        log_file = None
    
    ReceiveThread().start()
    SendThread().start()

    # Discovery startup should run after link startup
    discovery.startup(local_nid, locs_joined)

    # Start thread to send solititation messages from discovery module
    SolititationThread().start()


startup()
