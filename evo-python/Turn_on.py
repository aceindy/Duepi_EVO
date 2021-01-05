import socket
import sys
import const

sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM);
sock.connect(("192.168.103.11", 23))

#check if off
sock.send(const.get_status.encode())
dataFromServer = sock.recv(10).decode();

#turn on if off
if const.str_off in dataFromServer:
  sock.send(const.set_powerOn.encode())
  dataFromServer = sock.recv(10).decode();
  if const.str_ack in dataFromServer:
   print("OK")
  else:
   print(dataFromServer)
else:
 print("Already on")
sock.close()