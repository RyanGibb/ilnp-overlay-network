import socket
import struct
import sys
import time
from datetime import datetime

# Must have prefix ff00::/8 for multicast
# Also note ffx1::/16 is interface local and ffx2::/16 is link-local
MCAST_GRPS = ['ff12:0:0:0:0:0:0:0', 'ff15:7079:7468:6f6e:6465:6d6f:6d63:6173']
MCAST_PORT = 10000

def heartbeat():
    mcast_addrs = []
    for MCAST_GRP in MCAST_GRPS:
        (family, socktype, proto, canonname, sockaddr) = socket.getaddrinfo(MCAST_GRP, MCAST_PORT, family=socket.AF_INET6, type=socket.SOCK_DGRAM)[0]
        mcast_addrs.append(sockaddr)

    # Create a datagram (UDP) socket
    sock = socket.socket(socket.AF_INET6, socket.SOCK_DGRAM)
    # Set to non-blocking
    sock.settimeout(0)
    # Set time-to-live to 1
    sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 1)
    # Bind to MCAST_PORT
    sock.bind(('', MCAST_PORT))

    # Add to multicast groups
    for mcast_addr in mcast_addrs:
        (mcast_grp, mcast_port, flow_info, scope_id) = mcast_addr
        # remove interface suffix
        mcast_grp = mcast_grp.split("%")[0]
        # Binary representation of mcast_grp. Corresponds to struct in6_addr.
        mcast_group_bin = socket.inet_pton(socket.AF_INET6, mcast_grp)
        # Corresponds to struct in6_mreq with multicast group and interface id in binary representation.
        mreq = mcast_group_bin + struct.pack('=I', scope_id)
        sock.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_JOIN_GROUP, mreq)

    host_name = socket.gethostname()
    host_ip = socket.gethostbyname(host_name)
    while True:
        for mcast_addr in mcast_addrs:
            (mcast_grp, mcast_port, flow_info, scope_id) = mcast_addr
            message = "%s | %s %s | %s" % (str(datetime.now()), host_name, host_ip, mcast_grp)
            sock.sendto(message.encode('utf-8'), mcast_addr)
            print("%-50s <- %s" % ("[%s]:%s" % (mcast_grp, mcast_port), message))
        while True:
            try:
                data, address = sock.recvfrom(1024)
                message = data.decode('utf-8')
                recv_host, recv_port = socket.getnameinfo(address, (socket.NI_NUMERICHOST | socket.NI_NUMERICSERV)) # Gets full IPv6 address with scope
                print("%-50s -> %s" % ("[%s]:%s" % (recv_host, recv_port), message))
            except BlockingIOError:
                break
            except socket.timeout:
                break
        time.sleep(1)
    sock.close()


if __name__ == "__main__":
    heartbeat()
