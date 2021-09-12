import socket
import os
import time
import sys

sock_filename = "sock_client"
sock_addr = os.path.join(os.path.dirname(__file__), sock_filename)

server_sock_filename = "sock"
server_sock_addr = os.path.join(os.path.dirname(__file__), server_sock_filename)

sock = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)

try:
    os.remove(sock_addr)
except OSError:
    pass

sock.bind(sock_addr)

sock.sendto(("%s %s %s" % tuple(sys.argv[1:])).encode("utf-8"), server_sock_addr)
msg_bytes, addr = sock.recvfrom(1024)
msg = msg_bytes.decode("utf-8")
print(msg)
