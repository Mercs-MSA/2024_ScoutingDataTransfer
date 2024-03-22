"""
6369 Scouting Data Transfer
Transfer data form scouting tablets using qr code scanner
"""

import enum
import sys
import os
import json
import logging

import pandas

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
    QGroupBox,
    QTextBrowser
)
from PyQt6.QtCore import QSettings, QSize, QIODevice, Qt, pyqtSignal, QObject, QThread
from PyQt6.QtGui import QCloseEvent, QPixmap
from PyQt6.QtSerialPort import QSerialPort, QSerialPortInfo
import qdarktheme
import qtawesome

import disk_widget
import disk_detector
import utils

__version__ = "0.1.0-amarillo"

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
    "8 Data Bits": QSerialPort.DataBits.Data8,
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
    "Hardware FC": QSerialPort.FlowControl.HardwareControl,
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

PIT_DATA_HEADER = [
    "form",
    "teamNumber",
    "botLength",
    "botWidth",
    "botHeight",
    "botWeight",
    "drivebase",
    "drivebaseAlt",
    "climber",
    "climberAlt",
    "isKitbot",
    "intakeInBumper",
    "speakerScore",
    "ampScore",
    "trapScore",
    "groundPickup",
    "sourcePickup",
    "turretShoot",
    "extendShoot",
    "hasBlocker",
    "hasAuton",
    "autonSpeakerNotes",
    "autonAmpNotes",
    "autonConsistency",
    "autonVersatility",
    "autonRoutes",
    "autonPrefStart",
    "autonStrat",
    "hasAuton",
    "repairability",
    "maneuverability",
    "teleopStrat",
]

QUAL_DATA_HEADER = [
    "form",
    "teamNumber",
    "matchNumber",
    "startingPosition",
    "hasAuton",
    "autonLeave",
    "autonCrossCenter",
    "autonAStop",
    "autonPreload",
    "autonSpeakerNotesScored",
    "autonSpeakerNotesMissed",
    "autonAmpNotesScored",
    "autonAmpNotesMissed",
    "autonWingNotes",
    "autonCenterNotes",
    "teleopFloorPickup",
    "teleopSourcePickup",
    "teleopAmpScored",
    "teleopAmpMissed",
    "teleopSpeakerScored",
    "teleopSpeakerMissed",
    "teleopDroppedNotes",
    "teleopFedNotes",
    "teleopAmps",
    "endgameDidTheyClimb",
    "endgameDidTheyTrap",
    "endgameDidTheyHarmony",
    "endgameDefenseBot",
    "endgameDriverRating",
    "endgameDefenseRating",
    "endgameHighnote",
    "endgameCoOp",
    "endgameDidTheyGetACard",
    "endgameDidTheyNoShow",
    "endgameComments",
]

PLAYOFF_DATA_HEADER = [
    "form",
    "teamNumber",
    "matchNumber",
    "startingPosition",
    "hasAuton",
    "autonLeave",
    "autonCrossCenter",
    "autonAStop",
    "autonPreload",
    "autonSpeakerNotesScored",
    "autonSpeakerNotesMissed",
    "autonAmpNotesScored",
    "autonAmpNotesMissed",
    "autonWingNotes",
    "autonCenterNotes",
    "teleopFloorPickup",
    "teleopSourcePickup",
    "teleopAmpScored",
    "teleopAmpMissed",
    "teleopSpeakerScored",
    "teleopSpeakerMissed",
    "teleopDroppedNotes",
    "teleopFedNotes",
    "teleopAmps",
    "endgameDidTheyClimb",
    "endgameDidTheyTrap",
    "endgameDidTheyHarmony",
    "endgameDefenseBot",
    "endgameDriverRating",
    "endgameDefenseRating",
    "endgameHighnote",
    "endgameCoOp",
    "endgameDidTheyGetACard",
    "endgameDidTheyNoShow",
    "endgameComments",
]


class DataError(enum.Enum):
    DATA_MALFORMED = 0
    UNKNOWN_FORM = 1


