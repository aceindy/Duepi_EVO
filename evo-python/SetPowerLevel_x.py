import socket
import sys
import const

sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM);
sock.connect(("192.168.103.11", 23))
powerlevel=sys.argv[1]
powerlevelInt=int(powerlevel)
constInt=88
codeInt=constInt+powerlevelInt
codeHexStr=hex(codeInt)
data1=const.set_powerLevel.replace("yy",codeHexStr[2:4])
powerlevelHexStr=hex(powerlevelInt)
cmdPowerStr=data1.replace("x",powerlevelHexStr[2:3])

sock.send(const.get_status.encode())
answStat = sock.recv(10).decode();
if const.str_ignited in answStat:
  sock.send(cmdPowerStr.encode())
  dataFromServer = sock.recv(10).decode();
  if const.str_ack in dataFromServer:
   print("OK")
  else:
   print(dataFromServer)
else:
  print("No flame")
sock.close()
