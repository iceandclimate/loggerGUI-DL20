# first order
#!/usr/bin/env python

import os
import os.path
import sys
import datetime
import math

import pylab

from collections import OrderedDict, deque

from PyQt5 import QtWidgets, QtGui, QtCore
from io import StringIO
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.backends.backend_qt5agg import NavigationToolbar2QT as NavigationToolbar

import workers
import corrections
import utilities

MAX_HISTORY = 60 # how many points are saved, 60 = 3 minutes
Y_OFFSET = 0.1 # offset from sides in plot
Y_SCALE = 0.1 # maximum graph scale

FILE_SUFFIX_RAW = ".raw"
FILE_SUFFIX_LOG = ".log"
FILE_SUFFIX_DATA = ".csv"
FILE_SUFFIX_NOTES = ".txt"



def input(q = 'question'): #the input function in new versions of python apparently does not use stdin.readline. So we override.
    sys.stdin.q = q
    return sys.stdin.readline()


# pop up an input-field when reading from stdin
class ReadlineGUI():
    def __init__(self, parentWidget):
        self.parentWidget = parentWidget
        self.q = "Read"

    def question(self, q):
        self.q = q

    def readline(self):
        text, ok = QtWidgets.QInputDialog.getText(self.parentWidget, '', self.q)
        retval = str(text) if ok else ''
        self.parentWidget.log(retval + "\n")
        return retval

class OptionsDialog(QtWidgets.QDialog):
    def __init__(self, parent):
        super(OptionsDialog, self).__init__(parent)
        self.parentWidget = parent
        self.refs = {}
        layout = QtWidgets.QVBoxLayout(self)

        MAX = 10

        dpGB = QtWidgets.QGroupBox("Display Parameters")
        dpLayout = QtWidgets.QGridLayout(dpGB)

        for idx, readout in enumerate(self.parentWidget.readouts):
            w = self.parentWidget.readouts[readout]
            checkbox = QtWidgets.QCheckBox(w.label, checked=w.enabled)
            self.refs[readout] = checkbox
            dpLayout.addWidget(checkbox, idx % MAX, idx / MAX)

        buttons = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel,
            QtCore.Qt.Horizontal, self)

        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        dpGB.setLayout(dpLayout)

        layout.addWidget(dpGB)
        layout.addWidget(buttons)

    def accept(self):
        print("Options: updating GUI")

        for ref in self.refs:
            cb = self.refs[ref].isChecked()
            self.parentWidget.readouts[ref].setEnabled(cb)

        self.parentWidget.updateValueGui()
        super(OptionsDialog, self).accept()


class OffsetsDialog(QtWidgets.QDialog):
    def __init__(self, parent):
        super(OffsetsDialog, self).__init__(parent)
        self.parentWidget = parent
        self.refs = {}
        layout = QtWidgets.QVBoxLayout(self)

        dpGB = QtWidgets.QGroupBox("Offset Parameters")
        dpLayout = QtWidgets.QGridLayout(dpGB)

        for idx, offset in enumerate(self.parentWidget.offsets):
            value = self.parentWidget.offsets[offset]
            label = self.parentWidget.readouts[offset].label
            unit = self.parentWidget.readouts[offset].unit
            if unit:
                label += " (%s)" % unit
            dpLayout.addWidget(QtWidgets.QLabel(label), idx, 0)
            textbox = QtWidgets.QLineEdit(str(value))
            self.refs[offset] = textbox
            dpLayout.addWidget(textbox, idx, 1)

        buttons = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel,
            QtCore.Qt.Horizontal, self)

        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        dpGB.setLayout(dpLayout)

        layout.addWidget(dpGB)
        layout.addWidget(buttons)

    def accept(self):
        for ref in self.refs:

            if ref.endswith("_raw"):
                value = int(str(self.refs[ref].text()))
            else:
                value = float(str(self.refs[ref].text()))

            if abs(value) > 1e-10:
                print("Offset: setting %s to %f" % (ref, value))
                self.parentWidget.addNote("*** auto ***: setting offset '%s' to %f" % (ref, value))
                self.parentWidget.offsets[ref] = value

        super(OffsetsDialog, self).accept()