class DataWorker(QObject):
    finished = pyqtSignal(dict)
    on_data_error = pyqtSignal(DataError)

    def __init__(self, data: str, savedir: str, savedisk: str | None) -> None:
        super().__init__()
        self.data = data
        self.savedir = savedir
        self.savedisk = savedisk

    def run(
        self,
        data_frames: pandas.DataFrame,
        directory: str,
        disk: disk_detector.Disk | None,
        event_id: str,
    ):
        if not os.path.exists(directory):
            msg = QMessageBox()
            msg.setIcon(QMessageBox.Icon.Critical)
            msg.setText(f"Directory {directory}\ndoes not exist\nData import cancelled")
            msg.setWindowTitle("Data Error")
            msg.setStandardButtons(QMessageBox.StandardButton.Ok)
            msg.exec()
            self.finished.emit(data_frames)
            return
        data = self.data.strip("\r\n").split("||")
        form = data[0]
        logging.info("Data transfer started on form %s", str(form))

        if form == "pit":
            header = PIT_DATA_HEADER
            if len(data) != len(header):
                self.on_data_error.emit(DataError.DATA_MALFORMED)
                self.finished.emit(data_frames)
                return
        elif form == "qual":
            header = QUAL_DATA_HEADER
            if len(data) != len(header):
                self.on_data_error.emit(DataError.DATA_MALFORMED)
                self.finished.emit(data_frames)
                return
        elif form == "playoff":
            header = PLAYOFF_DATA_HEADER
            if len(data) != len(header):
                self.on_data_error.emit(DataError.DATA_MALFORMED)
                self.finished.emit(data_frames)
                return
        else:
            self.on_data_error.emit(DataError.UNKNOWN_FORM)
            self.finished.emit(data_frames)
            return

        df = pandas.DataFrame([data], columns=header)

        add_to_df = True

        # form type
        if form == "pit":
            # check for repeats
            if int(df["teamNumber"].iloc[0]) in [
                int(x) for x in data_frames["pit"]["teamNumber"].to_list()
            ]:
                if (
                    self.on_repeated_data("pit", df["teamNumber"].iloc[0])
                    == QMessageBox.StandardButton.No
                ):
                    add_to_df = False
        elif form == "qual":
            # check for repeats
            if (
                int(df["teamNumber"].iloc[0])
                in [int(x) for x in data_frames["qual"]["teamNumber"].to_list()]
            ) or (
                int(df["matchNumber"].iloc[0])
                in [int(x) for x in data_frames["qual"]["matchNumber"].to_list()]
            ):
                if (
                    self.on_repeated_data("qual", int(df["teamNumber"].iloc[0]))
                    == QMessageBox.StandardButton.No
                ):
                    add_to_df = False
        elif form == "playoff":
            # check for repeats
            if (
                int(df["teamNumber"].iloc[0])
                in [int(x) for x in data_frames["playoff"]["teamNumber"].to_list()]
            ) or (
                int(df["matchNumber"].iloc[0])
                in [int(x) for x in data_frames["playoff"]["matchNumber"].to_list()]
            ):
                if (
                    self.on_repeated_data("playoff", int(df["teamNumber"].iloc[0]))
                    == QMessageBox.StandardButton.No
                ):
                    add_to_df = False

        if add_to_df:
            data_frames[form] = pandas.concat([data_frames[form], df])

        logging.info("transfering data to %s", directory)

        # create directory structure
        for form in data_frames:
            if not os.path.exists(os.path.join(directory, form)):
                os.mkdir(os.path.join(directory, form))

            data_frames[form].to_csv(
                os.path.join(directory, form, f"{event_id}_{form}_total.csv"),
                index=False,
            )

        # create disk directory structure
        if disk:
            for form in data_frames:
                if not os.path.exists(os.path.join(disk.mountpoint, form)):
                    os.mkdir(os.path.join(disk.mountpoint, form))
                    logging.info("Created directory structure on %s", disk.mountpoint)

                data_frames[form].to_csv(
                    os.path.join(disk.mountpoint, form, f"{event_id}_{form}_total.csv"),
                    index=False,
                )

        self.finished.emit(data_frames)

    def on_repeated_data(self, form: str, team: int):
        """
        Display a warning for importing a repeat
        """

        logging.warning("Attempting to import repeated data team number: %s", team)

        msg = QMessageBox()
        msg.setIcon(QMessageBox.Icon.Warning)
        msg.setText(
            f"Repeated data import for {form} form.\nTeam Number: {team}\nImport anyway?"
        )
        msg.setWindowTitle("Data Error")
        msg.setStandardButtons(
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )

        ret = msg.exec()
        return ret


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

        self.data_buffer = ""  # data may come in split up

        self.data_frames = {
            "pit": pandas.DataFrame(columns=PIT_DATA_HEADER),
            "qual": pandas.DataFrame(columns=QUAL_DATA_HEADER),
            "playoff": pandas.DataFrame(columns=PLAYOFF_DATA_HEADER),
        }

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
        self.nav_button_home.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextUnderIcon)
        self.nav_button_home.setIconSize(QSize(48, 48))
        self.nav_button_home.setIcon(qtawesome.icon("mdi6.home"))
        self.nav_button_home.setChecked(True)
        self.nav_button_home.clicked.connect(lambda: self.nav(self.HOME_IDX))
        self.nav_layout.addWidget(self.nav_button_home)
        self.navigation_buttons.append(self.nav_button_home)

        self.nav_button_settings = QToolButton()
        self.nav_button_settings.setCheckable(True)
        self.nav_button_settings.setText("Settings")
        self.nav_button_settings.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextUnderIcon)
        self.nav_button_settings.setIconSize(QSize(48, 48))
        self.nav_button_settings.setIcon(qtawesome.icon("mdi6.cog"))
        self.nav_button_settings.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextUnderIcon)
        self.nav_button_settings.clicked.connect(lambda: self.nav(self.SETTINGS_IDX))
        self.nav_layout.addWidget(self.nav_button_settings)
        self.navigation_buttons.append(self.nav_button_settings)

        self.nav_button_about = QToolButton()
        self.nav_button_about.setCheckable(True)
        self.nav_button_about.setText("About")
        self.nav_button_about.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextUnderIcon)
        self.nav_button_about.setIconSize(QSize(48, 48))
        self.nav_button_about.setIcon(qtawesome.icon("mdi6.information"))
        self.nav_button_about.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextUnderIcon)
        self.nav_button_about.clicked.connect(lambda: self.nav(self.ABOUT_IDX))
        self.nav_layout.addWidget(self.nav_button_about)
        self.navigation_buttons.append(self.nav_button_about)

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

        self.disk_widget = disk_widget.DiskMgmtWidget(predicate=scouting_disk_predicate)
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
            self.serial.setBaudRate(int(settings.value("baud")))

        self.serial_baud.currentTextChanged.connect(self.change_baud)
        self.serial_grid.addWidget(self.serial_baud, 1, 0)

        self.serial_bits = QComboBox()
        self.serial_bits.setMinimumWidth(110)
        self.serial_bits.addItems([str(key) for key in DATA_BITS])

        if settings.contains("databits"):
            self.serial_bits.setCurrentText(settings.value("databits"))
            self.serial.setDataBits(DATA_BITS[settings.value("databits")])

        self.serial_bits.currentTextChanged.connect(self.change_data_bits)
        self.serial_grid.addWidget(self.serial_bits, 1, 1)

        self.serial_stop = QComboBox()
        self.serial_stop.setMinimumWidth(110)
        self.serial_stop.addItems([str(key) for key in STOP_BITS])

        if settings.contains("stopbits"):
            self.serial_stop.setCurrentText(settings.value("stopbits"))
            self.serial.setStopBits(STOP_BITS[settings.value("stopbits")])

        self.serial_stop.currentTextChanged.connect(self.change_stop_bits)
        self.serial_grid.addWidget(self.serial_stop, 1, 2)

        self.serial_flow = QComboBox()
        self.serial_flow.setMinimumWidth(140)
        self.serial_flow.addItems([str(key) for key in FLOW_CONTROL])

        if settings.contains("flow"):
            self.serial_flow.setCurrentText(settings.value("flow"))
            self.serial.setFlowControl(FLOW_CONTROL[settings.value("flow")])

        self.serial_flow.currentTextChanged.connect(self.change_flow)
        self.serial_grid.addWidget(self.serial_flow, 1, 3)

        self.serial_parity = QComboBox()
        self.serial_parity.setMinimumWidth(140)
        self.serial_parity.addItems([str(key) for key in PARITY])

        if settings.contains("parity"):
            self.serial_parity.setCurrentText(settings.value("parity"))
            self.serial.setParity(PARITY[settings.value("parity")])

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

        self.settings_layout = QVBoxLayout()
        self.settings_widget.setLayout(self.settings_layout)

        self.settings_dev_box = QGroupBox("Developer Options")
        self.settings_layout.addWidget(self.settings_dev_box)

        self.settings_dev_layout = QVBoxLayout()
        self.settings_dev_box.setLayout(self.settings_dev_layout)

        self.settings_emulate_scan = QPushButton("Emuluate Single Scan")
        self.settings_emulate_scan.clicked.connect(self.emulate_scan)
        self.settings_dev_layout.addWidget(self.settings_emulate_scan)

        # * ABOUT * #
        self.about_widget = QWidget()
        self.app_widget.insertWidget(self.ABOUT_IDX, self.about_widget)

        self.about_layout = QGridLayout()
        self.about_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.about_widget.setLayout(self.about_layout)

        self.about_icon = QLabel()
        self.about_icon.setPixmap(QPixmap("icons/mercs.png"))
        self.about_layout.addWidget(self.about_icon, 0, 0, 3, 1)

        self.about_title = QLabel("Mercs Scouting Transfer")
        self.about_title.setStyleSheet("font-size: 30px;")
        self.about_layout.addWidget(self.about_title, 0, 1)

        self.about_version = QLabel(__version__)
        self.about_version.setStyleSheet("font-size: 28px;")
        self.about_layout.addWidget(self.about_version, 1, 1)

        self.about_description = QTextBrowser()
        self.about_description.setReadOnly(True)
        self.about_description.setText("A simple tool to convert QR-code output from our <a href=\"https://github.com/Mercs-MSA/2024_ScoutingDataCollection/\">2024_ScoutingDataCollection</a> using a USB Serial based QR/Barcode scanner. Features include automatic exports, automatic backup to attached volumes, support for pits scouting, qualification and playoff scouting.")
        self.about_description.setTextInteractionFlags(Qt.TextInteractionFlag.LinksAccessibleByMouse)
        self.about_description.setOpenExternalLinks(True)
        self.about_description.setMaximumHeight(self.about_description.sizeHint().height())
        self.about_layout.addWidget(self.about_description, 2, 1)


        # * LOAD STARTING STATE *#
        self.attempt_load_csv()
        self.update_serial_ports()

        self.show()

    def nav(self, page: int):
        """ Navigate to a page in app_widget using buttons """

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

        self.attempt_load_csv()

    def attempt_load_csv(self):
        event_id = "2024txtest"
        for form in self.data_frames:
            if os.path.exists(
                os.path.join(
                    self.transfer_dir_textbox.text(),
                    form,
                    f"{event_id}_{form}_total.csv",
                )
            ):
                self.data_frames[form] = pandas.read_csv(
                    os.path.join(
                        self.transfer_dir_textbox.text(),
                        form,
                        f"{event_id}_{form}_total.csv",
                    )
                )

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

        ports = [
            port
            for port in QSerialPortInfo.availablePorts()
            if not port.portName().startswith("ttyS")
        ]

        if len(ports) < 1:
            self.show_port_ref_error()
            return

        port = ports[self.serial_port.currentIndex()]

        if (
            f"{port.portName()} - {port.description()}"
            != self.serial_port.currentText()
        ):
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
            msg.setText(
                "Serial connect operation failed\n"
                "Common issues:\n"
                "1. Your user account does not have appropriate rights\n"
                "2. Another application is using the serial port"
            )
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
            msg.setText(
                f"{self.serial.error().name}\nError occured during serial operation"
            )
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

            self.data_worker = DataWorker(data, self.transfer_dir_textbox.text(), disk)
            self.data_worker.finished.connect(self.on_data_transfer_complete)
            self.data_worker.on_data_error.connect(self.on_data_error)
            self.data_worker.moveToThread(self.worker_thread)
            self.worker_thread.started.connect(
                lambda: self.data_worker.run(
                    self.data_frames,
                    self.transfer_dir_textbox.text(),
                    self.disk_widget.get_selected_disk(),
                    "2024txtest",
                )
            )

            self.worker_thread.finished.connect(self.worker_thread.deleteLater)
            self.data_worker.finished.connect(self.worker_thread.quit)
            self.data_worker.finished.connect(self.data_worker.deleteLater)

            self.worker_thread.start()

    def on_data_transfer_complete(self, df: pandas.DataFrame):
        self.connection_icon.setPixmap(
            qtawesome.icon("mdi6.qrcode-scan", color="#03a9f4").pixmap(256, 256)
        )

        self.data_frames = df

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

    def on_data_error(self, errcode: DataError):
        """
        Display a data rx error
        """
        logging.error("Data rx error: %s", errcode.name)

        msg = QMessageBox()
        msg.setIcon(QMessageBox.Icon.Critical)
        msg.setText("Recieved data does not match expected data")
        msg.setWindowTitle("Data Error")
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

    def emulate_scan(self):
        with open("example_scan.txt", "r", encoding="utf-8") as file:
            self.on_data_retrieved(file.read().strip("\r\n ") + "\r\n")

    def closeEvent( # pylint: disable=invalid-name
        self, a0: QCloseEvent | None
    ) -> None:
        """
        Application close event

        Args:
            a0 (QCloseEvent | None): Qt close event
        """
        self.serial.disconnect()
        return super().closeEvent(a0)


if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)

    app = QApplication(sys.argv)
    settings = QSettings("Mercs", "ScoutingDataTransfer")
    qdarktheme.setup_theme(additional_qss="#big_dropdown {min-height: 56px}")
    qtawesome.dark(app)
    win = MainWindow()
    sys.exit(app.exec())
