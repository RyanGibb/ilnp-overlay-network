import socket
import os
import sys
import threading

import transport
import discovery

mtu = 65487

sock_filename = "sock"
sock_addr = os.path.join(os.path.dirname(__file__), sock_filename)

unix_sock = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)

try:
    os.remove(sock_addr)
except OSError:
    pass

unix_sock.bind(sock_addr)

udp_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

udp_sock.bind(("", 0 if len(sys.argv) <= 2 else int(sys.argv[2])))
server_port = udp_sock.getsockname()[1]
print("Listening on %s" % server_port)

mapping_update_cv = threading.Condition()

proxy_map = {}


class SendThread(threading.Thread):
    def run(self):
        while True:
            data, addr = udp_sock.recvfrom(mtu)
            local_port = addr[1]
            remote, ilnp_sock = proxy_map[local_port]
            try:
                remote_addrinfo = discovery.getaddrinfo(remote)
                print("%s -> %s: %s" % (local_port, remote_addrinfo, data))
                ilnp_sock.send(remote_addrinfo, data)
            except transport.NetworkException as e:
                print("Network Exception: %s" % e.message)


class ReceiveThread(threading.Thread):
    def __init__(self, ilnp_sock, local_port):
        super().__init__()
        self.ilnp_sock = ilnp_sock
        self.local_port = local_port
    
    def run(self):
        while True:
            data, src_addrinfo, dst_addrinfo, interface = self.ilnp_sock.receive()
            local_port = dst_addrinfo[1]
            print("%s <- %s: %s" % (local_port, src_addrinfo, data))
            try:
                udp_sock.sendto(data, ("localhost", local_port))
            except transport.NetworkException as e:
                print("Network Exception: %s" % e.message)


SendThread().start()


while True:
    msg_bytes, addr = unix_sock.recvfrom(mtu)
    
    # receive proxy info
    # local_port = port of UDP socket connecting to udp_sock, and used as ILNP local port
    local_port_str, remote_ilv, remort_port_str = msg_bytes.decode("utf-8").split()
    local_port = int(local_port_str)
    remort_port = int(remort_port_str)
    
    # respond with server (udp_sock) port
    unix_sock.sendto(str(server_port).encode("utf-8"), addr)

    ilnp_sock = transport.Socket()
    ilnp_sock.bind(local_port)
    ilnp_sock.set_receive_block(True)

    proxy_map[local_port] = ((remote_ilv, remort_port), ilnp_sock)

    ReceiveThread(ilnp_sock, local_port).start()

    print("Created mapping %s -> %s" % (local_port, (remote_ilv, remort_port)))
