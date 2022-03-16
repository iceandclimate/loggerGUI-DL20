import time
import serial

from PyQt5 import QtCore

class FileInputWorker(QtCore.QThread):

    update_signal = QtCore.pyqtSignal('QString', name = 'update')

    def __init__(self, filename, delay=3.0):
        QtCore.QThread.__init__(self)
        self.alive = False
        self.filename = filename
        self.delay = delay

    def __del__(self):
        self.stop()

    def stop(self):
        self.alive = False
        self.datafile.close()
        self.wait()

    def run(self):
        self.alive = True
        self.datafile = open(self.filename, "r", encoding='utf-8', errors ='replace')
        while (self.alive):
            line = self.datafile.readline()
            #self.emit( QtCore.SIGNAL('update(QString)'), line.rstrip())
            self.update_signal.emit(line.rstrip())
            time.sleep(self.delay)

        return

class SerialInputWorker(QtCore.QThread):

    update_signal = QtCore.pyqtSignal('QString', name = 'update')
    serial = None
    alive = False
    port = ''

    def __init__(self, port):
        QtCore.QThread.__init__(self)
        self.alive = False
        self.port = port

        self.serial = serial.Serial(
            self.port,
            baudrate=600,
            bytesize=serial.EIGHTBITS,
            parity=serial.PARITY_NONE,
            stopbits=serial.STOPBITS_ONE,
            timeout=5
        )

    def __del__(self):
        self.stop()

    def stop(self):
        self.alive = False
        self.serial.close()
        self.wait()

    def run(self):
        self.alive = True
        while self.alive:
            try:
                line = self.serial.readline()

                # # cap to 7 bit strings
                # result = ""
                # for char in line:
                #     result += chr(ord(char) & 0x7f)

                #self.emit( QtCore.SIGNAL('update(QString)'), result.rstrip())
                self.update_signal.emit(line.decode(encoding='UTF-8',errors='ignore').rstrip())  

            except serial.SerialTimeoutException:
                pass
        return