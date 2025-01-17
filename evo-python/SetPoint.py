import socket
import sys
import const

sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM);
sock.connect(("192.168.100.29", 23))
setPoint = 20
setPointInt = int(setPoint)

if setPointInt < 16:
    OFFSET = 97
elif setPointInt <= 25:
    OFFSET = 75
elif setPointInt <= 31:
    OFFSET = 82
else:
    OFFSET = 60

set_point_hex = f"{setPointInt:02X}"
offset_hex    = f"{(setPointInt + OFFSET):02X}"

data = const.set_temperature \
    .replace("xx", set_point_hex) \
    .replace("yy", offset_hex)
sock.send(data.encode())

dataFromServer = sock.recv(10).decode()
if const.str_ack in dataFromServer:
    print("OK")
else:
    print(dataFromServer)

sock.close()
