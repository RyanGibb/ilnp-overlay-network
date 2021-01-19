import socket
import struct
import os

import util

joined_mcast_grps = set()


def send(mcast_grp, message):
    if mcast_grp not in joined_mcast_grps:
        raise IOError("Not joined multicast group '%s'" % mcast_grp)
    (family, socktype, proto, canonname, sockaddr) = socket.getaddrinfo(
        mcast_grp, mcast_port,
        family=socket.AF_INET6, type=socket.SOCK_DGRAM
    )[0]
    # If message larger than buffer size message will be truncated
    if len(message) > buffer_size:
        raise IOError("Message length larger than buffer size: %d > %d" %
            (len(message), buffer_size)
        )
    sock.sendto(message, sockaddr)

    if log_file != None:
        util.write_log(log_file, "%-60s <- %-60s %s" % (
            "[%s]:%d" % (mcast_grp, mcast_port),
            "[%s]:%d" % (local_addr, mcast_port),
            message
        ))


def join(mcast_grp):
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


def receive():
    # buffer_size byte buffer and therefor max message size
    # Ancillary data buffer for IPV6_PKTINFO data item of 20 bytes:
    #  16 bytes for to_address and 4 bytes for interface_id
    message, ancdata, msg_flags, from_address = sock.recvmsg(
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

    if log_file != None:
        util.write_log(log_file, "%-60s -> %-60s %s" % (
            "[%s]:%s" % (from_ip, from_port),
            "[%s]:%d" % (util.bytes_to_hex(to_address), mcast_port),
            message
        ))
    return to_address, message


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
    local_addr = socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET6)[0][4][0]
    
    global log_file
    if "log" in config_section and config_section.getboolean("log"):
        log_filepath = util.get_log_file_path("link")
        log_file = open(log_filepath, "a")
        util.write_log(log_file, "Started")
        for k in config_section:
            util.write_log(log_file, "\t%s = %s" % (k, config_section[k]))
    else:
        log_file = None



startup()

