import struct
import os
import secrets
import collections
import threading
import os
import time
import random

import link
import discovery
import util
from util import NetworkException
from collections import defaultdict

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

LOC_UPDATE_NEXT_HEADER = 44

# Output circular queues
out_queue = collections.deque(maxlen=None)
# Map of input circular queues indexed by next header
in_queues = {}

# Map of locators to interfaces (which are locators than this node has joined),
# and timestamps (seconds since epoch).
# Populated by backwards learning.
loc_to_interface = {}

# Map of identifiers to timestamps. Keeps track of active unicast ILNP sessions
# for determining where to send locator updates.
# Active here means sent in the past active_uncast_session_ttl seconds.
active_nids =   {}


def map_locator_to_interface(loc):
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


# Send now, mapping nid to locator, and locator to interface.
def _send(loc, nid, data, next_header, interface=None):
    if interface == None:
        interface = map_locator_to_interface(loc)
        if interface == None:
            raise NetworkException("No interface to locator: %s" % loc)
    local_loc = interface
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
    if log_file != None:
        util.write_log(log_file, "%-45s <- %-30s %s %s" % (
            ":".join([loc, nid]) + "%" + interface,
            ":".join([local_loc, local_nid]),
            "(%5d, %2d, %2d)" % (payload_length, next_header, hop_limit),
            (str(data[:29]) + '...') if len(data) > 32 else data
        ))
    message = header + data
    link.send(interface, message)
    # Don't count discovery and locator update messages as active
    if loc != ALL_NODES_LOC:
        active_nids[nid] = time.time()


# Add to send queue.
def send(loc, nid, data, next_header):
    # note if maxlen set this will overwrite the oldest value
    return out_queue.append((loc, nid, data, next_header))


# Sends messages in send queue
class SendThread(threading.Thread):
    def run(self):
        global send_cv
        send_cv = threading.Condition()
        while True:
            try:
                _send(*out_queue.popleft())
            except IndexError:
                with send_cv:
                    send_cv.wait()
                continue
            except Exception as e:
                if log_file != None:
                    util.write_log(log_file, "Error sending: %s" % e)


# Recieve now
def _receive():
    message, recieved_interface, from_ip = link.receive()

    header = message[:40] # Header is 40 bytes
    data = message[40:]

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
    src_loc        = util.bytes_to_hex(src_loc_bytes)
    src_nid        = util.bytes_to_hex(src_nid_bytes)
    dst_loc        = util.bytes_to_hex(dst_loc_bytes)
    dst_nid        = util.bytes_to_hex(dst_nid_bytes)

    # Ignore own messages, if they aren't to us
    if from_ip == link.local_addr and dst_nid != local_nid:
        # Unless they are a discovery message, in which case we will
        # store the mapping (for local name resoltion) but will not respond
        # if next_header == discovery.DISCOVERY_NEXT_HEADER:
        #     discovery.process_message(data, recieved_interface)
        return
    
    # Add mapping from source locator to the interface the packet was recieved on
    loc_to_interface[src_loc] = recieved_interface, time.time()

    # If not for us, try to forward
    if dst_nid != local_nid and dst_loc != ALL_NODES_LOC:
        # Only forward if the destination locator of the packet is different from
        # the interface it was received on.
        if recieved_interface != dst_loc:
            interface = map_locator_to_interface(dst_loc)
            if interface != None:
                mutable_message = bytearray(message)
                if mutable_message[7] > 0:
                    # Decrement hop limit
                    mutable_message[7] -= 1
                    hop_limit -= 1
                    link.send(interface, bytes(mutable_message))
                    util.write_log(log_file, "%-45s <- %-30s %s %s" % (
                        ":".join([dst_loc, dst_nid]) + "%" + interface,
                        "*" + ":".join([src_loc, src_nid]),
                        "(%5d, %2d, %2d)" % (payload_length, next_header, hop_limit),
                        (str(data[:29]) + '...') if len(data) > 32 else data
                    ))
        return

    if log_file != None:
        util.write_log(log_file, "%-45s -> %-30s %s %s" % (
            ":".join([src_loc, src_nid]) + "%" + recieved_interface,
            ":".join([dst_loc, dst_nid]),
            "(%5d,%3d,%3d)" % (payload_length, next_header, hop_limit),
            (str(data[:29]) + '...') if len(data) > 32 else data
        ))

    if next_header == discovery.DISCOVERY_NEXT_HEADER:
        solititation = discovery.process_message(data, recieved_interface)
        # If discovery message was a solititation
        if solititation:
            # timestamp of last recieved solititation
            global solititation_timestamp
            solititation_timestamp = time.time()

            # Respond to solititation
            advertisement = discovery.get_advertisement(recieved_interface, local_nid)
            # send advertisement to all interfaces
            for loc in locs_joined:
                _send(
                    ALL_NODES_LOC, "0:0:0:0", advertisement,
                    discovery.DISCOVERY_NEXT_HEADER, map_locator_to_interface(loc)
                )

        # Forward discovery message to other interfaces
        for loc in locs_joined:
            if loc == recieved_interface:
                continue
            mutable_message = bytearray(message)
            if mutable_message[7] > 0:
                # Decrement hop limit
                mutable_message[7] -= 1
                link.send(map_locator_to_interface(loc), bytes(mutable_message))
        
    elif next_header == LOC_UPDATE_NEXT_HEADER:
        advertisement = struct.unpack("!?", data[0:1])[0]
        # If a locator upate advertisement (as oppsed to an acknowledgement)
        if advertisement:
            # Process locator updates
            # Start at 1 (after type field)
            new_locs = [util.bytes_to_hex(struct.unpack("!8s", data[i:i+8])[0]) for i in range(1, len(data), 8)]
            discovery.locator_update(src_nid, new_locs)
            # Send locator update acknowledgement (only used for backwards learning)
            loc_update_ack = struct.pack("!?", False)
            _send(new_locs[0], src_nid, loc_update_ack, LOC_UPDATE_NEXT_HEADER, interface=recieved_interface)
        
    else:
        active_nids[src_nid] = time.time()
        return (next_header, (data, src_loc, src_nid, dst_loc, dst_nid))