class ValueDisplay(QtWidgets.QFrame):
    def __init__(self, parentWidget, label, unit, format="%d", enabled=False):
        super(ValueDisplay, self).__init__()

        self.parentWidget = parentWidget
        self.label = label
        self.unit = unit
        self.format = format + " %s"
        self.value = "-"
        self.history = deque(maxlen=MAX_HISTORY) # automatically pops elements when MAX_HISTORY is reached

        self.labelWidget = QtWidgets.QLabel(self.label)
        self.labelWidget.setFont(QtGui.QFont("mono", 9));

        self.valueWidget = QtWidgets.QLabel(self.value)
        self.valueWidget.setFont(QtGui.QFont("mono", 18));

        self.setMinimumWidth(300)
        self.setMaximumWidth(300)

        self.setFrameShape(QtWidgets.QFrame.Panel)
        self.setLineWidth(0)
        layout = QtWidgets.QVBoxLayout()
        layout.addWidget(self.labelWidget)
        layout.addWidget(self.valueWidget)
        self.setLayout(layout)
        self.setEnabled(enabled)


    def mouseDoubleClickEvent(self, event):
        self.setActive()

    def setEnabled(self, enabled):
        self.enabled = enabled
        self.setVisible(self.enabled)

    def set(self, value):
        self.value = value
        self.history.append(value)
        self.valueWidget.setText(self.format % (self.value, self.unit))
        self.plot()

    def setActive(self):
        print("Plot: Tracking parameter", self.label)
        if self.parentWidget.activePlot is not None:
            self.parentWidget.activePlot.setLineWidth(0)

        self.setLineWidth(1)
        self.parentWidget.activePlot = self
        self.plot()

    def plot(self):
        if self.parentWidget.activePlot is self:
            data = list(self.history)
            self.parentWidget.plot.set_data(list(range(len(data))), data)
            ymin = math.floor(min(data) / Y_SCALE) * Y_SCALE
            ymax = math.ceil(max(data) / Y_SCALE)  * Y_SCALE
            pylab.xlim(0, MAX_HISTORY)
            pylab.ylim(ymin - Y_OFFSET, ymax + Y_OFFSET)
            self.parentWidget.canvas.draw()



