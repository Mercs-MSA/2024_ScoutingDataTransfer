"""
6369 Scouting Data Transfer
Transfer data form scouting tablets using qr code scanner
"""

import sys
import os
import json
import csv

from PyQt6.QtWidgets import (
    QApplication,
    QMainWindow,
    QHBoxLayout,
    QVBoxLayout,
    QWidget,
    QSplitter,
    QLineEdit,
    QPushButton,
    QToolButton,
    QLabel,
    QFileDialog,
    QGridLayout,
    QComboBox,
    QMessageBox,
    QStackedWidget,
)
from PyQt6.QtCore import QSettings, QSize, QIODevice, Qt, pyqtSignal, QObject, QThread
from PyQt6.QtGui import QCloseEvent
from PyQt6.QtSerialPort import QSerialPort, QSerialPortInfo
import qdarktheme
import qtawesome

import disk_widget
import disk_detector
import utils

BAUDS = [
    300,
    600,
    900,
    1200,
    2400,
    3200,
    4800,
    9600,
    19200,
    38400,
    57600,
    115200,
    230400,
    460800,
    921600,
]

DATA_BITS = {
    "5 Data Bits": QSerialPort.DataBits.Data5,
    "6 Data Bits": QSerialPort.DataBits.Data6,
    "7 Data Bits": QSerialPort.DataBits.Data7,
    "8 Data Bits": QSerialPort.DataBits.Data8
}

STOP_BITS = {
    "1 Stop Bits": QSerialPort.StopBits.OneStop,
    "1.5 Stop Bits": QSerialPort.StopBits.OneAndHalfStop,
    "2 Stop Bits": QSerialPort.StopBits.TwoStop,
}

PARITY = {
    "No Parity": QSerialPort.Parity.NoParity,
    "Even Parity": QSerialPort.Parity.EvenParity,
    "Odd Parity": QSerialPort.Parity.OddParity,
    "Mark Parity": QSerialPort.Parity.MarkParity,
    "Space Parity": QSerialPort.Parity.SpaceParity,
}

FLOW_CONTROL = {
    "No Flow Control": QSerialPort.FlowControl.NoFlowControl,
    "Software FC": QSerialPort.FlowControl.SoftwareControl,
    "Hardware FC": QSerialPort.FlowControl.HardwareControl
}

def scouting_disk_predicate(disk: disk_detector.Disk) -> tuple[bool, str, str]:
    """Disk detection predicate

    Args:
        disk (disk_detector.Disk): Disk to attempt search

    Returns:
        tuple[bool, str, str]: Output from predicate (Visible, Name, Icon)
    """
    if os.path.isfile(os.path.join(disk.mountpoint, "scout_disk_opts.json")):
        with open(
            os.path.join(disk.mountpoint, "scout_disk_opts.json"), "r", encoding="utf-8"
        ) as file:
            opts = json.load(file)
    else:
        opts = {}

    if "display" in opts:
        if "id" in opts:
            return (
                True,
                f"ID: {opts['id']} {disk.mountpoint} fs:{disk.fstype} "
                f"cap:{utils.format_bytes(disk.capacity)}",
                str(opts["id"]),
            )
        if opts["display"]:
            return (
                True,
                f"ID: ?? {disk.mountpoint} fs:{disk.fstype} "
                 "cap:{utils.format_bytes(disk.capacity)}",
                "0",
            )

    return False, "", "??"


settings: QSettings | None = None


class DataWorker(QObject):
    finished = pyqtSignal()
    def __init__(self, data: str, savedir: str, savedisk: str | None) -> None:
        super().__init__()

        self.data = data
        self.savedir = savedir
        self.savedisk = savedisk

    def run(self):
        """ Here is where all data processing must occur """
        print(self.data)
        self.finished.emit()

