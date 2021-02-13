import socket
import struct
import os

import util

joined_mcast_grps = set()


# Transforms locators into a multicast address (an interface in our overlay network).
# loc should be a 64 bit hex string
def _get_mcast_grp(loc):    
    # 16 bit hex representation of user ID (modulo 2^16)
    uid_hex = format(os.getuid() % 65536, "x")

    # Must have prefix ff00::/8 for multicast.
    # The next 4 bits are flags. Transient/non-perminant is denoted by 1.
    # The final 4 bits are for the scope. Link-local is denoted by 2.
    mcast_prefix = "ff12"

    # Multicast group address is of the form:
    # +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
    # |        Multicast Prefix       |             UNUSED            |
    # +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
    # |            User ID            |             UNUSED            |
    # +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
    # |                                                               |
    # +                              Loc                              +
    # |                                                               |
    # +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
    return "%s:0:%s:0:%s%%%s" % (
        mcast_prefix,
        uid_hex,
        loc,
        mcast_interface
    )


def send(interface, data):
    mcast_grp = _get_mcast_grp(interface)
    if mcast_grp not in joined_mcast_grps:
        raise IOError("Not joined multicast group '%s'" % mcast_grp)
    (family, socktype, proto, canonname, sockaddr) = socket.getaddrinfo(
        mcast_grp, mcast_port,
        family=socket.AF_INET6, type=socket.SOCK_DGRAM
    )[0]
    # If data larger than buffer size data will be truncated
    if len(data) > buffer_size:
        raise IOError("data length larger than buffer size: %d > %d" %
            (len(data), buffer_size)
        )
    if log_file != None:
        util.write_log(log_file, "%-45s <- %-45s %s" % (
            "[%s]:%d" % (mcast_grp.split("%")[0], mcast_port),
            "[%s]:%d" % (local_addr, mcast_port),
            (str(data[:61]) + '...') if len(data) > 64 else data
        ))
    sock.sendto(data, sockaddr)


def join(interface):
    mcast_grp = _get_mcast_grp(interface)
    if mcast_grp in joined_mcast_grps:
        raise IOError("Already joined multicast group '%s'" % mcast_grp)
    (family, socktype, proto, canonname, sockaddr) = socket.getaddrinfo(
        mcast_grp, mcast_port,
        family=socket.AF_INET6, type=socket.SOCK_DGRAM
    )[0]
    (mcast_addr, mcast_sock_port, flow_info, scope_id) = sockaddr

    # Remove interface suffix
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

    if log_file != None:
        util.write_log(log_file, ("Joined %s" % mcast_grp))


def leave(interface):
    mcast_grp = _get_mcast_grp(interface)
    if mcast_grp not in joined_mcast_grps:
        raise IOError("Not joined multicast group '%s'" % mcast_grp)
    (family, socktype, proto, canonname, sockaddr) = socket.getaddrinfo(
        mcast_grp, mcast_port,
        family=socket.AF_INET6, type=socket.SOCK_DGRAM
    )[0]
    (mcast_addr, mcast_sock_port, flow_info, scope_id) = sockaddr

    # Remove interface suffix
    mcast_addr = mcast_addr.split("%")[0]
    # Binary representation of mcast_addr. Corresponds to struct in6_addr.
    mcast_group_bin = socket.inet_pton(socket.AF_INET6, mcast_addr)

    # Corresponds to struct in6_mreq
    # with multicast group and interface id in binary representations.
    # 16s = 16 chars (bytes) for mcast_group_bin
    # i = signed int for scope_id
    mreq = struct.pack("16si", mcast_group_bin, scope_id)
    sock.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_LEAVE_GROUP, mreq)

    joined_mcast_grps.remove(mcast_grp)

    if log_file != None:
        util.write_log(log_file, ("Removed %s" % mcast_grp))


def receive():
    # buffer_size byte buffer and therefor max message size
    # Ancillary data buffer for IPV6_PKTINFO data item of 20 bytes:
    #  16 bytes for to_address and 4 bytes for interface_id
    data, ancdata, msg_flags, from_address = sock.recvmsg(
        buffer_size, socket.CMSG_SPACE(20)
    )

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
    from_ip_without_interface = from_address[0]

    mcast_grp = util.bytes_to_hex(to_address)

    # Extract locator the packet was recived from from multicast group
    recived_interface = util.bytes_to_hex(to_address[8:16])

    if log_file != None:
        util.write_log(log_file, "%-45s -> %-45s %s" % (
            "[%s]:%s" % (from_ip_without_interface, from_port),
            "[%s]:%d" % (mcast_grp, mcast_port),
            (str(data[:61]) + '...') if len(data) > 64 else data
        ))
    return data, recived_interface, from_ip_without_interface


def startup():
    config_section = util.config["link"]
    
    global mcast_port, mcast_interface, buffer_size
    mcast_port      = config_section.getint("mcast_port")
    mcast_interface = config_section["mcast_interface"]
    buffer_size     = config_section.getint("buffer_size")

    # Create a datagram (UDP) socket
    global sock
    sock = socket.socket(socket.AF_INET6, socket.SOCK_DGRAM)
    # Set to blocking
    sock.settimeout(None)
    # Set time-to-live to 1
    sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 1)
    # Bind to mcast_port
    sock.bind(('', mcast_port))
    # Set the delivery of IPV6_PKTINFO control message on incoming datagrams
    sock.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_RECVPKTINFO, 1)

    global local_addr
    # from https://stackoverflow.com/questions/24196932/how-can-i-get-the-ip-address-from-nic-in-python
    local_addr = os.popen('ip addr show %s' % mcast_interface).read().split("inet6 ")[1].split("/")[0]
    
    global log_file
    log_file = util.get_log_file("link")



startup()

