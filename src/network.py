import struct

import link


VERSION_SHIFT       = 28
TRAFFIC_CLASS_SHIFT = 20
FLOW_LABEL_SHIFT    = 0

VERSION_MASK        = 0xf0000000
TRAFFIC_CLASS_MASK  = 0x0ff00000
FLOW_LABEL_MASK     = 0x000fffff

# static header fields
version = 0         # not used
traffic_class = 0   # not used
flow_label = 0      # not used

static_masked_fields = (
    version         << VERSION_SHIFT        |
    traffic_class   << TRAFFIC_CLASS_SHIFT  |
    flow_label      << FLOW_LABEL_SHIFT
)


# Message should be binary
def send(locator, data):
    # TODO add address resolution and forwarding table
    # (locator -> interface, where an interface is a multicast group)
    interface = link.get_mcast_grp(locator, link.PackageType.DATA_PACKAGE)

    # ILNPv6 header
    next_header = 42    # identifies skinny transport layer
    payload_length = len(data)
    hop_limit = 0       # TODO set
    source_nid = 0      # TODO
    source_locator = 0  # TODO
    destination_nid = 0 # TODO
    destination_locator = int(locator.replace(":", ""), 16) # hex to int
    header = struct.pack("!4s2sss8s8s8s8s",
        static_masked_fields.to_bytes(4, byteorder="big", signed=False),
        payload_length      .to_bytes(2, byteorder="big", signed=False),
        next_header         .to_bytes(1, byteorder="big", signed=False),
        hop_limit           .to_bytes(1, byteorder="big", signed=False),
        source_nid          .to_bytes(8, byteorder="big", signed=False),
        source_locator      .to_bytes(8, byteorder="big", signed=False),
        destination_nid     .to_bytes(8, byteorder="big", signed=False),
        destination_locator .to_bytes(8, byteorder="big", signed=False)
    )
    message = header + data
    link.send(interface, message)


def receive():
    interface, message = link.receive()

    header = message[:40]
    (
        masked_bytes,
        payload_length_bytes,
        next_header_bytes,
        hop_limit_bytes,
        source_nid_bytes,
        source_locator_bytes,
        destination_nid_bytes,
        destination_locator_bytes
    ) = struct.unpack("!4s2sss8s8s8s8s", header)
    
    # Not currently used
    # masked_fields  = int.from_bytes(masked_bytes, byteorder="big", signed=False)
    # version        = (masked_fields & VERSION_MASK)       >> VERSION_SHIFT
    # traffic_class  = (masked_fields & TRAFFIC_CLASS_MASK) >> TRAFFIC_CLASS_SHIFT
    # flow_label     = (masked_fields & FLOW_LABEL_MASK)    >> FLOW_LABEL_SHIFT

    payload_length      = int.from_bytes(payload_length_bytes,      byteorder="big", signed=False)
    next_header         = int.from_bytes(next_header_bytes,         byteorder="big", signed=False)
    hop_limit           = int.from_bytes(hop_limit_bytes,           byteorder="big", signed=False)
    source_nid          = ":".join([source_nid_bytes[2*i:2*i+2].hex() for i in range(4)])
    source_locator      = ":".join([source_locator_bytes[2*i:2*i+2].hex() for i in range(4)])
    destination_nid     = ":".join([destination_nid_bytes[2*i:2*i+2].hex() for i in range(4)])
    destination_locator = ":".join([destination_locator_bytes[2*i:2*i+2].hex() for i in range(4)])
    print(destination_locator)
    data = message[40:]
    # TODO check if destination locator & nid is this machine
    return data
