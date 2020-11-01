import struct
import os
import secrets

import link


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

# identifier used for multicasting over overlay network
MCAST_IDENTIFIER = 'ff12:0:0:0'

locators_joined = []

local_identifier = None
local_locator    = None


def bytes_to_hex(bytes):
    return ":".join([
        format(
            int.from_bytes(
                bytes[2*i:2*i+2],
                byteorder="big"
            ),
            "x"
        ) for i in range(4)
    ])


def send(locator, identifier, data):
    # TODO add address resolution and forwarding table
    # (locator -> interface, where an interface is a multicast group)
    interface = link.get_mcast_grp(locator, link.PackageType.DATA_PACKAGE)

    # ILNPv6 header is of the form:
    # +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
    # |Version| Traffic Class |           Flow Label                  |
    # +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
    # |         Payload Length        |  Next Header  |   Hop Limit   |
    # +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
    # |                                                               |
    # +                         Source Locator                        +
    # |                                                               |
    # +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
    # |                                                               |
    # +                       Source Identifier                       +
    # |                                                               |
    # +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
    # |                                                               |
    # +                      Destination Locator                      +
    # |                                                               |
    # +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
    # |                                                               |
    # +                     Destination Identifier                    +
    # |                                                               |
    # +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
    next_header = 42 # identifies skinny transport layer
    payload_length = len(data)
    hop_limit   = 0 # TODO set
    src_identifier = int(local_identifier.replace(":", ""), 16)
    src_locator    = int(local_locator.replace(":", ""), 16)
    dst_identifier = int(identifier.replace(":", ""), 16)
    dst_locator    = int(locator.replace(":", ""), 16)
    header = struct.pack("!4s2sss8s8s8s8s",
        STATIC_MASKS_FIELD.to_bytes(4, byteorder="big", signed=False),
        payload_length    .to_bytes(2, byteorder="big", signed=False),
        next_header       .to_bytes(1, byteorder="big", signed=False),
        hop_limit         .to_bytes(1, byteorder="big", signed=False),
        src_locator       .to_bytes(8, byteorder="big", signed=False),
        src_identifier    .to_bytes(8, byteorder="big", signed=False),
        dst_locator       .to_bytes(8, byteorder="big", signed=False),
        dst_identifier    .to_bytes(8, byteorder="big", signed=False),
    )

    message = header + data
    link.send(interface, message)


def receive():
    interface, message = link.receive()

    header = message[:40] # Header is 40 bytes
    (
        masked_bytes,
        payload_length_bytes,
        next_header_bytes,
        hop_limit_bytes,
        src_locator_bytes,
        src_identifier_bytes,
        dst_locator_bytes,
        dst_identifier_bytes,
    ) = struct.unpack("!4s2sss8s8s8s8s", header)
    
    # Not currently used
    # masked_fields  = int.from_bytes(masked_bytes, byteorder="big", signed=False)
    # version        = (masked_fields & VERSION_MASK)       >> VERSION_SHIFT
    # traffic_class  = (masked_fields & TRAFFIC_CLASS_MASK) >> TRAFFIC_CLASS_SHIFT
    # flow_label     = (masked_fields & FLOW_LABEL_MASK)    >> FLOW_LABEL_SHIFT

    dst_identifier = bytes_to_hex(dst_identifier_bytes)
    if dst_identifier != local_identifier and dst_identifier == MCAST_IDENTIFIER:
        return
    payload_length = int.from_bytes(payload_length_bytes, byteorder="big", signed=False)
    next_header    = int.from_bytes(next_header_bytes,    byteorder="big", signed=False)
    hop_limit      = int.from_bytes(hop_limit_bytes,      byteorder="big", signed=False)
    src_identifier = bytes_to_hex(src_identifier_bytes)
    src_locator    = bytes_to_hex(src_locator_bytes)
    dst_locator    = bytes_to_hex(dst_locator_bytes)
    data = message[40:]
    # TODO queue based on next_header
    return data, src_locator, src_identifier, dst_locator, dst_identifier


def startup():
    # Read configuration file
    global locators_joined, local_identifier, local_locator
    config_file = open(os.path.join(os.path.dirname(__file__), "..", CONFIG_FILENAME), "r")
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
            locators_joined.append(value)
        elif name == "LOCAL_IDENTIFIER":
            local_identifier = value
    config_file.close()

    for locator in locators_joined:
        link.join(link.get_mcast_grp(locator, link.PackageType.CONTROL_PACKAGE))
        link.join(link.get_mcast_grp(locator, link.PackageType.DATA_PACKAGE))
    
    # TODO improve assignement
    if local_identifier == None:
        local_identifier = bytes_to_hex(secrets.token_bytes(8))
    # TODO add collision detection
    local_locator = locators_joined[0]


startup()
