import socket
import sys
import const

sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM);
sock.settimeout(3)
sock.connect(("192.168.103.11", 23))
tosend="\x1bR" + str(sys.argv[1]) + "&"
sock.send(tosend.encode())
print(sock.recv(10).decode())
sock.close()