# Receive from queue
def receive(next_header):
    # Raises IndexError if no elements present, or KeyError if no queue exists
    return in_queues[next_header].popleft()


# Recieves messages and adds them to recieve queue
class ReceiveThread(threading.Thread):
    def run(self):
        global receive_cv
        receive_cv = defaultdict(threading.Condition)
        # Queues by next header
        while True:
            try:
                returned = _receive()
                if returned != None:
                    next_header, returned_tuple = returned
                    in_queues.setdefault(
                        next_header, collections.deque(maxlen=None)
                    ).append((
                        returned_tuple
                    ))
                    with receive_cv[next_header]:
                        receive_cv[next_header].notify()
            except Exception as e:
                if log_file != None:
                    util.write_log(log_file, "Error recieving: %s" % e)


class SolititationThread(threading.Thread):
    def run(self):
        while True:
            try:
                global solititation_timestamp
                # don't send solititation if solititation received in passed discovery.wait_time
                if solititation_timestamp == 0 or time.time() - solititation_timestamp > discovery.wait_time:
                    for loc in locs_joined:
                        # nid doesn't matter for ALL_NODES_LOC
                        _send(
                            ALL_NODES_LOC, "0:0:0:0", discovery.get_solititation(loc, local_nid),
                            discovery.DISCOVERY_NEXT_HEADER, loc
                        )
                    solititation_timestamp = time.time()
                # sleep a random time from (discovery.wait_time / 2) to discovery.wait_time
                time.sleep(random.random() * discovery.wait_time / 2 + discovery.wait_time / 2)
            except Exception as e:
                if log_file != None:
                    util.write_log(log_file, "Error sending solicitation: %s" % e)


class MoveThread(threading.Thread):
    def __init__(self, loc_cycle, move_time, handover_time):
        threading.Thread.__init__(self)
        self.loc_cycle = loc_cycle
        self.move_time = move_time
        self.handover_time = handover_time
        self.loc_cycle_index = 0

    def run(self):
        while True:
            time.sleep(self.move_time)
            try:
                new_loc_cycle_index = (self.loc_cycle_index + 1) % len(self.loc_cycle)
                new_locs_joined = self.loc_cycle[new_loc_cycle_index]
                global locs_joined
                if log_file != None:
                    util.write_log(log_file, "Moving from %s to %s" % (locs_joined, new_locs_joined))
                for loc in new_locs_joined:
                    if loc not in self.loc_cycle[self.loc_cycle_index]:
                        link.join(loc)
                new_locs_joined_bytes = [util.hex_to_bytes(joined_loc, 8) for joined_loc in new_locs_joined]
                # True for locator update advertisement
                loc_update_advrt = struct.pack("!?" + "8s" * len(new_locs_joined), True, *new_locs_joined_bytes)
                for dst_nid, timestamp in active_nids.items():
                    if time.time() - timestamp > active_uncast_session_ttl:
                        del active_nids[dst_nid]
                        continue
                    # Send locator update advertisement on interface to first new locator
                    # so backwards learning can be done on locator update.
                    _send(new_locs_joined[0], dst_nid, loc_update_advrt, LOC_UPDATE_NEXT_HEADER)
                    # TODO wait for ack
                
                time.sleep(self.handover_time)

                # Reset backwards learning
                global loc_to_interface
                to_remove=[]
                for mapped_loc, (interface, timestamp) in loc_to_interface.items():
                    if interface not in new_locs_joined:
                        to_remove.append(mapped_loc)
                for mapped_loc in to_remove:
                    del loc_to_interface[mapped_loc]
                # Leave locators
                for loc in locs_joined:
                    if loc not in new_locs_joined:
                        link.leave(loc)
                
                self.loc_cycle_index = new_loc_cycle_index
                locs_joined = new_locs_joined
            except Exception as e:
                if log_file != None:
                    util.write_log(log_file, "Error moving: %s" % e)


def startup():
    config_section = util.config["network"]
    
    global locs_joined
    loc_cycle = [[loc.strip() for loc in cycle.split(",")] for cycle in config_section["locators"].split("-")]
    locs_joined = loc_cycle[0]
    for loc in locs_joined:
        link.join(loc)
        # For locs joined, send to own interface
        # Timestamp of None indicates that this is a non-expiring mapping
        loc_to_interface[loc] = loc, None

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
        backwards_learning_ttl = 300000
    
    global active_uncast_session_ttl
    if "active_uncast_session_ttl" in config_section:
        active_uncast_session_ttl = config_section["active_uncast_session_ttl"]
    else:
        active_uncast_session_ttl = 300000

    global log_file
    log_file = util.get_log_file("network")
    
    ReceiveThread().start()
    SendThread().start()

    # Discovery startup should run after link startup
    discovery.startup()

    global solititation_timestamp
    solititation_timestamp = 0
    # Start thread to send solititation messages from discovery module
    SolititationThread().start()

    if len(loc_cycle) > 1:
        if "move_time" in config_section:
            move_time = config_section.getfloat("move_time")
        else:
            move_time = 20
        if "handover_time" in config_section:
            handover_time = config_section.getfloat("handover_time")
        else:
            handover_time = 10
        MoveThread(loc_cycle, move_time, handover_time).start()


startup()
