import socket
import time
import sys
import const

sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM);
sock.connect(("192.168.103.11", 23))
sock.send(const.get_temperature.encode())
dataFromServer = sock.recv(10).decode();
if len(dataFromServer) != 0:
  tempStrHex=dataFromServer[1:5]
  tempIntDec=int(tempStrHex,16)
  tempFloatDec=tempIntDec/10.0
  print(tempFloatDec)
else:
  print(dataFromServer)
sock.close()