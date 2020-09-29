import socket
import struct
import sys
import time
from datetime import datetime

# Must have prefix ff00::/8 for multicast
# Also note ffx1::/16 is interface local and ffx2::/16 is link-local
# Indexed by channel ID
MCAST_GRPS = [
    'ff15:7079:7468:6f6e:6465:6d6f:6d63:6173', 
    'ff12:0:0:0:0:0:0:1%enp3s0',
    'ff12:0:0:0:0:0:0:2%enp3s0',
    'ff12:0:0:0:0:0:0:3%enp3s0'
]
MCAST_PORT = 10000

def heartbeat():
    mcast_addrs = []
    for MCAST_GRP in MCAST_GRPS:
        (family, socktype, proto, canonname, sockaddr) = socket.getaddrinfo(
            MCAST_GRP, MCAST_PORT,
            family=socket.AF_INET6, type=socket.SOCK_DGRAM
        )[0]
        mcast_addrs.append(sockaddr)

    # Create a datagram (UDP) socket
    sock = socket.socket(socket.AF_INET6, socket.SOCK_DGRAM)
    # Set to non-blocking
    sock.settimeout(0)
    # Set time-to-live to 1
    sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 1)
    # Bind to MCAST_PORT
    sock.bind(('', MCAST_PORT))
    # Set the delivery of IPV6_PKTINFO control message on incoming datagrams
    sock.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_RECVPKTINFO, 1)

    # Maps binary representation of multicast groups to channel IDs.
    mcast_addrs_bin = {}

    # Add to multicast groups
    for mcast_addr in mcast_addrs:
        (mcast_grp, mcast_port, flow_info, scope_id) = mcast_addr
        # remove interface suffix
        mcast_grp = mcast_grp.split("%")[0]
        # Binary representation of mcast_grp. Corresponds to struct in6_addr.
        mcast_group_bin = socket.inet_pton(socket.AF_INET6, mcast_grp)

        mcast_addrs_bin[mcast_group_bin] = len(mcast_addrs_bin) # Channel ID

        # Corresponds to struct in6_mreq
        # with multicast group and interface id in binary representations.
        # 16s = 16 chars (bytes) for mcast_group_bin
        # i = signed int for scope_id
        mreq = struct.pack("16si", mcast_group_bin, scope_id)
        sock.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_JOIN_GROUP, mreq)

    host_name = socket.gethostname()
    host_ip = socket.gethostbyname(host_name)
    while True:
        for channel_id in range(len(mcast_addrs)):
            mcast_addr = mcast_addrs[channel_id]
            (mcast_grp, mcast_port, flow_info, scope_id) = mcast_addr
            message = "%s | %s %s" % (str(datetime.now()), host_name, host_ip)
            sock.sendto(message.encode('utf-8'), mcast_addr)
            print("%-55s Channel %d <- %s" % 
                ("[%s]:%s" % (mcast_grp, mcast_port), channel_id, message)
            )
        while True:
            try:
                # 1024 byte buffer and therefor max message size
                # Ancillary data buffer for IPV6_PKTINFO data item of 20 bytes:
                #  16 bytes for to_address and 4 bytes for interface_id
                data, ancdata, msg_flags, from_address = sock.recvmsg(
                    1024, socket.CMSG_SPACE(20)
                )
                assert len(ancdata) == 1
                cmsg_level, cmsg_type, cmsg_data = ancdata[0]
                assert cmsg_level == socket.IPPROTO_IPV6
                assert cmsg_type == socket.IPV6_PKTINFO
                # Destination IP address of packet (e.g. multicast group),
                # and the ID of the interface it was received on.
                to_address, interface_id = struct.unpack("16si", cmsg_data)
                channel_id = mcast_addrs_bin[to_address]

                message = data.decode('utf-8')
                # Gets IPv6 address and port the packet was sent from
                from_ip, from_port = socket.getnameinfo(from_address,
                    (socket.NI_NUMERICHOST | socket.NI_NUMERICSERV)
                )
                print("%-55s Channel %d -> %s" %
                    ("[%s]:%s" % (from_ip, from_port), channel_id, message)
                )
            except BlockingIOError:
                break
        time.sleep(1)
    sock.close()


if __name__ == "__main__":
    heartbeat()
