#Set up a simple packet sniffer for the Duepi connections

#The address of the machine this code runs on
#This will be the address/port used by the DPREmote app to connect to the stove
SERVER_IP = '192.168.101.9'
SERVER_PORT = 24
#The address of the pelletstove
STOVE_IP = '192.168.103.11'
STOVE_PORT = 23


import socket
server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
server_address = (SERVER_IP, SERVERPORT)
server_socket.bind(server_address)
server_socket.listen(1)
print('Waiting for a connection...')
client_socket, client_address = server_socket.accept()
print('Connected by', client_address)
server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

server_address = (STOVE_IP, STOVE_PORT)
server_socket.connect(server_address)
prtstr = ""
while True:
    data = client_socket.recv(16)
    if not data:
        break

    prtstr = "tx: " + str(data)
    server_socket.sendall(data)

    data = server_socket.recv(16)
    if not data:
        break
    prtstr = prtstr + ",rx: "+ str(data)
    print(prtstr)
    client_socket.sendall(data)

client_socket.close()
server_socket.close()
