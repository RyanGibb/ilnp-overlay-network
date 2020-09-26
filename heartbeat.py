import socket
import struct
import sys
import time
from datetime import datetime

MCAST_GRP = '224.3.29.71'
MCAST_PORT = 10000

def heartbeat():
    # Create the datagram socket
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    # Set a timeout so the socket does not block indefinitely when trying
    # to receive data.
    sock.settimeout(0)

    # Set the time-to-live for messages to 1 so they do not go past the
    # local network segment.
    ttl = struct.pack('b', 1)
    sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, ttl)


    # Bind to the server address
    sock.bind(('', MCAST_PORT))

    # Tell the operating system to add the socket to the multicast group
    # on all interfaces.
    group = socket.inet_aton(MCAST_GRP)
    mreq = struct.pack('4sL', group, socket.INADDR_ANY)
    sock.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)


    host_name = socket.gethostname()
    host_ip = socket.gethostbyname(host_name)
    while True:
        message = "%s | %s | %s" % (str(datetime.now()), host_name, host_ip)
        sock.sendto(message.encode('utf-8'), (MCAST_GRP, MCAST_PORT))
        print("%-25s <- %s" % ("[%s]:%s" % (MCAST_GRP, MCAST_PORT), message))
        
        while True:
            try:
                data, address = sock.recvfrom(1024)
                message = data.decode('utf-8')
                recv_host, recv_port = socket.getnameinfo(address, (socket.NI_NUMERICHOST | socket.NI_NUMERICSERV)) # Gets full IPv6 address with scope
                print("%-25s -> %s" % ("[%s]:%s" % (recv_host, recv_port), message))
            except BlockingIOError:
                break
            except socket.timeout:
                break

        time.sleep(5)
    sock.close()


if __name__ == "__main__":
    heartbeat()