class MainWindow(QtWidgets.QMainWindow):
    def __init__(self):

        super(MainWindow, self).__init__()

        # "globals"
        self.recording = False
        self.savefilename = None
        self.inputworker = None
        self.last_record = "####"

        # widgets
        self.figure = pylab.figure()
        self.canvas = FigureCanvas(self.figure)
        #self.toolbar = NavigationToolbar(self.canvas, self)

        y_formatter = pylab.mpl.ticker.ScalarFormatter(useOffset=False)
        self.activePlot = None
        self.plot = pylab.plot([], [], 'r.-', markersize=18, clip_on=False)[0]
        self.plot.set_markerfacecolor((.8, 0, 0, 1))
        self.plot.set_color((.8, 0, 0, .1))
        self.figure.axes[0].yaxis.set_major_formatter(y_formatter)

        pylab.grid(True)
        self.figure.tight_layout()

        # value name, ValueDisplay(self, parameter name, parameter unit, parameter format, default enabled)
        self.readouts = OrderedDict([
            ("record_number",                   ValueDisplay(self, "Record number",                 "",     "%d",   True)),

            # ----
            ("transducer_top",                  ValueDisplay(self, "Transducer top",                "raw",    "%.0f", True)),
            ("transducer_bottom",               ValueDisplay(self, "Transducer bottom",             "raw",    "%.0f", True)),
            ("temperature_voltage",             ValueDisplay(self, "Temperature (internal)",       "raw",    "%.0f", True)),
            ("button",                          ValueDisplay(self, "Button",                        "state",  "%.0f", True)),
            # ----
            ("heading",                         ValueDisplay(self, "Heading",                     "deg",  "%.1f", True)),
            ("pitch",                           ValueDisplay(self, "Pitch",                       "deg",  "%.2f", True)),
            ("roll",                            ValueDisplay(self, "Roll",                        "deg",  "%.2f", True)),
            # ----
            ("depth_top",                       ValueDisplay(self, "AtmDepth (top)",                 "m",   "%.2f")),
            ("pressure_top",                    ValueDisplay(self, "Pressure (top)",              "B",   "%.2f", True)),
            ("temperature_top",                 ValueDisplay(self, "Temperature (top)",           "C","%.2f", True)),
            # ----
            ("depth_bottom",                       ValueDisplay(self, "AtmDepth (bottom)",              "m",   "%.2f")),
            ("pressure_bottom",                    ValueDisplay(self, "Pressure (bottom)",              "B",   "%.2f", True)),
            ("temperature_bottom",                 ValueDisplay(self, "Temperature (bottom)",           "C","%.2f", True)),
            # ---- Calculated values ----
            ("delta_pressure",                          ValueDisplay(self, "ΔP (bottom-top)",           "B","%.3f", True)),
        ])

        self.offsets = OrderedDict([
            ("depth_top", 0.0),
            ("depth_bottom", 0.0),
            ("temperature_top", 0),
            ("temperature_bottom", 0),
            ("pressure_top", 0),
            ("pressure_bottom", 0),

        ])

        # setup console
        self.console = QtWidgets.QTextEdit()
        self.console.setReadOnly(True)
        self.console.setTextColor(QtGui.QColor("white"))
        self.console.setFont(QtGui.QFont("mono", 10));
        self.setConsoleColor("black")
        self.console.setFixedHeight(150)

        # redirect streams to console
        self.streams = sys.stdin, sys.stdout, sys.stderr
        sys.stdin = ReadlineGUI(self)
        sys.stdout = StringIO()
        sys.stdout.write = self.log
        sys.stderr = StringIO()
        sys.stderr.write = self.logErr

        # layouts
        self.valuebox = QtWidgets.QVBoxLayout()
        graphbox = QtWidgets.QVBoxLayout()
        graphbox.addWidget(self.canvas)
        #graphbox.addWidget(self.toolbar)
        topbox = QtWidgets.QHBoxLayout()
        topbox.addLayout(graphbox)
        topbox.addLayout(self.valuebox)
        box = QtWidgets.QVBoxLayout()
        box.addLayout(topbox)
        box.addWidget(self.console)


        # menubar
        self.menubar = self.menuBar()
        self.fileMenu = self.menubar.addMenu('&File')
        self.actionMenu = self.menubar.addMenu('&Action')
        self.trackMenu = self.menubar.addMenu('&Track')

        connectSerialAction = QtWidgets.QAction('Connect: Serial Port...', self)
        connectSerialAction.setShortcut('Ctrl+O')
        connectSerialAction.triggered.connect(self.connectSerial)

        connectFileAction = QtWidgets.QAction('Connect: File (Replay)...', self)
        connectFileAction.setShortcut('Ctrl+I')
        connectFileAction.triggered.connect(self.connectFile)

        disconnectAction = QtWidgets.QAction('Disconnect...', self)
        disconnectAction.triggered.connect(self.disconnect)

        saveFileAction = QtWidgets.QAction('Set Save File...', self)
        saveFileAction.setShortcut('Ctrl+S')
        saveFileAction.triggered.connect(self.setSaveFile)
        saveCloseFileAction = QtWidgets.QAction('Close Save File', self)
        saveCloseFileAction.triggered.connect(self.closeSaveFile)


        exitAction = QtWidgets.QAction('Exit', self)
        exitAction.setShortcut('Ctrl+Q')
        exitAction.triggered.connect(self.close)

        self.fileMenu.addAction(connectSerialAction)
        self.fileMenu.addAction(connectFileAction)
        self.fileMenu.addAction(disconnectAction)
        self.fileMenu.addSeparator()
        self.fileMenu.addAction(saveFileAction)
        self.fileMenu.addAction(saveCloseFileAction)
        self.fileMenu.addSeparator()
        self.fileMenu.addAction(exitAction)

        toggleRecordingAction = QtWidgets.QAction('Record', self, checkable=True)
        toggleRecordingAction.setShortcut('Ctrl+R')
        toggleRecordingAction.triggered.connect(self.toggleRecording)

        addNoteAction = QtWidgets.QAction('Add note...', self)
        addNoteAction.setShortcut('Ctrl+N')
        addNoteAction.triggered.connect(self.addNote)

        optionsAction = QtWidgets.QAction('Options...', self)
        optionsAction.triggered.connect(self.showOptions)


        offsetsAction = QtWidgets.QAction('Offsets...', self)
        offsetsAction.triggered.connect(self.showOffsets)

        self.actionMenu.addAction(toggleRecordingAction)
        self.actionMenu.addSeparator()
        self.actionMenu.addAction(addNoteAction)
        self.actionMenu.addSeparator()
        self.actionMenu.addAction(optionsAction)
        self.actionMenu.addAction(offsetsAction)

        # value widgets
        for idx, readout in enumerate(self.readouts):
            self.valuebox.addWidget(self.readouts[readout])
        self.updateValueGui()

        # wrap the main window in a widget, due to QMainWindow requirement
        wrap = QtWidgets.QWidget()
        wrap.setLayout(box)
        self.setCentralWidget(wrap)
        self.setWindowTitle("DL20 logger")
        self.show()

        print("Logger GUI: Started")


    def updateValueGui(self):

        self.trackMenu.clear()
        idx = 0
        for readout in self.readouts:

            if self.readouts[readout].enabled:
                idx += 1
                action = QtWidgets.QAction(self.readouts[readout].label, self)
                if idx < 10:
                    action.setShortcut('Ctrl+%d' % (idx))
                action.triggered.connect(self.readouts[readout].setActive)
                self.trackMenu.addAction(action)


        self.valuebox.update()


    def connectSerial(self):

        ports = utilities.enumerate_serial()
        print("Serial: Detected the %d serial ports on the system" % len(ports))

        if len(ports):
            print("Found:", ", ".join(ports))

        try:
            port = input("Enter port name: ")
        except EOFError:
            print("Serial: User cancelled")
            return

        print("Serial: Using port:", port)

        worker = workers.SerialInputWorker(port)
        self.setInputWorker(worker)
        worker.start()

        print("Serial: Connected")

    def connectFile(self):
        filename = str(QtWidgets.QFileDialog.getOpenFileName()[0])

        if filename == "":
            print("File input: No file chosen, try again.")
            return

        print("File input: Selected filename:", filename)

        try:
            delay = float(input("File input: Update delay (seconds): "))
        except EOFError:
            print("File input: User cancelled")
            return

        worker = workers.FileInputWorker(filename, delay)
        self.setInputWorker(worker)
        worker.start()

        print("File input: Connected.")

    def setSaveFile(self):

        filename = str(QtWidgets.QFileDialog.getSaveFileName()[0])

        if filename == "":
            print("File save: No file chosen, try again.")
            return

        print("File save: Selected filename:", filename)

        if os.path.isfile(filename + FILE_SUFFIX_RAW):
            print("File save WARNING: raw data file already exists at", filename + FILE_SUFFIX_RAW)

        if os.path.isfile(filename + FILE_SUFFIX_LOG):
            print("File save WARNING: log data file already exists at", filename + FILE_SUFFIX_LOG)

        if os.path.isfile(filename + FILE_SUFFIX_NOTES):
            print("File save WARNING: notes data file already exists at", filename + FILE_SUFFIX_NOTES)

        if os.path.isfile(filename + FILE_SUFFIX_LOG):
            print("File save WARNING: output data file already exists at", filename + FILE_SUFFIX_DATA)

        self.savefilename = filename

    def toggleRecording(self):
        self.recording = not self.recording
        print("Recording:", "On" if self.recording else "Off")

        for action in self.fileMenu.actions():
            action.setEnabled(not self.recording)

        if self.recording:

            hasErrors = False


            if self.inputworker is None:
                print("Recording WARNING: no input source is selected, nothing will be recorded")
                hasErrors = True

            if self.savefilename is None:
                print("Recording WARNING: save file is not chosen, nothing will be saved to disk")
                hasErrors = True

            if hasErrors:
                self.setConsoleColor("darkred")
            else:
                self.setConsoleColor("darkgreen")

        else:
            self.setConsoleColor("black")

    def addNote(self, note=None):
        if self.savefilename is not None:
            last_record = str(self.last_record) # save when note is being entered
            if note is None:
                note = input("Note text (for record %s): ", last_record)
            tofile = "%s: %s\n" % (last_record, note)
            with open(self.savefilename + FILE_SUFFIX_NOTES, "a") as logfile:
                logfile.write(tofile)

        else:
            print("Adding Note WARNING: No save file selected, cannot add any notes")

    def showOptions(self):
        od = OptionsDialog(self)
        od.exec_()

    def showOffsets(self):
        od = OffsetsDialog(self)
        od.exec_()

    def newData(self, line):
        # new data comes in from either source (serial or file)
        # as a line in the custom encoding format

        if line == "":
            #IGNORE EMPTY LINES...
            #print("WARNING: End of data stream")
            #self.disconnect()
            return

        # first: save a backup, if savefile is selected and recording
        if self.recording and self.savefilename is not None:
            with open(self.savefilename + FILE_SUFFIX_RAW, "a") as rawfile:
                rawfile.write(line + "\n")

        # second: convert the line into dict, using the data parser and apply offsets
        record = corrections.parseRecord(line, self.offsets)

        # third: save the coverted data, if savefile is selected and recording
        if self.recording and self.savefilename is not None:
            with open(self.savefilename + FILE_SUFFIX_DATA, "a") as datafile:
                record = OrderedDict(sorted(record.items()))

                # if datafile is empty, add header
                if os.fstat(datafile.fileno()).st_size == 0:
                    print("Save: New datafile, adding header")
                    keys = ",".join(['"%s"' % x for x in list(record.keys())])
                    datafile.write(keys + "\n")

                values = ",".join(["%e" % x for x in list(record.values())])
                datafile.write(values + "\n")

        # fourth: update display
        for readout in self.readouts:
            self.readouts[readout].set(record[readout])

        # fifth: save persistently the record number
        self.last_record = record["record_number"]

    def disconnect(self):
        if self.inputworker is not None:
            print("Input worker: Stopping")
            self.inputworker.stop()

    def closeSaveFile(self):
        print("Save file: Closed")
        self.last_record = ""
        self.savefilename = None

    def setInputWorker(self, worker):
        self.disconnect()
        self.inputworker = worker
        self.inputworker.update_signal.connect( self.newData )
        #self.connect(self.inputworker, QtCore.SIGNAL("update(QString)"), self.newData )
        #self.get_thread.update.connect(self.newData)


    def closeEvent(self, evnt):
        if self.recording:
            print("Recording: Cannot close when recording. Stop recording first!")
            evnt.ignore()
        else:
            super(MainWindow, self).closeEvent(evnt)

    def setConsoleColor(self, color):
        p = QtGui.QPalette()
        p.setColor(QtGui.QPalette.Base, QtGui.QColor(color))
        self.console.setPalette(p)

    # write text to log
    def log(self, text):
        sys.stdin.question(text)
        self.console.setText(self.console.toPlainText() + text)
        cursor = QtGui.QTextCursor(self.console.textCursor());
        cursor.movePosition(QtGui.QTextCursor.End, QtGui.QTextCursor.MoveAnchor);
        self.console.setTextCursor(cursor);
        self.console.ensureCursorVisible()
        # save to logfile
        if self.savefilename is not None:
            with open(self.savefilename + FILE_SUFFIX_LOG, "a") as logfile:
                logfile.write(text)

    # send both to stderr and console
    def logErr(self, text):
        self.streams[2].write(text)
        self.log(text)

def runGui():
    app = QtWidgets.QApplication([])
    # app_icon = QtGui.QIcon()
    # iconprefix = os.path.join(os.path.dirname(__file__),'assets','icon')
    # app_icon.addFile(f'{iconprefix}16.png', QtCore.QSize(16,16))
    # app_icon.addFile(f'{iconprefix}24.png', QtCore.QSize(24,24))
    # app_icon.addFile(f'{iconprefix}32.png', QtCore.QSize(32,32))
    # app_icon.addFile(f'{iconprefix}48.png', QtCore.QSize(48,48))
    # app_icon.addFile(f'{iconprefix}64.png', QtCore.QSize(64,64))
    # app_icon.addFile(f'{iconprefix}256.png', QtCore.QSize(256,256))
    # app.setWindowIcon(app_icon)

    s = MainWindow()
    s.showMaximized()
    #s.show()
    sys.exit(app.exec_())

if __name__ == '__main__':
    # change directory to home dir
    os.chdir(os.path.expanduser("~"))
    runGui()

