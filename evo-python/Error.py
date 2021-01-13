import socket
sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM);
sock.connect(("adresseIP", port#))
cmdGetStatus = "\x1bRDA00067&"
sock.send(cmdGetStatus.encode())
dataFromServer = sock.recv(10);
statusInt=int(dataFromServer[4:6],16)

if statusInt == 0 :
  print("OK")
elif statusInt == 1 :
  print("Allumage rate")
elif statusInt == 2 :
  print("Capteur aspiration defectueux")
elif statusInt == 3 :
  print("Aspiration air insuffisant")
elif statusInt == 4 :
  print("Temperature de l'eau")
elif statusInt == 5 :
  print("Pellet termine")
elif statusInt == 6 :
  print("Pressostat")
elif statusInt == 8 :
  print("absence de courant")
elif statusInt == 9 :
  print("Moteur fumee")
elif statusInt == 10 :
  print("Surtension carte")
elif statusInt == 11 :
  print("Date depassee")
elif statusInt == 13 :
  print("Regulation capteur aspiration")
elif statusInt == 14 :
  print("Surchauffe")
else:
  print(statusInt)
sock.close()