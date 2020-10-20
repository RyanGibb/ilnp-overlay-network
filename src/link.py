import socket
import struct
import sys
import os
from enum import Enum

# Must have prefix ff00::/8 for multicast.
# The next 4 bits are flags. Transient/non-perminant is denoted by 1.
# The final 4 bits are for the scope. Link-local is denoted by 2.
MCAST_PREFIX = "ff12"
MCAST_PORT = 10000
MCAST_INTERFACE = "enp3s0"

# 32 bit hex representation of user ID (modulo 2^32)
uid_hex = format(os.getuid() % 4294967296, "x")
uid_hex_upper = uid_hex[:-4]
if uid_hex_upper == "":
    uid_hex_upper = "0"
uid_hex_lower = uid_hex[-4:]

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
        MCAST_PREFIX,
        package_type_hex,
        uid_hex_upper,
        uid_hex_lower,
        locator,
        MCAST_INTERFACE
    )

# Create a datagram (UDP) socket
sock = socket.socket(socket.AF_INET6, socket.SOCK_DGRAM)
# Set to non-blocking
sock.settimeout(0) # TODO set timeout?
# Set time-to-live to 1
sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 1)
# Bind to MCAST_PORT
sock.bind(('', MCAST_PORT))
# Set the delivery of IPV6_PKTINFO control message on incoming datagrams
sock.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_RECVPKTINFO, 1)

host_name = socket.gethostname()
host_ip = socket.gethostbyname(host_name)

BUFFER_SIZE = 1024

joined_mcast_grps = set()


def send(mcast_grp, message):
    # TODO replace with control plane discovery of groups, current solution
    # means can only receive from a group after sending to the group                  
    if mcast_grp not in joined_mcast_grps:
        connect(mcast_grp)
        joined_mcast_grps.add(mcast_grp)

    (family, socktype, proto, canonname, sockaddr) = socket.getaddrinfo(
        mcast_grp, MCAST_PORT,
        family=socket.AF_INET6, type=socket.SOCK_DGRAM
    )[0]
    (mcast_addr, mcast_port, flow_info, scope_id) = sockaddr
    encoded_message = message.encode('utf-8')
    if len(encoded_message) > BUFFER_SIZE: # TODO test
        raise Exception()
    sock.sendto(encoded_message, sockaddr)
    # print("%-50s <- %s" % ("[%s]:%s" % (mcast_addr, mcast_port), message))


def connect(mcast_grp):
    (family, socktype, proto, canonname, sockaddr) = socket.getaddrinfo(
        mcast_grp, MCAST_PORT,
        family=socket.AF_INET6, type=socket.SOCK_DGRAM
    )[0]
    (mcast_addr, mcast_port, flow_info, scope_id) = sockaddr

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

def receive():
    # try:
        # BUFFER_SIZE byte buffer and therefor max message size
        # Ancillary data buffer for IPV6_PKTINFO data item of 20 bytes:
        #  16 bytes for to_address and 4 bytes for interface_id
    data, ancdata, msg_flags, from_address = sock.recvmsg(
        BUFFER_SIZE, socket.CMSG_SPACE(20)
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

    message = data.decode('utf-8')
    # Gets IPv6 address and port the packet was sent from
    from_ip, from_port = socket.getnameinfo(from_address,
        (socket.NI_NUMERICHOST | socket.NI_NUMERICSERV)
    )
    # print("%-50s -> %s" % ("[%s]:%s" % (from_ip, from_port), message))

    # Return the multicast group the packet was sent to, which corresponds to
    # the interface it was recieved on for the emulated link layer,
    # and the message.
    return (to_address, message)
