import socket
import sys
import const

sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM);
sock.connect(("192.168.103.11", 23))

# check if igniting or ignited
sock.send(const.get_status.encode())
dataFromServer = sock.recv(10).decode();

#turn off if igniting or ignited
if const.str_ignition in dataFromServer:
  sock.send(const.set_powerOff.encode())
  dataFromServer = sock.recv(10).decode();
elif const.str_ignited in dataFromServer:
  sock.send(const.set_powerOff.encode())
  dataFromServer = sock.recv(10).decode();
else:
  print("Not on")
if const.str_ack in dataFromServer:
  print("OK")
else:
 print(dataFromServer)
sock.close()
