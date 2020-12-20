import socket
import sys
import const

sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM);
sock.connect(("192.168.103.11", 23))
setPoint=sys.argv[1]
setPointInt=int(setPoint)
constInt=75
codeInt=setPointInt+constInt
codeHexStr=hex(codeInt)
setPointHexStr=hex(setPointInt)
data2=const.set_temperature.replace("yy",codeHexStr[2:4])
data3=data2.replace("xx",setPointHexStr[2:4])
sock.send(data3.encode())
dataFromServer = sock.recv(10).decode();
if const.str_ack in dataFromServer:
  print("OK")
else:
 print(dataFromServer)
sock.close()