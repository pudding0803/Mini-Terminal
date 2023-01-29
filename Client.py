import json
import socket
import sys
import threading

from PyQt5 import QtWidgets, QtCore
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QMessageBox

from UI import Ui_MainWindow


def get_dirs_tree(dirs: dict, layer: int) -> str:
    output = ''
    for k, v in dirs.items():
        output += '\t' * layer
        if type(v) is str:
            output += f'- {k}.{v}\n'
        else:
            output += f'- {k}/\n'
            output += get_dirs_tree(v, layer + 1)
    return output


def show_message_box():
    msg_box = QMessageBox()
    msg_box.setWindowFlag(Qt.FramelessWindowHint)
    msg_box.setIcon(QMessageBox.Question)
    msg_box.setWindowTitle('Command Help')
    msg_box.setText(
        'adduser [user name]\n'
        'su [user name]\n'
        'cd [relative path | absolute path]\n'
        'mkdir [directory name]\n'
        'rmdir [directory name]\n'
        'touch [file name].[file extension]\n'
        'rm [file name]\n'
        'exit'
    )
    msg_box.setStyleSheet(f'''
        QLabel {{
            min-height: 260px;
            padding: 5px;
            font-family: Comic Sans MS;
            font-size: 22px;
        }}
        QPushButton {{
            font-family: Comic Sans MS;
        }}
    ''')
    msg_box.setStandardButtons(QMessageBox.Ok)
    msg_box.exec_()


class ClientController(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.ui = Ui_MainWindow()
        self.ui.setupUi(self)
        self.ui.submit.clicked.connect(self.send)
        self.ui.help.clicked.connect(show_message_box)
        self.show()

        self.user = None

        self.PORT = 6000
        self.FORMAT = 'utf-8'
        with open('server.txt', 'r') as file:
            self.SERVER = file.readline()
        self.ADDR = (self.SERVER, self.PORT)
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.connect(self.ADDR)
        self.send_avail = False
        print('Client connect to server')

        threading.Thread(target=self.start).start()

    def start(self):
        connect = True
        while connect:
            while not self.send_avail:
                pass
            self.send_avail = False
            self.ui.submit.setEnabled(False)
            msg = {'user': self.user, 'cmd': self.ui.cmd.text()}
            self.sock.send(json.dumps(msg).encode(self.FORMAT))
            if self.ui.cmd.text() == 'exit':
                self.sock.close()
                self.close()
                sys.exit(0)
            self.ui.cmd.clear()
            msg = json.loads(self.sock.recv(1024).decode(self.FORMAT))
            if 'error' in msg.keys():
                self.ui.error.setText(msg['error'])
            else:
                self.ui.error.clear()
            if len(msg) > 1:
                self.user = msg['name']
                self.ui.user.setText('Welcome, ' + self.user)
                self.ui.path.setText(msg['path'])
                self.ui.files.setText(get_dirs_tree(msg['files'], 0))
                self.ui.files.setMinimumHeight(self.ui.files.text().count('\n') * 34)
            self.ui.submit.setEnabled(True)

    def send(self):
        self.send_avail = True

    def keyPressEvent(self, event):
        if event.key() == QtCore.Qt.Key_Return:
            self.send()


def main():
    app = QtWidgets.QApplication(sys.argv)
    window = ClientController()
    window.setWindowTitle('Personal Cloud System')
    sys.exit(app.exec_())


if __name__ == '__main__':
    main()
