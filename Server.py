import json
import socket
import threading
from typing import Union

import pymongo


def get_curr_pos(path: str, parent: list) -> int | list:
    tmp = path.split('/')
    if tmp[-1] == '':
        tmp.pop()
    if tmp[0] == '':
        tmp.pop(0)
    else:
        tmp = parent + tmp
    pos = []
    for t in tmp:
        if t == '..' and len(pos) != 0:
            pos.pop()
        elif t == '..' or '':
            return -1
        elif t != '.':
            pos.append(t)
    return pos


def get_curr_dirs(files: dict, pos: list) -> int | dict:
    curr = files
    for p in pos:
        if p not in curr.keys():
            return -1
        curr = curr[p]
    return curr


class ServerController:
    def __init__(self):
        myclient = pymongo.MongoClient("mongodb://localhost:27017/")
        self.data = myclient['server']['data']
        self.data.update_many({}, {'$set': {'online': False}})

        self.SERVER = socket.gethostbyname(socket.gethostname())
        self.PORT = 6000
        self.ADDR = (self.SERVER, self.PORT)
        self.FORMAT = 'utf-8'
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.bind(self.ADDR)
        self.sock.listen()
        self.start()

    def handle_client(self, conn, addr):
        print(f'[NEW CONNECTION] {addr} connected.')
        connect = True
        while connect:
            msg = json.loads(conn.recv(1024).decode(self.FORMAT))
            cmd = msg['cmd'].split()
            if len(cmd) == 1 and cmd[0] == 'exit':
                if msg['user'] is not None:
                    self.data.update_one({'name': msg['user']},
                                         {'$set': {'online': False}})
                break
            elif len(cmd) == 2 and cmd[0] == 'adduser':
                user = cmd[1]
                data = self.data.find_one({'name': user})
                if data is None:
                    self.data.insert_one({'name': user,
                                          'files': {},
                                          'pos': [],
                                          'online': True})
                    data = self.data.find_one({'name': user})
                    msg = json.dumps({'name': data['name'],
                                      'files': data['files'],
                                      'path': '/'})
                else:
                    msg = json.dumps({'error': f'User [{user}] is used.'})
            elif len(cmd) == 2 and cmd[0] == 'su':
                user = cmd[1]
                data = self.data.find_one({'name': user})
                if data is None:
                    msg = json.dumps({'error': f'User [{user}] does not exist.'})
                elif data['online']:
                    msg = json.dumps({'error': f'User [{user}] is using now.'})
                else:
                    self.data.update_one({'name': user},
                                         {'$set': {'pos': [], 'online': True}})
                    data = self.data.find_one({'name': user})
                    msg = json.dumps({'name': user,
                                      'files': data['files'],
                                      'path': '/'})
            elif msg['user'] is None:
                msg = json.dumps({'error': 'Please sign in first.'})
            else:
                if len(cmd) == 2 and cmd[0] == 'cd':
                    path = cmd[1]
                    data = self.data.find_one({'name': msg['user']})
                    pos = get_curr_pos(path, data['pos'])
                    if pos == -1:
                        msg = json.dumps({'name': msg['user'],
                                          'files': data['files'],
                                          'path': '/',
                                          'error': f'The path "{path}" does not exist.'})
                    else:
                        dirs = get_curr_dirs(data['files'], pos)
                        if dirs == -1:
                            msg = json.dumps({'name': msg['user'],
                                              'files': data['files'],
                                              'path': '/',
                                              'error': f'The path "{path}" does not exist.'})
                        else:
                            self.data.update_one({'name': msg['user']}, {'$set': {'pos': pos}})
                            data = self.data.find_one({'name': msg['user']})
                            msg = json.dumps({'name': msg['user'],
                                              'files': get_curr_dirs(data['files'], data['pos']),
                                              'path': '/' + '/'.join(data['pos'])})
                elif len(cmd) == 2 and cmd[0] == 'mkdir':
                    dirs = cmd[1]
                    data = self.data.find_one({'name': msg['user']})
                    curr = get_curr_dirs(data['files'], data['pos'])
                    if dirs in curr.keys():
                        msg = json.dumps({'name': msg['user'],
                                          'files': data['files'],
                                          'path': '/' + '/'.join(data['pos']),
                                          'error': f'The directory [{dirs}] already exists.'})
                    else:
                        curr[dirs] = {}
                        msg = self.update_files_and_get_msg(msg['user'], data['files'], curr)
                elif len(cmd) == 2 and cmd[0] == 'rmdir':
                    dirs = cmd[1]
                    data = self.data.find_one({'name': msg['user']})
                    curr = get_curr_dirs(data['files'], data['pos'])
                    if dirs not in curr.keys() or type(curr[dirs]) is not dict:
                        msg = json.dumps({'name': msg['user'],
                                          'files': data['files'],
                                          'path': '/' + '/'.join(data['pos']),
                                          'error': f'The directory [{dirs}] does not exist.'})
                    else:
                        curr.pop(dirs)
                        msg = self.update_files_and_get_msg(msg['user'], data['files'], curr)
                elif len(cmd) == 2 and cmd[0] == 'touch':
                    full_file = cmd[1].split('.')
                    data = self.data.find_one({'name': msg['user']})
                    curr = get_curr_dirs(data['files'], data['pos'])
                    if len(full_file) != 2:
                        msg = json.dumps({'name': msg['user'],
                                          'files': data['files'],
                                          'path': '/' + '/'.join(data['pos']),
                                          'error': f'The format of [{".".join(full_file)}] is invalid.'})
                    else:
                        file, ext = full_file
                        if file in curr.keys() and curr[file] == ext:
                            msg = json.dumps({'name': msg['user'],
                                              'files': data['files'],
                                              'path': '/' + '/'.join(data['pos']),
                                              'error': f'The file [{file}.{ext}] already exists.'})
                        else:
                            curr[file] = ext
                            msg = self.update_files_and_get_msg(msg['user'], data['files'], curr)
                elif len(cmd) == 2 and cmd[0] == 'rm':
                    file = cmd[1]
                    data = self.data.find_one({'name': msg['user']})
                    curr = get_curr_dirs(data['files'], data['pos'])
                    if file not in curr.keys() or type(curr[file]) is not str:
                        msg = json.dumps({'name': msg['user'],
                                          'files': data['files'],
                                          'path': '/' + '/'.join(data['pos']),
                                          'error': f'The file [{file}] does not exist.'})
                    else:
                        curr.pop(file)
                        msg = self.update_files_and_get_msg(msg['user'], data['files'], curr)
                else:
                    if msg['user'] is not None:
                        data = self.data.find_one({'name': msg['user']})
                        curr = get_curr_dirs(data['files'], data['pos'])
                        msg = json.dumps({'name': msg['user'],
                                          'files': curr,
                                          'path': '/' + '/'.join(data['pos']),
                                          'error': 'Unknown command.'})
                    else:
                        msg = json.dumps({'error': 'Unknown command.'})
            conn.send(msg.encode(self.FORMAT))
        conn.close()
        print(f'[DISCONNECTION] {addr} disconnected.')
        self.sock.close()

    def start(self):
        print(f'[LISTENING] Server is listening on {self.SERVER}')
        with open('server.txt', 'w') as file:
            file.write(self.SERVER)
        while True:
            conn, addr = self.sock.accept()
            threading.Thread(target=self.handle_client, args=(conn, addr)).start()

    def update_files_and_get_msg(self, user: str, files: dict, curr: dict) -> str:
        self.data.update_one({'name': user},
                             {'$set': {'files': files}})
        data = self.data.find_one({'name': user})
        return json.dumps({'name': user,
                           'files': curr,
                           'path': '/' + '/'.join(get_curr_pos('./', data['pos']))})


def main():
    ServerController()


if __name__ == '__main__':
    main()