class MainWindow(QMainWindow):
    """Main Window"""

    HOME_IDX, SETTINGS_IDX, ABOUT_IDX = range(3)

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("6369 Scouting Data Transfer")

        self.serial = QSerialPort()
        self.serial.errorOccurred.connect(self.on_serial_error)
        self.serial.aboutToClose.connect(self.serial_close)
        self.serial.readyRead.connect(self.on_serial_recieve)

        self.data_worker = None
        self.worker_thread = None

        self.is_scanning = False

        self.data_buffer = "" # data may come in split up

        self.root_widget = QWidget()
        self.setCentralWidget(self.root_widget)

        self.root_layout = QVBoxLayout()
        self.root_widget.setLayout(self.root_layout)

        # App navigation
        
        self.nav_layout = QHBoxLayout()
        self.root_layout.addLayout(self.nav_layout)

        self.navigation_buttons: list[QToolButton] = []

        self.nav_button_home = QToolButton()
        self.nav_button_home.setCheckable(True)
        self.nav_button_home.setText("Home")
        self.nav_button_home.setChecked(True)
        self.nav_button_home.clicked.connect(lambda: self.nav(self.HOME_IDX))
        self.nav_layout.addWidget(self.nav_button_home)
        self.navigation_buttons.append(self.nav_button_home)

        self.nav_button_settings = QToolButton()
        self.nav_button_settings.setCheckable(True)
        self.nav_button_settings.setText("Settings")
        self.nav_button_settings.clicked.connect(lambda: self.nav(self.SETTINGS_IDX))
        self.nav_layout.addWidget(self.nav_button_settings)
        self.navigation_buttons.append(self.nav_button_settings)

        self.app_widget = QStackedWidget()
        self.root_layout.addWidget(self.app_widget)

        # * HOME * #

        self.home_widget = QWidget()
        self.app_widget.insertWidget(self.HOME_IDX, self.home_widget)

        self.home_layout = QHBoxLayout()
        self.home_widget.setLayout(self.home_layout)

        self.splitter = QSplitter()
        self.home_layout.addWidget(self.splitter)

        # Data manager (left side)
        self.drive_widget = QWidget()
        self.splitter.addWidget(self.drive_widget)

        self.drive_layout = QVBoxLayout()
        self.drive_widget.setLayout(self.drive_layout)

        self.drive_layout.addStretch()

        self.transfer_dir_label = QLabel("Transfer Directory")
        self.drive_layout.addWidget(self.transfer_dir_label)

        self.transfer_dir_layout = QHBoxLayout()
        self.drive_layout.addLayout(self.transfer_dir_layout)

        self.transfer_dir_textbox = QLineEdit()

        if settings.contains("transferDir"):
            self.transfer_dir_textbox.setText(settings.value("transferDir"))

        self.transfer_dir_textbox.textChanged.connect(self.update_transfer_dir)
        self.transfer_dir_layout.addWidget(self.transfer_dir_textbox)

        self.transfer_dir_picker = QPushButton("Pick Dir")
        self.transfer_dir_picker.clicked.connect(self.select_transfer_dir)
        self.transfer_dir_layout.addWidget(self.transfer_dir_picker)

        self.transfer_dir_icon = QLabel()
        self.transfer_dir_layout.addWidget(self.transfer_dir_icon)

        valid = os.path.isdir(self.transfer_dir_textbox.text())
        if valid:
            self.transfer_dir_icon.setPixmap(
                qtawesome.icon("mdi6.check-circle", color="#4caf50").pixmap(
                    QSize(24, 24)
                )
            )
        else:
            self.transfer_dir_icon.setPixmap(
                qtawesome.icon("mdi6.alert", color="#f44336").pixmap(QSize(24, 24))
            )

        self.drive_layout.addStretch()

        self.disk_widget = disk_widget.DiskMgmtWidget(
            predicate=scouting_disk_predicate
        )
        self.disk_widget.set_select_visible(False)
        self.drive_layout.addWidget(self.disk_widget)

        self.drive_layout.addStretch()

        # Scan manager (right side)
        self.scanner_widget = QWidget()
        self.splitter.addWidget(self.scanner_widget)

        self.scanner_layout = QVBoxLayout()
        self.scanner_widget.setLayout(self.scanner_layout)

        self.serial_grid = QGridLayout()
        self.scanner_layout.addLayout(self.serial_grid)

        self.serial_port = QComboBox()
        self.serial_grid.addWidget(self.serial_port, 0, 0, 1, 5)

        self.serial_refresh = QPushButton("Refresh")
        self.serial_refresh.clicked.connect(self.update_serial_ports)
        self.serial_grid.addWidget(self.serial_refresh, 1, 5)

        self.serial_connect = QPushButton("Connect")
        self.serial_connect.clicked.connect(self.connect_to_port)
        self.serial_grid.addWidget(self.serial_connect, 0, 5)

        self.serial_baud = QComboBox()
        self.serial_baud.setMinimumWidth(90)
        self.serial_baud.addItems([str(baud) for baud in BAUDS])

        if settings.contains("baud"):
            self.serial_baud.setCurrentText(str(settings.value("baud")))

        self.serial_baud.currentTextChanged.connect(self.change_baud)
        self.serial_grid.addWidget(self.serial_baud, 1, 0)

        self.serial_bits = QComboBox()
        self.serial_bits.setMinimumWidth(110)
        self.serial_bits.addItems([str(key) for key in DATA_BITS])

        if settings.contains("databits"):
            self.serial_bits.setCurrentText(settings.value("databits"))

        self.serial_bits.currentTextChanged.connect(self.change_data_bits)
        self.serial_grid.addWidget(self.serial_bits, 1, 1)

        self.serial_stop = QComboBox()
        self.serial_stop.setMinimumWidth(110)
        self.serial_stop.addItems([str(key) for key in STOP_BITS])

        if settings.contains("stopbits"):
            self.serial_stop.setCurrentText(settings.value("stopbits"))

        self.serial_stop.currentTextChanged.connect(self.change_stop_bits)
        self.serial_grid.addWidget(self.serial_stop, 1, 2)

        self.serial_flow = QComboBox()
        self.serial_flow.setMinimumWidth(140)
        self.serial_flow.addItems([str(key) for key in FLOW_CONTROL])

        if settings.contains("flow"):
            self.serial_flow.setCurrentText(settings.value("flow"))

        self.serial_flow.currentTextChanged.connect(self.change_flow)
        self.serial_grid.addWidget(self.serial_flow, 1, 3)

        self.serial_parity = QComboBox()
        self.serial_parity.setMinimumWidth(140)
        self.serial_parity.addItems([str(key) for key in PARITY])

        if settings.contains("parity"):
            self.serial_parity.setCurrentText(settings.value("parity"))

        self.serial_parity.currentTextChanged.connect(self.change_parity)
        self.serial_grid.addWidget(self.serial_parity, 1, 4)

        self.serial_disconnect = QPushButton("Disconnect")
        self.serial_disconnect.clicked.connect(self.disconnect_port)
        self.serial_disconnect.setEnabled(False)
        self.serial_grid.addWidget(self.serial_disconnect, 2, 0, 1, 6)

        self.scanner_layout.addStretch()

        self.connection_icon = QLabel()
        self.connection_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.connection_icon.setPixmap(
            qtawesome.icon("mdi6.serial-port").pixmap(256, 256)
        )
        self.scanner_layout.addWidget(self.connection_icon)

        self.scanner_layout.addStretch()

        # * SETTINGS * #
        self.settings_widget = QWidget()
        self.app_widget.insertWidget(self.SETTINGS_IDX, self.settings_widget)

        self.show()

    def nav(self, page: int):

        for button in self.navigation_buttons:
            button.setChecked(False)

        self.app_widget.setCurrentIndex(page)
        self.navigation_buttons[page].setChecked(True)

    def select_transfer_dir(self) -> None:
        """
        Pick file for transfer directory
        """

        self.transfer_dir_textbox.setText(
            str(QFileDialog.getExistingDirectory(self, "Select Directory"))
        )

    def update_transfer_dir(self) -> None:
        """
        Check if transfer dir is valid and set to persistent storage
        """

        valid = os.path.isdir(self.transfer_dir_textbox.text())
        if valid:
            self.transfer_dir_icon.setPixmap(
                qtawesome.icon("mdi6.check-circle", color="#4caf50").pixmap(
                    QSize(24, 24)
                )
            )
        else:
            self.transfer_dir_icon.setPixmap(
                qtawesome.icon("mdi6.alert", color="#f44336").pixmap(QSize(24, 24))
            )
        settings.setValue("transferDir", self.transfer_dir_textbox.text())

    def update_serial_ports(self):
        """
        Refresh list of available serial ports
        """

        self.serial_port.clear()
        for port in QSerialPortInfo.availablePorts():
            if not port.portName().startswith("ttyS"):
                self.serial_port.addItem(f"{port.portName()} - {port.description()}")

    def change_baud(self):
        """
        Set baud rate from combo box
        """

        baud = int(self.serial_baud.currentText())
        self.serial.setBaudRate(baud)
        settings.setValue("baud", baud)

    def change_data_bits(self):
        """
        Set data bits from combo box
        """

        bits = DATA_BITS[self.serial_bits.currentText()]
        self.serial.setDataBits(bits)
        settings.setValue("databits", self.serial_bits.currentText())

    def change_stop_bits(self):
        """
        Set stop bits from combo box
        """

        stop_bits = STOP_BITS[self.serial_stop.currentText()]
        self.serial.setStopBits(stop_bits)
        settings.setValue("stopbits", self.serial_stop.currentText())

    def change_flow(self):
        """
        Set flow control from combo box
        """

        flow = FLOW_CONTROL[self.serial_flow.currentText()]
        self.serial.setFlowControl(flow)
        settings.setValue("flow", self.serial_flow.currentText())

    def change_parity(self):
        """
        Set parity type from combo box
        """

        parity = PARITY[self.serial_parity.currentText()]
        self.serial.setParity(parity)
        settings.setValue("parity", self.serial_parity.currentText())

    def connect_to_port(self):
        """
        Attempt to connect to serial port
        """

        ports = [port for port in QSerialPortInfo.availablePorts()
                 if not port.portName().startswith("ttyS")]

        if len(ports) < 1:
            self.show_port_ref_error()
            return

        port = ports[self.serial_port.currentIndex()]

        if f"{port.portName()} - {port.description()}" != self.serial_port.currentText():
            self.show_port_ref_error()
            return

        self.serial.setPort(port)

        baud = int(self.serial_baud.currentText())
        self.serial.setBaudRate(baud)

        bits = DATA_BITS[self.serial_bits.currentText()]
        self.serial.setDataBits(bits)

        stop_bits = STOP_BITS[self.serial_stop.currentText()]
        self.serial.setStopBits(stop_bits)

        flow = FLOW_CONTROL[self.serial_flow.currentText()]
        self.serial.setFlowControl(flow)

        parity = PARITY[self.serial_parity.currentText()]
        self.serial.setParity(parity)

        ok = self.serial.open(QIODevice.ReadWrite)
        if ok:
            self.set_serial_options_enabled(False)
            self.connection_icon.setPixmap(
                qtawesome.icon("mdi6.qrcode-scan", color="#03a9f4").pixmap(256, 256)
            )
        else:
            msg = QMessageBox()
            msg.setIcon(QMessageBox.Icon.Critical)
            msg.setText("Serial connect operation failed\n"
                        "Common issues:\n"
                        "1. Your user account does not have appropriate rights\n"
                        "2. Another application is using the serial port")
            msg.setWindowTitle("Can't connect")
            msg.setStandardButtons(QMessageBox.StandardButton.Ok)
            msg.exec()

    def disconnect_port(self):
        """
        Disconnect from serial port
        """

        self.serial.close()
        self.set_serial_options_enabled(True)
        self.connection_icon.setPixmap(
            qtawesome.icon("mdi6.serial-port").pixmap(256, 256)
        )

    def on_serial_error(self):
        """
        Serial error callback
        """

        if self.serial.error() == QSerialPort.SerialPortError.NoError:
            msg = QMessageBox()
            msg.setIcon(QMessageBox.Icon.Information)
            msg.setText("Connection Successful!")
            msg.setWindowTitle("Serial")
            msg.setStandardButtons(QMessageBox.StandardButton.Ok)
            msg.exec()
            return

        if self.serial.isOpen():
            self.serial.close()
            msg = QMessageBox()
            msg.setIcon(QMessageBox.Icon.Critical)
            msg.setText(f"{self.serial.error().name}\nError occured during serial operation")
            msg.setWindowTitle("Serial error")
            msg.setStandardButtons(QMessageBox.StandardButton.Ok)
            msg.exec()

            self.connection_icon.setPixmap(
                qtawesome.icon("mdi6.alert-decagram", color="#f44336").pixmap(256, 256)
            )

    def serial_close(self):
        """
        Serial shutdown callback
        """

        msg = QMessageBox()
        msg.setIcon(QMessageBox.Icon.Information)
        msg.setText("Serial controller shut down")
        msg.setWindowTitle("Serial")
        msg.setStandardButtons(QMessageBox.StandardButton.Ok)
        msg.exec()

        self.set_serial_options_enabled(True)

    def on_serial_recieve(self):
        self.connection_icon.setPixmap(
                qtawesome.icon("mdi6.timer-sand", color="#03a9f4").pixmap(256, 256)
            )
        data = self.serial.readLine()
        self.data_buffer += data.data().decode()
        if self.data_buffer.endswith("\r\n"):
            self.on_data_retrieved(self.data_buffer)
            self.data_buffer = ""
            

    def on_data_retrieved(self, data: str):
        if not self.is_scanning:
            self.is_scanning = True

            if self.disk_widget.get_selected_disk() is None:
                disk = None
            else:
                disk = self.disk_widget.get_selected_disk().mountpoint

            self.worker_thread = QThread()

            self.data_worker = DataWorker(
                data,
                self.transfer_dir_textbox.text(),
                disk
            )
            self.data_worker.finished.connect(self.on_data_transfer_complete)
            self.data_worker.moveToThread(self.worker_thread)
            self.worker_thread.started.connect(self.data_worker.run)

            self.worker_thread.finished.connect(self.worker_thread.deleteLater)
            self.data_worker.finished.connect(self.worker_thread.quit)
            self.data_worker.finished.connect(self.data_worker.deleteLater)
            
            self.worker_thread.start()

    def on_data_transfer_complete(self):
        self.connection_icon.setPixmap(
            qtawesome.icon("mdi6.qrcode-scan", color="#03a9f4").pixmap(256, 256)
        )

        self.is_scanning = False

    def show_port_ref_error(self):
        """
        Display a serial port list refresh error
        """

        msg = QMessageBox()
        msg.setIcon(QMessageBox.Icon.Warning)
        msg.setText("Port refresh required")
        msg.setWindowTitle("Can't connect")
        msg.setStandardButtons(QMessageBox.StandardButton.Ok)
        msg.exec()

    def set_serial_options_enabled(self, ena: bool):
        """
        Set whether to disable serial options
        """

        self.serial_port.setEnabled(ena)
        self.serial_connect.setEnabled(ena)
        self.serial_refresh.setEnabled(ena)
        self.serial_port.setEnabled(ena)
        self.serial_baud.setEnabled(ena)
        self.serial_bits.setEnabled(ena)
        self.serial_stop.setEnabled(ena)
        self.serial_flow.setEnabled(ena)
        self.serial_parity.setEnabled(ena)
        self.serial_disconnect.setEnabled(not ena)

    def closeEvent(self, a0: QCloseEvent | None) -> None: # pylint: disable=invalid-name
        """
        Application close event

        Args:
            a0 (QCloseEvent | None): Qt close event
        """
        self.serial.disconnect()
        return super().closeEvent(a0)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    settings = QSettings("Mercs", "ScoutingDataTransfer")
    qdarktheme.setup_theme(additional_qss="#big_dropdown {min-height: 56px}")
    qtawesome.dark(app)
    win = MainWindow()
    sys.exit(app.exec())
