import socket
import sys
import const

sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM);
sock.connect(("192.168.103.11", 23))
sock.send(const.get_status.encode())
dataFromServer = sock.recv(10).decode();
if const.str_cool1 in dataFromServer:
  print("Cooling down")
elif const.str_cool2 in dataFromServer:
  print("Cooling down ")
elif const.str_off in dataFromServer:
  print("Off")
elif const.str_igniting in dataFromServer:
  print("Igniting starting")
elif const.str_ignited in dataFromServer:
  print("Flame On")
else:
  print(dataFromServer)
sock.close()
