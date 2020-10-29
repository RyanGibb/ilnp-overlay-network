import socket
import struct
import sys
import os
from enum import Enum


CONFIG_FILENAME = "link_config.cnf"

# Must have prefix ff00::/8 for multicast.
# The next 4 bits are flags. Transient/non-perminant is denoted by 1.
# The final 4 bits are for the scope. Link-local is denoted by 2.
mcast_prefix = "ff12"
mcast_port = 10000
mcast_interface = "eth0"

locators_joined = []

buffer_size = 1024

joined_mcast_grps = set()

class PackageType():
    DATA_PACKAGE = 0
    CONTROL_PACKAGE = 1

# package_type should be PackageType.DATA_PACKAGE or PackageType.CONTROL_PACKAGE
# locator should be a 64 bit hex string
def get_mcast_grp(locator, package_type):
    # 16 bit hex representation of package type (modulo 2^16)
    package_type_hex = format(package_type % 65536, "x")
    # Multicast group address is of the form:
    # +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
    # |        Multicast Prefix       |         Package Type          |
    # +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
    # |                            User ID                            |
    # +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
    # |                                                               |
    # +                            Locator                            +
    # |                                                               |
    # +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
    return "%s:%s:%s:%s:%s%%%s" % (
        mcast_prefix,
        package_type_hex,
        uid_hex_upper,
        uid_hex_lower,
        locator,
        mcast_interface
    )


def send(mcast_grp, message):
    # TODO replace with control plane discovery of groups, current solution
    # means can only receive from a group after sending to the group                  
    if mcast_grp not in joined_mcast_grps:
        raise Exception("Not in mcast_group") # TODO exception types

    (family, socktype, proto, canonname, sockaddr) = socket.getaddrinfo(
        mcast_grp, mcast_port,
        family=socket.AF_INET6, type=socket.SOCK_DGRAM
    )[0]
    if len(message) > buffer_size: # TODO test
        raise Exception()
    sock.sendto(message, sockaddr)
    # print("%-50s <- %s" % ("[%s]:%s" % (mcast_addr, mcast_port), message))


def join(mcast_grp):
    (family, socktype, proto, canonname, sockaddr) = socket.getaddrinfo(
        mcast_grp, mcast_port,
        family=socket.AF_INET6, type=socket.SOCK_DGRAM
    )[0]
    (mcast_addr, mcast_sock_port, flow_info, scope_id) = sockaddr

    # remove interface suffix
    mcast_addr = mcast_addr.split("%")[0]
    # Binary representation of mcast_addr. Corresponds to struct in6_addr.
    mcast_group_bin = socket.inet_pton(socket.AF_INET6, mcast_addr)

    # Corresponds to struct in6_mreq
    # with multicast group and interface id in binary representations.
    # 16s = 16 chars (bytes) for mcast_group_bin
    # i = signed int for scope_id
    mreq = struct.pack("16si", mcast_group_bin, scope_id)
    sock.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_JOIN_GROUP, mreq)

    joined_mcast_grps.add(mcast_grp)


def receive():
    # try:
        # buffer_size byte buffer and therefor max message size
        # Ancillary data buffer for IPV6_PKTINFO data item of 20 bytes:
        #  16 bytes for to_address and 4 bytes for interface_id
    message, ancdata, msg_flags, from_address = sock.recvmsg(
        buffer_size, socket.CMSG_SPACE(20)
    )
    # except BlockingIOError:
    #     return None
    
    assert len(ancdata) == 1
    cmsg_level, cmsg_type, cmsg_data = ancdata[0]
    assert cmsg_level == socket.IPPROTO_IPV6
    assert cmsg_type == socket.IPV6_PKTINFO
    # Destination IP address of packet (multicast group),
    # and the ID of the interface it was received on.
    to_address, interface_id = struct.unpack("16si", cmsg_data)
    
    # Gets IPv6 address and port the packet was sent from
    from_ip, from_port = socket.getnameinfo(from_address,
        (socket.NI_NUMERICHOST | socket.NI_NUMERICSERV)
    )
    # print("%-50s -> %s" % ("[%s]:%s" % (from_ip, from_port), message))

    # Return the multicast group the packet was sent to, which corresponds to
    # the interface it was recieved on for the emulated link layer,
    # and the message.

    # TODO package type and channels
    return (to_address, message)


def startup():
    # Read configuration file
    global mcast_port, mcast_interface, locators_joined, buffer_size
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
        if name == "MCAST_PORT":
            try:
                mcast_port = int(value)
            except ValueError as err:
                print("Error parsing MCAST_PORT from %s: %s" % (CONFIG_FILENAME, err))
                sys.exit(-1)
        elif name == "MCAST_INTERFACE":
            mcast_interface = value
        elif name == "BUFFER_SIZE":
            try:
                buffer_size = int(value)
            except ValueError as err:
                print("Error parsing BUFFER_SIZE from %s: %s" % (CONFIG_FILENAME, err))
                sys.exit(-1)
    config_file.close()

    # 32 bit hex representation of user ID (modulo 2^32)
    global uid_hex_upper, uid_hex_lower
    uid_hex = format(os.getuid() % 4294967296, "x")
    uid_hex_upper = uid_hex[:-4]
    if uid_hex_upper == "":
        uid_hex_upper = "0"
    uid_hex_lower = uid_hex[-4:]

    # Create a datagram (UDP) socket
    global sock
    sock = socket.socket(socket.AF_INET6, socket.SOCK_DGRAM)
    # Set to non-blocking
    sock.settimeout(0) # TODO set timeout?
    # Set time-to-live to 1
    sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 1)
    # Bind to mcast_port
    sock.bind(('', mcast_port))
    # Set the delivery of IPV6_PKTINFO control message on incoming datagrams
    sock.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_RECVPKTINFO, 1)


startup()
