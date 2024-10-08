"""
6369 Scouting Data Transfer
Transfer data form scouting tablets using qr code scanner
"""

import sys
import os
import logging
import traceback
import typing
import datetime
import json

import pandas

from PySide6.QtWidgets import (
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
    QTextBrowser,
    QCheckBox,
    QTableView,
    QTabWidget,
    QAbstractItemView,
    QScroller,
    QInputDialog,
    QListWidget,
    QListWidgetItem,
    QScrollArea,
    QMenu,
)
from PySide6.QtCore import (
    QSettings,
    QSize,
    QIODevice,
    Qt,
    Signal,
    QObject,
    QThread,
    QUrl,
    QPoint,
)
from PySide6.QtMultimedia import QSoundEffect
from PySide6.QtGui import QCloseEvent, QPixmap, QIcon
from PySide6.QtSerialPort import QSerialPort, QSerialPortInfo
import qdarktheme
import qtawesome

import statbotics

import disk_widget
import disk_detector
import data_models
import constants
import utils

__version__: typing.Final = "v2.0.0-state"

settings: QSettings | None = None
win: QMainWindow | None = None


class DataWorker(QObject):
    finished = Signal(dict)
    on_data_error = Signal(constants.DataError)

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
            msg = QMessageBox(win)
            msg.setIcon(QMessageBox.Icon.Critical)
            msg.setText(f"Directory {directory}\ndoes not exist\nData import cancelled")
            msg.setWindowTitle("Data Error")
            msg.setStandardButtons(QMessageBox.StandardButton.Ok)
            msg.exec()
            self.finished.emit(data_frames)
            return
        data = list(utils.convert_types(self.data.strip("\r\n").split("||")))
        form = data[0]
        logging.info("Data transfer started on form %s", str(form))

        if form == "pit":
            header = constants.PIT_DATA_HEADER
            if len(data) != len(header):
                self.on_data_error.emit(constants.DataError.DATA_MALFORMED)
                self.finished.emit(data_frames)
                return
        elif form == "qual":
            header = constants.QUAL_DATA_HEADER
            if len(data) != len(header):
                self.on_data_error.emit(constants.DataError.DATA_MALFORMED)
                self.finished.emit(data_frames)
                return
        elif form == "playoff":
            header = constants.PLAYOFF_DATA_HEADER
            if len(data) != len(header):
                self.on_data_error.emit(constants.DataError.DATA_MALFORMED)
                self.finished.emit(data_frames)
                return
        else:
            self.on_data_error.emit(constants.DataError.UNKNOWN_FORM)
            self.finished.emit(data_frames)
            return

        df = pandas.DataFrame([data], columns=header)

        add_to_df = True

        if df["teamNumber"].iloc[0] == "frcnull":
            self.on_data_error.emit(constants.DataError.TEAM_NUMBER_NULL)
            self.finished.emit(data_frames)
            return

        if form == "qual" or form == "playoff":
            if df["matchNumber"].iloc[0] is None:
                self.on_data_error.emit(constants.DataError.MATCH_NUMBER_NULL)
                self.finished.emit(data_frames)
                return

        # form type
        if form == "pit":
            # check for repeats
            if int(df["teamNumber"].iloc[0].strip("frc")) in [
                int(x.strip("frc")) for x in data_frames["pit"]["teamNumber"].to_list()
            ]:
                if (
                    self.on_repeated_data("pit", df["teamNumber"].iloc[0])
                    == QMessageBox.StandardButton.No
                ):
                    add_to_df = False
        elif form == "qual":
            # check for repeats
            if (
                int(df["teamNumber"].iloc[0].strip("frc"))
                in [
                    int(x.strip("frc"))
                    for x in data_frames["qual"]["teamNumber"].to_list()
                ]
            ) and (
                int(df["matchNumber"].iloc[0])
                in [int(x) for x in data_frames["qual"]["matchNumber"].to_list()]
            ):
                if (
                    self.on_repeated_data("qual", df["teamNumber"].iloc[0])
                    == QMessageBox.StandardButton.No
                ):
                    add_to_df = False
        elif form == "playoff":
            # check for repeats
            if (
                int(df["teamNumber"].iloc[0].strip("frc"))
                in [
                    int(x.strip("frc"))
                    for x in data_frames["playoff"]["teamNumber"].to_list()
                ]
            ) and (
                int(df["matchNumber"].iloc[0])
                in [int(x) for x in data_frames["playoff"]["matchNumber"].to_list()]
            ):
                if (
                    self.on_repeated_data(
                        "playoff", int(df["teamNumber"].iloc[0].strip("frc"))
                    )
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

        msg = QMessageBox(win)
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


class EventCodeWorker(QObject):
    finished = Signal(list)
    on_error = Signal(str)

    def __init__(self, api: statbotics.Statbotics, district: str) -> None:
        super().__init__()
        self.api = api
        self.district = district

    def run(self):
        try:
            events = self.api.get_events(
                datetime.datetime.now().year, district=self.district
            )
            self.finished.emit(events)
        except Exception:
            traceback.print_exc()
            self.on_error.emit(traceback.format_exc())
            self.finished.emit([])


class PitTeamWorker(QObject):
    finished = Signal(list)
    on_error = Signal(str)

    def __init__(self, api: statbotics.Statbotics, event: str) -> None:
        super().__init__()
        self.api = api
        self.event = event

    def run(self):
        try:
            teams = self.api.get_team_events(
                event=self.event, fields=["team", "team_name"]
            )
            self.finished.emit(teams)
        except Exception:
            traceback.print_exc()
            self.on_error.emit(traceback.format_exc())
            self.finished.emit([])


class MatchMatchWorker(QObject):
    finished = Signal(list)
    pit_teams = Signal(list)
    on_error = Signal(str)

    def __init__(self, api: statbotics.Statbotics, event: str) -> None:
        super().__init__()
        self.api = api
        self.eventcode = event

    def run(self):
        try:
            pit_teams = self.api.get_team_events(
                event=self.eventcode, fields=["team", "team_name"]
            )
            matches = self.api.get_matches(
                event=self.eventcode,
                fields=[
                    "match_number",
                    "red_1",
                    "red_2",
                    "red_3",
                    "blue_1",
                    "blue_2",
                    "blue_3",
                    "playoff",
                ],
            )
            self.finished.emit(matches)
            self.pit_teams.emit(pit_teams)
        except Exception:
            traceback.print_exc()
            self.on_error.emit(traceback.format_exc())
            self.finished.emit([])


class MainWindow(QMainWindow):
    """Main Window"""

    HOME_IDX, ASSIGN_IDX, SETTINGS_IDX, ABOUT_IDX = range(4)

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("6369 Scouting Data Transfer")
        self.setWindowIcon(QIcon("icons/mercs.png"))

        self.show()

        self.serial = QSerialPort()
        self.serial.errorOccurred.connect(self.on_serial_error)
        self.serial.aboutToClose.connect(self.serial_close)
        self.serial.readyRead.connect(self.on_serial_recieve)

        self.sbapi = statbotics.Statbotics()

        self.mediaplayer = QSoundEffect()

        self.data_worker = None
        self.api_worker = None
        self.worker_thread = None

        self.is_scanning = False

        self.data_buffer = ""  # data may come in split up

        self.data_frames = {
            "pit": pandas.DataFrame(),
            "qual": pandas.DataFrame(),
            "playoff": pandas.DataFrame(),
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
        self.nav_button_home.setToolButtonStyle(
            Qt.ToolButtonStyle.ToolButtonTextUnderIcon
        )
        self.nav_button_home.setIconSize(QSize(48, 48))
        self.nav_button_home.setIcon(qtawesome.icon("mdi6.home"))
        self.nav_button_home.setChecked(True)
        self.nav_button_home.clicked.connect(lambda: self.nav(self.HOME_IDX))
        self.nav_layout.addWidget(self.nav_button_home)
        self.navigation_buttons.append(self.nav_button_home)

        self.nav_button_assign = QToolButton()
        self.nav_button_assign.setCheckable(True)
        self.nav_button_assign.setText("Assign")
        self.nav_button_assign.setToolButtonStyle(
            Qt.ToolButtonStyle.ToolButtonTextUnderIcon
        )
        self.nav_button_assign.setIconSize(QSize(48, 48))
        self.nav_button_assign.setIcon(qtawesome.icon("mdi6.clipboard-list"))
        self.nav_button_assign.setToolButtonStyle(
            Qt.ToolButtonStyle.ToolButtonTextUnderIcon
        )
        self.nav_button_assign.clicked.connect(lambda: self.nav(self.ASSIGN_IDX))
        self.nav_layout.addWidget(self.nav_button_assign)
        self.navigation_buttons.append(self.nav_button_assign)

        self.nav_button_settings = QToolButton()
        self.nav_button_settings.setCheckable(True)
        self.nav_button_settings.setText("Settings")
        self.nav_button_settings.setToolButtonStyle(
            Qt.ToolButtonStyle.ToolButtonTextUnderIcon
        )
        self.nav_button_settings.setIconSize(QSize(48, 48))
        self.nav_button_settings.setIcon(qtawesome.icon("mdi6.cog"))
        self.nav_button_settings.setToolButtonStyle(
            Qt.ToolButtonStyle.ToolButtonTextUnderIcon
        )
        self.nav_button_settings.clicked.connect(lambda: self.nav(self.SETTINGS_IDX))
        self.nav_layout.addWidget(self.nav_button_settings)
        self.navigation_buttons.append(self.nav_button_settings)

        self.nav_button_about = QToolButton()
        self.nav_button_about.setCheckable(True)
        self.nav_button_about.setText("About")
        self.nav_button_about.setToolButtonStyle(
            Qt.ToolButtonStyle.ToolButtonTextUnderIcon
        )
        self.nav_button_about.setIconSize(QSize(48, 48))
        self.nav_button_about.setIcon(qtawesome.icon("mdi6.information"))
        self.nav_button_about.setToolButtonStyle(
            Qt.ToolButtonStyle.ToolButtonTextUnderIcon
        )
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

        self.disk_widget = disk_widget.DiskMgmtWidget(
            predicate=disk_detector.scouting_disk_predicate
        )
        self.disk_widget.set_select_visible(False)
        self.drive_layout.addWidget(self.disk_widget)

        self.data_view_tabs = QTabWidget()
        self.drive_layout.addWidget(self.data_view_tabs)

        self.data_view_pit_widget = QWidget()
        self.data_view_tabs.addTab(self.data_view_pit_widget, "Pit")

        self.data_view_pit_layout = QVBoxLayout()
        self.data_view_pit_layout.setContentsMargins(0, 0, 0, 0)
        self.data_view_pit_widget.setLayout(self.data_view_pit_layout)

        self.pit_model = data_models.PandasModel(self.data_frames["pit"])

        self.pit_table_view = QTableView()
        self.pit_table_view.setEditTriggers(
            QAbstractItemView.EditTrigger.NoEditTriggers
        )
        self.pit_table_view.setAlternatingRowColors(True)
        self.pit_table_view.setSelectionMode(
            QAbstractItemView.SelectionMode.NoSelection
        )
        self.pit_table_view.setModel(self.pit_model)
        self.pit_table_view.setHorizontalScrollMode(
            QAbstractItemView.ScrollMode.ScrollPerPixel
        )
        self.data_view_pit_layout.addWidget(self.pit_table_view)

        self.data_view_qual_widget = QWidget()
        self.data_view_tabs.addTab(self.data_view_qual_widget, "Qualifications")

        self.data_view_qual_layout = QVBoxLayout()
        self.data_view_qual_layout.setContentsMargins(0, 0, 0, 0)
        self.data_view_qual_widget.setLayout(self.data_view_qual_layout)

        self.qual_model = data_models.PandasModel(self.data_frames["qual"])

        self.qual_table_view = QTableView()
        self.qual_table_view.setEditTriggers(
            QAbstractItemView.EditTrigger.NoEditTriggers
        )
        self.qual_table_view.setAlternatingRowColors(True)
        self.qual_table_view.setSelectionMode(
            QAbstractItemView.SelectionMode.NoSelection
        )
        self.qual_table_view.setModel(self.qual_model)
        self.qual_table_view.setHorizontalScrollMode(
            QAbstractItemView.ScrollMode.ScrollPerPixel
        )
        self.data_view_qual_layout.addWidget(self.qual_table_view)

        self.data_view_playoff_widget = QWidget()
        self.data_view_tabs.addTab(self.data_view_playoff_widget, "Playoffs")

        self.data_view_playoff_layout = QVBoxLayout()
        self.data_view_playoff_layout.setContentsMargins(0, 0, 0, 0)
        self.data_view_playoff_widget.setLayout(self.data_view_playoff_layout)

        self.playoff_model = data_models.PandasModel(self.data_frames["playoff"])

        self.playoff_table_view = QTableView()
        self.playoff_table_view.setEditTriggers(
            QAbstractItemView.EditTrigger.NoEditTriggers
        )
        self.playoff_table_view.setAlternatingRowColors(True)
        self.playoff_table_view.setSelectionMode(
            QAbstractItemView.SelectionMode.NoSelection
        )
        self.playoff_table_view.setModel(self.playoff_model)
        self.playoff_table_view.setHorizontalScrollMode(
            QAbstractItemView.ScrollMode.ScrollPerPixel
        )
        self.data_view_playoff_layout.addWidget(self.playoff_table_view)

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
        self.serial_baud.addItems([str(baud) for baud in constants.BAUDS])

        if settings.contains("baud"):
            self.serial_baud.setCurrentText(str(settings.value("baud")))
            self.serial.setBaudRate(int(settings.value("baud")))

        self.serial_baud.currentTextChanged.connect(self.change_baud)
        self.serial_grid.addWidget(self.serial_baud, 1, 0)

        self.serial_bits = QComboBox()
        self.serial_bits.setMinimumWidth(110)
        self.serial_bits.addItems([str(key) for key in constants.DATA_BITS])

        if settings.contains("databits"):
            self.serial_bits.setCurrentText(settings.value("databits"))
            self.serial.setDataBits(constants.DATA_BITS[settings.value("databits")])

        self.serial_bits.currentTextChanged.connect(self.change_data_bits)
        self.serial_grid.addWidget(self.serial_bits, 1, 1)

        self.serial_stop = QComboBox()
        self.serial_stop.setMinimumWidth(110)
        self.serial_stop.addItems([str(key) for key in constants.STOP_BITS])

        if settings.contains("stopbits"):
            self.serial_stop.setCurrentText(settings.value("stopbits"))
            self.serial.setStopBits(constants.STOP_BITS[settings.value("stopbits")])

        self.serial_stop.currentTextChanged.connect(self.change_stop_bits)
        self.serial_grid.addWidget(self.serial_stop, 1, 2)

        self.serial_flow = QComboBox()
        self.serial_flow.setMinimumWidth(140)
        self.serial_flow.addItems([str(key) for key in constants.FLOW_CONTROL])

        if settings.contains("flow"):
            self.serial_flow.setCurrentText(settings.value("flow"))
            self.serial.setFlowControl(constants.FLOW_CONTROL[settings.value("flow")])

        self.serial_flow.currentTextChanged.connect(self.change_flow)
        self.serial_grid.addWidget(self.serial_flow, 1, 3)

        self.serial_parity = QComboBox()
        self.serial_parity.setMinimumWidth(140)
        self.serial_parity.addItems([str(key) for key in constants.PARITY])

        if settings.contains("parity"):
            self.serial_parity.setCurrentText(settings.value("parity"))
            self.serial.setParity(constants.PARITY[settings.value("parity")])

        self.serial_parity.currentTextChanged.connect(self.change_parity)
        self.serial_grid.addWidget(self.serial_parity, 1, 4)

        self.serial_disconnect = QPushButton("Disconnect")
        self.serial_disconnect.clicked.connect(self.disconnect_port)
        self.serial_disconnect.setEnabled(False)
        self.serial_grid.addWidget(self.serial_disconnect, 2, 0, 1, 6)

        self.scanner_layout.addStretch()

        self.connection_icon = qtawesome.IconWidget()
        self.connection_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.connection_icon.setIconSize(QSize(256, 256))
        self.connection_icon.setIcon(qtawesome.icon("mdi6.serial-port"))
        self.scanner_layout.addWidget(self.connection_icon)

        self.scanner_layout.addStretch()

        # * ASSIGN * #
        self.assign_widget = QTabWidget()
        self.app_widget.insertWidget(self.ASSIGN_IDX, self.assign_widget)

        self.assign_pit_widget = QWidget()
        self.assign_widget.addTab(self.assign_pit_widget, "Pit")

        self.assign_pit_layout = QVBoxLayout()
        self.assign_pit_widget.setLayout(self.assign_pit_layout)

        self.assign_pit_top_options = QHBoxLayout()
        self.assign_pit_layout.addLayout(self.assign_pit_top_options)

        self.assign_pit_generate_statbotics = QPushButton("Pull from Statbotics")
        self.assign_pit_generate_statbotics.setIcon(qtawesome.icon("mdi6.web"))
        self.assign_pit_generate_statbotics.setIconSize(QSize(32, 32))
        self.assign_pit_generate_statbotics.clicked.connect(
            self.assign_pit_generate_worker
        )
        self.assign_pit_top_options.addWidget(self.assign_pit_generate_statbotics)

        self.assign_pit_clear_ignored = QPushButton("Clear")
        self.assign_pit_clear_ignored.setIcon(qtawesome.icon("mdi6.eraser"))
        self.assign_pit_clear_ignored.setIconSize(QSize(32, 32))
        # self.assign_pit_clear_ignored.clicked.connect(self.assign_pit_ignored_teams.clear) # this is done later after listview in init'ed
        self.assign_pit_top_options.addWidget(self.assign_pit_clear_ignored)

        # creating a QListWidget
        self.assign_pit_ignored_teams = QListWidget(self)

        # setting drag drop mode
        self.assign_pit_ignored_teams.setContextMenuPolicy(
            Qt.ContextMenuPolicy.CustomContextMenu
        )
        self.assign_pit_ignored_teams.customContextMenuRequested.connect(
            self.assign_show_ignored_pit_context
        )
        self.assign_pit_ignored_teams.setDragDropMode(
            QAbstractItemView.DragDropMode.DragDrop
        )
        self.assign_pit_ignored_teams.setDefaultDropAction(Qt.DropAction.MoveAction)
        self.assign_pit_clear_ignored.clicked.connect(
            self.assign_pit_ignored_teams.clear
        )

        self.assign_pit_layout.addWidget(self.assign_pit_ignored_teams)

        self.assign_pit_tablets = 6
        self.assign_pit_tablet_slots: list[QListWidget] = []

        self.assign_pit_tablet_layout = QHBoxLayout()
        self.assign_pit_layout.addLayout(self.assign_pit_tablet_layout)

        self.assign_pit_tablet_label = QLabel(
            f"Tablet Count: {self.assign_pit_tablets}"
        )
        self.assign_pit_tablet_layout.addWidget(self.assign_pit_tablet_label)

        self.assign_pit_tablet_add = QPushButton()
        self.assign_pit_tablet_add.setIcon(qtawesome.icon("mdi6.plus"))
        self.assign_pit_tablet_add.setIconSize(QSize(32, 32))
        self.assign_pit_tablet_add.clicked.connect(
            lambda: self.change_assign_pit_tablet_count(1)
        )
        self.assign_pit_tablet_layout.addWidget(self.assign_pit_tablet_add)

        self.assign_pit_tablet_subtract = QPushButton()
        self.assign_pit_tablet_subtract.setIcon(qtawesome.icon("mdi6.minus"))
        self.assign_pit_tablet_subtract.setIconSize(QSize(32, 32))
        self.assign_pit_tablet_subtract.clicked.connect(
            lambda: self.change_assign_pit_tablet_count(-1)
        )
        self.assign_pit_tablet_layout.addWidget(self.assign_pit_tablet_subtract)

        self.assign_pit_tablet_generate = QPushButton("Generate Slots")
        self.assign_pit_tablet_generate.setIcon(
            qtawesome.icon("mdi6.cellphone-settings")
        )
        self.assign_pit_tablet_generate.setIconSize(QSize(32, 32))
        self.assign_pit_tablet_generate.clicked.connect(
            self.generate_assign_pit_tablet_slots
        )
        self.assign_pit_tablet_layout.addWidget(self.assign_pit_tablet_generate)

        self.assign_pit_tablet_sort = QPushButton("Auto Sort")
        self.assign_pit_tablet_sort.setIcon(qtawesome.icon("mdi6.auto-fix"))
        self.assign_pit_tablet_sort.setIconSize(QSize(32, 32))
        self.assign_pit_tablet_sort.setEnabled(False)
        self.assign_pit_tablet_sort.clicked.connect(self.sort_assign_pit_tablet_slots)
        self.assign_pit_tablet_layout.addWidget(self.assign_pit_tablet_sort)

        self.assign_pit_tablet_clear = QPushButton("Clear Slots")
        self.assign_pit_tablet_clear.setIcon(
            qtawesome.icon("mdi6.notification-clear-all")
        )
        self.assign_pit_tablet_clear.setIconSize(QSize(32, 32))
        self.assign_pit_tablet_clear.clicked.connect(self.clear_assign_pit_tablet_slots)
        self.assign_pit_tablet_layout.addWidget(self.assign_pit_tablet_clear)

        self.assign_pit_tablet_export = QPushButton("Export Dir")
        self.assign_pit_tablet_export.setIcon(qtawesome.icon("mdi6.export"))
        self.assign_pit_tablet_export.setIconSize(QSize(32, 32))
        self.assign_pit_tablet_export.clicked.connect(
            self.export_assign_pit_tablet_slots
        )
        self.assign_pit_tablet_layout.addWidget(self.assign_pit_tablet_export)

        self.assign_pit_tablets_scroll = QScrollArea()
        self.assign_pit_tablets_scroll.setWidgetResizable(True)
        self.assign_pit_layout.addWidget(self.assign_pit_tablets_scroll)

        self.assign_pit_tablets_widget = QWidget()
        self.assign_pit_tablets_scroll.setWidget(self.assign_pit_tablets_widget)

        self.assign_pit_tablets_layout = QHBoxLayout()
        self.assign_pit_tablets_widget.setLayout(self.assign_pit_tablets_layout)

        # Match
        self.assign_match_widget = QWidget()
        self.assign_widget.addTab(self.assign_match_widget, "Match")

        self.assign_match_layout = QVBoxLayout()
        self.assign_match_widget.setLayout(self.assign_match_layout)

        self.assign_match_top_options = QHBoxLayout()
        self.assign_match_layout.addLayout(self.assign_match_top_options)

        self.assign_match_generate_statbotics = QPushButton("Pull from Statbotics")
        self.assign_match_generate_statbotics.setIcon(qtawesome.icon("mdi6.web"))
        self.assign_match_generate_statbotics.setIconSize(QSize(32, 32))
        self.assign_match_generate_statbotics.clicked.connect(
            self.assign_match_generate_worker
        )
        self.assign_match_top_options.addWidget(self.assign_match_generate_statbotics)

        self.assign_match_clear_ignored = QPushButton("Clear")
        self.assign_match_clear_ignored.setIcon(qtawesome.icon("mdi6.eraser"))
        self.assign_match_clear_ignored.setIconSize(QSize(32, 32))
        # self.assign_match_clear_ignored.clicked.connect(self.assign_match_ignored_teams.clear) # this is done later after listview in init'ed
        self.assign_match_top_options.addWidget(self.assign_match_clear_ignored)

        # creating a QListWidget
        self.assign_match_pit_teams = []

        self.assign_match_ignored_teams = QListWidget(self)

        self.assign_match_ignored_teams.setContextMenuPolicy(
            Qt.ContextMenuPolicy.CustomContextMenu
        )
        self.assign_match_ignored_teams.customContextMenuRequested.connect(
            self.assign_show_ignored_match_context
        )
        self.assign_match_ignored_teams.setDragDropMode(
            QAbstractItemView.DragDropMode.DragDrop
        )
        self.assign_match_ignored_teams.setDefaultDropAction(Qt.DropAction.MoveAction)
        self.assign_match_clear_ignored.clicked.connect(
            self.assign_match_ignored_teams.clear
        )

        self.assign_match_layout.addWidget(self.assign_match_ignored_teams)

        self.assign_match_tablets = 6
        self.assign_match_tablet_slots: list[QListWidget] = []

        self.assign_match_tablet_layout = QHBoxLayout()
        self.assign_match_layout.addLayout(self.assign_match_tablet_layout)

        self.assign_match_tablet_label = QLabel(
            f"Tablet Count: {self.assign_match_tablets}"
        )
        self.assign_match_tablet_layout.addWidget(self.assign_match_tablet_label)

        self.assign_match_tablet_add = QPushButton()
        self.assign_match_tablet_add.setIcon(qtawesome.icon("mdi6.plus"))
        self.assign_match_tablet_add.setIconSize(QSize(32, 32))
        self.assign_match_tablet_add.clicked.connect(
            lambda: self.change_assign_match_tablet_count(1)
        )
        self.assign_match_tablet_layout.addWidget(self.assign_match_tablet_add)

        self.assign_match_tablet_subtract = QPushButton()
        self.assign_match_tablet_subtract.setIcon(qtawesome.icon("mdi6.minus"))
        self.assign_match_tablet_subtract.setIconSize(QSize(32, 32))
        self.assign_match_tablet_subtract.clicked.connect(
            lambda: self.change_assign_match_tablet_count(-1)
        )
        self.assign_match_tablet_layout.addWidget(self.assign_match_tablet_subtract)

        self.assign_match_tablet_generate = QPushButton("Generate Slots")
        self.assign_match_tablet_generate.setIcon(
            qtawesome.icon("mdi6.cellphone-settings")
        )
        self.assign_match_tablet_generate.setIconSize(QSize(32, 32))
        self.assign_match_tablet_generate.clicked.connect(
            self.generate_assign_match_tablet_slots
        )
        self.assign_match_tablet_layout.addWidget(self.assign_match_tablet_generate)

        self.assign_match_tablet_sort = QPushButton("Auto Sort")
        self.assign_match_tablet_sort.setIcon(qtawesome.icon("mdi6.auto-fix"))
        self.assign_match_tablet_sort.setIconSize(QSize(32, 32))
        self.assign_match_tablet_sort.setEnabled(False)
        self.assign_match_tablet_sort.clicked.connect(
            self.sort_assign_match_tablet_slots
        )
        self.assign_match_tablet_layout.addWidget(self.assign_match_tablet_sort)

        self.assign_match_tablet_clear = QPushButton("Clear Slots")
        self.assign_match_tablet_clear.setIcon(
            qtawesome.icon("mdi6.notification-clear-all")
        )
        self.assign_match_tablet_clear.setIconSize(QSize(32, 32))
        self.assign_match_tablet_clear.clicked.connect(
            self.clear_assign_match_tablet_slots
        )
        self.assign_match_tablet_layout.addWidget(self.assign_match_tablet_clear)

        self.assign_match_tablet_export = QPushButton("Export Dir")
        self.assign_match_tablet_export.setIcon(qtawesome.icon("mdi6.export"))
        self.assign_match_tablet_export.setIconSize(QSize(32, 32))
        self.assign_match_tablet_export.clicked.connect(
            self.export_assign_match_tablet_slots
        )
        self.assign_match_tablet_layout.addWidget(self.assign_match_tablet_export)

        self.assign_match_tablets_scroll = QScrollArea()
        self.assign_match_tablets_scroll.setWidgetResizable(True)
        self.assign_match_layout.addWidget(self.assign_match_tablets_scroll)

        self.assign_match_tablets_widget = QWidget()
        self.assign_match_tablets_scroll.setWidget(self.assign_match_tablets_widget)

        self.assign_match_tablets_layout = QHBoxLayout()
        self.assign_match_tablets_widget.setLayout(self.assign_match_tablets_layout)

        # * SETTINGS * #
        self.settings_widget = QWidget()
        self.app_widget.insertWidget(self.SETTINGS_IDX, self.settings_widget)

        self.settings_layout = QVBoxLayout()
        self.settings_widget.setLayout(self.settings_layout)

        self.settings_dev_box = QGroupBox("Developer")
        self.settings_layout.addWidget(self.settings_dev_box)

        self.settings_dev_layout = QVBoxLayout()
        self.settings_dev_box.setLayout(self.settings_dev_layout)

        self.settings_emulate_scan = QPushButton("Emulate Single Scan")
        self.settings_emulate_scan.clicked.connect(self.emulate_scan)
        self.settings_dev_layout.addWidget(self.settings_emulate_scan)

        self.settings_ui_box = QGroupBox("UI")
        self.settings_layout.addWidget(self.settings_ui_box)

        self.settings_ui_layout = QVBoxLayout()
        self.settings_ui_box.setLayout(self.settings_ui_layout)

        self.settings_touchui = QCheckBox("Touch UI")
        self.settings_touchui.stateChanged.connect(self.set_touch_mode)
        self.settings_ui_layout.addWidget(self.settings_touchui)

        self.settings_event_box = QGroupBox("Event")
        self.settings_layout.addWidget(self.settings_event_box)

        self.settings_event_layout = QHBoxLayout()
        self.settings_event_box.setLayout(self.settings_event_layout)

        self.event_entry = QComboBox()
        self.event_entry.setEditable(True)
        self.event_entry.currentTextChanged.connect(self.on_event_changed)
        self.settings_event_layout.addWidget(self.event_entry)

        if settings.contains("event"):
            self.event_entry.setEditText(settings.value("event", type=str))

        self.event_fetch = QPushButton("Fetch")
        self.event_fetch.clicked.connect(self.fetch_events)
        self.settings_event_layout.addWidget(self.event_fetch)

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
        self.about_description.setText(
            "A simple tool to convert QR-code output from our "
            '<a href="https://github.com/Mercs-MSA/2024_ScoutingDataCollection">'
            "2024_ScoutingDataCollection</a> using a USB Serial based QR/Barcode scanner. "
            "Features include a data viewer, Statbotics event fetching, automatic exports, "
            "automatic backup to attached volumes, support for pits scouting, "
            "qualification and playoff scouting."
        )
        self.about_description.setTextInteractionFlags(
            Qt.TextInteractionFlag.LinksAccessibleByMouse
        )
        self.about_description.setOpenExternalLinks(True)
        self.about_description.setMaximumHeight(
            self.about_description.sizeHint().height()
        )
        self.about_layout.addWidget(self.about_description, 2, 1)

        # * UI post-load *#
        self.spin_animation = qtawesome.Spin(self.connection_icon, interval=5, step=2)

        # * LOAD STARTING STATE *#
        self.attempt_load_csv()
        self.update_serial_ports()

        if settings.contains("touchui"):
            self.set_touch_mode(settings.value("touchui", type=bool))
            self.settings_touchui.setChecked(settings.value("touchui", type=bool))

    def nav(self, page: int):
        """Navigate to a page in app_widget using buttons"""

        for button in self.navigation_buttons:
            button.setChecked(False)

        self.app_widget.setCurrentIndex(page)
        self.navigation_buttons[page].setChecked(True)

    def set_touch_mode(self, enabled: bool):
        if enabled:
            self.setStyleSheet(
                "QPushButton { height: 36px; font-size: 14px; }"
                "QToolButton { font-size: 14px; }"
                "QComboBox { height: 42px; }"
                "QLineEdit { height: 36px; }"
                "QCheckBox::indicator { width: 32px; height: 32px; }"
                "QTabBar::tab { font-size: 16px; }"
                "QScrollBar:vertical:handle { width: 20px; }"
                "QScrollBar:horizontal:handle { height: 20px; }"
            )
            QScroller.grabGesture(
                self.pit_table_view.viewport(),
                QScroller.ScrollerGestureType.TouchGesture,
            )
            QScroller.grabGesture(
                self.qual_table_view.viewport(),
                QScroller.ScrollerGestureType.TouchGesture,
            )
            QScroller.grabGesture(
                self.playoff_table_view.viewport(),
                QScroller.ScrollerGestureType.TouchGesture,
            )
        else:
            self.setStyleSheet("")
            QScroller.ungrabGesture(self.pit_table_view.viewport())
            QScroller.ungrabGesture(self.qual_table_view.viewport())
            QScroller.ungrabGesture(self.playoff_table_view.viewport())

        settings.setValue("touchui", enabled)

    def on_event_changed(self):
        settings.setValue("event", self.event_entry.currentText())

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
        event_id = self.event_entry.currentText()
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
            elif form == "pit":
                self.data_frames["pit"] = pandas.DataFrame(
                    columns=constants.PIT_DATA_HEADER
                )
            elif form == "qual":
                self.data_frames["qual"] = pandas.DataFrame(
                    columns=constants.QUAL_DATA_HEADER
                )
            elif form == "playoff":
                self.data_frames["playoff"] = pandas.DataFrame(
                    columns=constants.PLAYOFF_DATA_HEADER
                )

        self.pit_model.load_data(self.data_frames["pit"])
        self.qual_model.load_data(self.data_frames["qual"])
        self.playoff_model.load_data(self.data_frames["playoff"])

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

        bits = constants.DATA_BITS[self.serial_bits.currentText()]
        self.serial.setDataBits(bits)
        settings.setValue("databits", self.serial_bits.currentText())

    def change_stop_bits(self):
        """
        Set stop bits from combo box
        """

        stop_bits = constants.STOP_BITS[self.serial_stop.currentText()]
        self.serial.setStopBits(stop_bits)
        settings.setValue("stopbits", self.serial_stop.currentText())

    def change_flow(self):
        """
        Set flow control from combo box
        """

        flow = constants.FLOW_CONTROL[self.serial_flow.currentText()]
        self.serial.setFlowControl(flow)
        settings.setValue("flow", self.serial_flow.currentText())

    def change_parity(self):
        """
        Set parity type from combo box
        """

        parity = constants.PARITY[self.serial_parity.currentText()]
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

        bits = constants.DATA_BITS[self.serial_bits.currentText()]
        self.serial.setDataBits(bits)

        stop_bits = constants.STOP_BITS[self.serial_stop.currentText()]
        self.serial.setStopBits(stop_bits)

        flow = constants.FLOW_CONTROL[self.serial_flow.currentText()]
        self.serial.setFlowControl(flow)

        parity = constants.PARITY[self.serial_parity.currentText()]
        self.serial.setParity(parity)

        ok = self.serial.open(QIODevice.ReadWrite)
        if ok:
            logging.info("Connected to serial")
            self.set_serial_options_enabled(False)
            self.connection_icon.setIcon(
                qtawesome.icon("mdi6.qrcode-scan", color="#03a9f4")
            )
        else:
            logging.error("Can't connect to serial port, %s", self.serial.error().name)
            msg = QMessageBox(self)
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
        self.connection_icon.setIcon(qtawesome.icon("mdi6.serial-port"))

    def on_serial_error(self):
        """
        Serial error callback
        """

        if self.serial.error() == QSerialPort.SerialPortError.NoError:
            msg = QMessageBox(self)
            msg.setIcon(QMessageBox.Icon.Information)
            msg.setText("Connection Successful!")
            msg.setWindowTitle("Serial")
            msg.setStandardButtons(QMessageBox.StandardButton.Ok)
            msg.exec()
            return

        if self.serial.isOpen():
            self.serial.close()
            msg = QMessageBox(self)
            msg.setIcon(QMessageBox.Icon.Critical)
            msg.setText(
                f"{self.serial.error().name}\nError occured during serial operation"
            )
            msg.setWindowTitle("Serial error")
            msg.setStandardButtons(QMessageBox.StandardButton.Ok)
            msg.exec()

            self.connection_icon.setIcon(
                qtawesome.icon("mdi6.alert-decagram", color="#f44336")
            )

    def serial_close(self):
        """
        Serial shutdown callback
        """

        msg = QMessageBox(self)
        msg.setIcon(QMessageBox.Icon.Information)
        msg.setText("Serial controller shut down")
        msg.setWindowTitle("Serial")
        msg.setStandardButtons(QMessageBox.StandardButton.Ok)
        msg.exec()

        self.set_serial_options_enabled(True)

    def on_serial_recieve(self):
        self.connection_icon.setIcon(
            qtawesome.icon(
                "mdi6.loading", color="#03a9f4", animation=self.spin_animation
            )
        )
        data = self.serial.readAll()
        self.data_buffer += data.data().decode()
        if self.data_buffer.endswith("\n"):
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
                    self.event_entry.currentText(),
                )
            )

            self.data_worker.finished.connect(self.worker_thread.quit)

            self.worker_thread.start()

    def fetch_events(self):
        if self.worker_thread and self.worker_thread.isRunning():
            msg = QMessageBox(self)
            msg.setIcon(QMessageBox.Icon.Critical)
            msg.setText("Another API operation is running")
            msg.setWindowTitle("API")
            msg.setStandardButtons(QMessageBox.StandardButton.Ok)
            msg.exec()
        else:
            district, ok = QInputDialog.getText(
                self, "API", "What district would you like to fetch"
            )

            if ok:
                self.worker_thread = QThread()

                self.api_worker = EventCodeWorker(self.sbapi, district)
                self.api_worker.finished.connect(self.on_event_fetch_complete)
                self.api_worker.on_error.connect(self.on_api_error)
                self.api_worker.moveToThread(self.worker_thread)
                self.worker_thread.started.connect(self.api_worker.run)

                self.api_worker.finished.connect(self.worker_thread.quit)

                self.worker_thread.start()

    def on_event_fetch_complete(self, events: list):
        self.event_entry.clear()
        self.event_entry.addItems([event["key"] for event in events])

    def on_api_error(self, stack: str):
        self.mediaplayer.setSource(QUrl.fromLocalFile("mad.wav"))
        self.mediaplayer.setVolume(1)
        self.mediaplayer.play()

        msg = QMessageBox(self)
        msg.setIcon(QMessageBox.Icon.Critical)
        msg.setText("Error from fetch operation")
        msg.setWindowTitle("API")
        msg.setDetailedText(stack)
        msg.setStandardButtons(QMessageBox.StandardButton.Ok)
        msg.exec()

    def on_data_transfer_complete(self, df: pandas.DataFrame):
        self.connection_icon.setIcon(
            qtawesome.icon("mdi6.qrcode-scan", color="#03a9f4")
        )

        self.data_frames = df
        self.pit_model.load_data(self.data_frames["pit"])
        self.qual_model.load_data(self.data_frames["qual"])
        self.playoff_model.load_data(self.data_frames["playoff"])

        self.is_scanning = False

    def show_port_ref_error(self):
        """
        Display a serial port list refresh error
        """

        self.mediaplayer.setSource(QUrl.fromLocalFile("mad.wav"))
        self.mediaplayer.setVolume(1)
        self.mediaplayer.play()

        msg = QMessageBox(self)
        msg.setIcon(QMessageBox.Icon.Warning)
        msg.setText("Port refresh required")
        msg.setWindowTitle("Can't connect")
        msg.setStandardButtons(QMessageBox.StandardButton.Ok)
        msg.exec()

    def on_data_error(self, errcode: constants.DataError):
        """
        Display a data rx error
        """
        logging.error("Data rx error: %s", errcode.name)

        self.mediaplayer.setSource(QUrl.fromLocalFile("mad.wav"))
        self.mediaplayer.setVolume(1)
        self.mediaplayer.play()

        msg = QMessageBox(self)
        msg.setIcon(QMessageBox.Icon.Critical)
        msg.setText(f"Error when recieving data:\n{errcode.name}")
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

    def change_assign_pit_tablet_count(self, change: int):
        if self.assign_pit_tablets + change in range(1, 13):
            self.assign_pit_tablets += change
        self.assign_pit_tablet_label.setText(f"Tablet Count: {self.assign_pit_tablets}")

    def change_assign_match_tablet_count(self, change: int):
        if self.assign_match_tablets + change in range(1, 13):
            self.assign_match_tablets += change
        self.assign_match_tablet_label.setText(
            f"Tablet Count: {self.assign_match_tablets}"
        )

    def generate_assign_pit_tablet_slots(self):
        self.assign_pit_tablet_add.setEnabled(False)
        self.assign_pit_tablet_subtract.setEnabled(False)
        self.assign_pit_tablet_generate.setEnabled(False)
        self.assign_pit_tablet_sort.setEnabled(True)

        for i in range(self.assign_pit_tablets):
            slot = QListWidget()
            slot.setDragDropMode(QAbstractItemView.DragDropMode.DragDrop)
            slot.setDefaultDropAction(Qt.DropAction.MoveAction)
            self.assign_pit_tablets_layout.addWidget(slot)

            self.assign_pit_tablet_slots.append(slot)

    def generate_assign_match_tablet_slots(self):
        self.assign_match_tablet_add.setEnabled(False)
        self.assign_match_tablet_subtract.setEnabled(False)
        self.assign_match_tablet_generate.setEnabled(False)
        self.assign_match_tablet_sort.setEnabled(True)

        for i in range(self.assign_match_tablets):
            slot = QListWidget()
            slot.setDragDropMode(QAbstractItemView.DragDropMode.DragDrop)
            slot.setDefaultDropAction(Qt.DropAction.MoveAction)
            self.assign_match_tablets_layout.addWidget(slot)

            self.assign_match_tablet_slots.append(slot)

    def sort_assign_pit_tablet_slots(self):
        chunks = utils.chunk_into_n(
            [
                self.assign_pit_ignored_teams.item(x)
                for x in range(self.assign_pit_ignored_teams.count())
            ],
            self.assign_pit_tablets,
        )

        if len(self.assign_pit_tablet_slots) != len(chunks):
            return

        for idx, chunk in enumerate(chunks):
            for item in chunk:
                new_item = QListWidgetItem()
                new_item.setText(item.text())
                new_item.setData(
                    Qt.ItemDataRole.UserRole, item.data(Qt.ItemDataRole.UserRole)
                )
                self.assign_pit_tablet_slots[idx].addItem(new_item)

        self.assign_pit_ignored_teams.clear()

    def sort_assign_match_tablet_slots(self):
        converted_matches = [
            self.assign_match_ignored_teams.item(x).data(Qt.ItemDataRole.UserRole)
            for x in range(self.assign_match_ignored_teams.count())
        ]

        outputs = [{"field": []} for i in range(self.assign_match_tablets)]

        for index, session in enumerate(converted_matches):
            outputs[index % int(self.assign_match_tablets)]["field"].append(session)

        for idx, out in enumerate(outputs):
            for session in out["field"]:
                item = QListWidgetItem()
                item.setText(
                    f"Team: {session['teamNumber']} | Match: {session['match']} | Alliance: {session['alliance']} | Position: {session['position']}"
                )
                item.setData(Qt.ItemDataRole.UserRole, session)
                self.assign_match_tablet_slots[idx].addItem(item)

        self.assign_match_ignored_teams.clear()

    def clear_assign_pit_tablet_slots(self):
        self.assign_pit_tablet_add.setEnabled(True)
        self.assign_pit_tablet_subtract.setEnabled(True)
        self.assign_pit_tablet_generate.setEnabled(True)
        self.assign_pit_tablet_sort.setEnabled(False)

        for slot in self.assign_pit_tablet_slots:
            for item in [slot.item(x) for x in range(slot.count())]:
                new_item = QListWidgetItem()
                new_item.setText(item.text())
                new_item.setData(
                    Qt.ItemDataRole.UserRole, item.data(Qt.ItemDataRole.UserRole)
                )
                self.assign_pit_ignored_teams.addItem(new_item)

            self.assign_pit_tablets_layout.removeWidget(slot)
            slot.deleteLater()

        self.assign_pit_tablet_slots.clear()

    def clear_assign_match_tablet_slots(self):
        self.assign_match_tablet_add.setEnabled(True)
        self.assign_match_tablet_subtract.setEnabled(True)
        self.assign_match_tablet_generate.setEnabled(True)
        self.assign_match_tablet_sort.setEnabled(False)

        for slot in self.assign_match_tablet_slots:
            for item in [slot.item(x) for x in range(slot.count())]:
                new_item = QListWidgetItem()
                new_item.setText(item.text())
                new_item.setData(
                    Qt.ItemDataRole.UserRole, item.data(Qt.ItemDataRole.UserRole)
                )
                self.assign_match_ignored_teams.addItem(new_item)

            self.assign_match_tablets_layout.removeWidget(slot)
            slot.deleteLater()

        self.assign_match_tablet_slots.clear()

    def export_assign_pit_tablet_slots(self):
        output_sessions = []

        for slot in self.assign_pit_tablet_slots:
            output_sessions.append(
                {
                    "pit": [
                        {"team": d.data(Qt.ItemDataRole.UserRole)[0]}
                        for d in [slot.item(x) for x in range(slot.count())]
                    ],
                    "field": [],
                    "teamnames": [
                        {
                            str(d.data(Qt.ItemDataRole.UserRole)[0]): d.data(
                                Qt.ItemDataRole.UserRole
                            )[1]
                        }
                        for d in [slot.item(x) for x in range(slot.count())]
                    ],
                }
            )

        directory = QFileDialog.getExistingDirectory(self, "Select Directory")
        if directory:
            for i in range(len(output_sessions)):
                json.dump(
                    output_sessions[i],
                    open(os.path.join(directory, f"assign_{i}.json"), "w"),
                )

    def export_assign_match_tablet_slots(self):
        merged_teams = {
            str(d["team"]): d["team_name"] for d in self.assign_match_pit_teams
        }
        print(merged_teams)
        output_sessions = []

        for slot in self.assign_match_tablet_slots:
            output_sessions.append(
                {
                    "pit": [],
                    "field": [
                        item.data(Qt.ItemDataRole.UserRole)
                        for item in [slot.item(x) for x in range(slot.count())]
                    ],
                    "teamnames": [
                        {
                            str(
                                d.data(Qt.ItemDataRole.UserRole)["teamNumber"]
                            ): merged_teams[
                                str(d.data(Qt.ItemDataRole.UserRole)["teamNumber"])
                            ]
                        }
                        for d in [slot.item(x) for x in range(slot.count())]
                    ],
                }
            )

        directory = QFileDialog.getExistingDirectory(self, "Select Directory")
        if directory:
            for i in range(len(output_sessions)):
                json.dump(
                    output_sessions[i],
                    open(os.path.join(directory, f"assign_{i}.json"), "w"),
                )

    def assign_show_ignored_pit_context(self, point: QPoint):
        global_pos = self.assign_pit_ignored_teams.mapToGlobal(point)

        menu = QMenu()
        menu.addAction("Delete", self.assign_pit_context_delete)
        menu.addAction("Insert", self.assign_pit_context_insert)

        menu.exec(global_pos)

    def assign_show_ignored_match_context(self, point: QPoint):
        global_pos = self.assign_pit_ignored_teams.mapToGlobal(point)

        menu = QMenu()
        menu.addAction("Delete", self.assign_match_context_delete)

        menu.exec(global_pos)

    def assign_pit_context_delete(self):
        for _ in range(len(self.assign_pit_ignored_teams.selectedItems())):
            self.assign_pit_ignored_teams.takeItem(
                self.assign_pit_ignored_teams.currentRow()
            )

    def assign_pit_context_insert(self):
        # ask for team number
        team_number, okPressed = QInputDialog.getInt(
            self,
            "Team Number",
            "Enter a valid team number"
        )
        if okPressed:
            item = QListWidgetItem(f"Team {team_number}")
            item.setData(Qt.ItemDataRole.UserRole, [team_number])
            self.assign_pit_ignored_teams.addItem(item)

    def assign_match_context_delete(self):
        for _ in range(len(self.assign_match_ignored_teams.selectedItems())):
            self.assign_match_ignored_teams.takeItem(
                self.assign_match_ignored_teams.currentRow()
            )

    def assign_pit_generate_worker(self):
        text, okPressed = QInputDialog.getText(
            self,
            "Event Code",
            "Enter a valid TBA-format event code",
            QLineEdit.EchoMode.Normal,
            "",
        )
        if okPressed and text.strip() != "":
            self.worker_thread = QThread()

            self.api_worker = PitTeamWorker(self.sbapi, text)
            self.api_worker.finished.connect(self.on_pit_generate_statbotics)
            self.api_worker.on_error.connect(self.on_api_error)
            self.api_worker.moveToThread(self.worker_thread)
            self.worker_thread.started.connect(self.api_worker.run)

            self.api_worker.finished.connect(self.worker_thread.quit)

            self.worker_thread.start()
        else:
            QMessageBox.critical(self, "Error", "Please enter a code")

    def assign_match_generate_worker(self):
        text, okPressed = QInputDialog.getText(
            self,
            "Event Code",
            "Enter a valid TBA-format event code",
            QLineEdit.EchoMode.Normal,
            "",
        )
        if okPressed and text.strip() != "":
            self.worker_thread = QThread()

            self.api_worker = MatchMatchWorker(self.sbapi, text)
            self.api_worker.finished.connect(self.on_match_generate_statbotics)
            self.api_worker.pit_teams.connect(self.on_pit_teams)
            self.api_worker.on_error.connect(self.on_api_error)
            self.api_worker.moveToThread(self.worker_thread)
            self.worker_thread.started.connect(self.api_worker.run)

            self.api_worker.finished.connect(self.worker_thread.quit)

            self.worker_thread.start()
        else:
            QMessageBox.critical(self, "Error", "Please enter a code")

    def on_pit_generate_statbotics(self, data: list):
        self.assign_pit_ignored_teams.clear()

        for team in data:
            item = QListWidgetItem(str(team["team"]))
            item.setData(
                Qt.ItemDataRole.UserRole, [int(team["team"]), team["team_name"]]
            )
            self.assign_pit_ignored_teams.addItem(item)

            app.processEvents()

    def on_match_generate_statbotics(self, matches: list):
        converted_matches = []

        for match in [
            matches[i] for i in range(len(matches)) if i == matches.index(matches[i])
        ]:
            if not match["playoff"]:
                match_number = match["match_number"]

                # Red Teams
                for i in range(1, 4):
                    team_number = match[f"red_{i}"]
                    converted_matches.append(
                        {
                            "match": match_number,
                            "teamNumber": team_number,
                            "alliance": 0,
                            "position": i - 1,
                        }
                    )

                # Blue Teams
                for i in range(1, 4):
                    team_number = match[f"blue_{i}"]
                    converted_matches.append(
                        {
                            "match": match_number,
                            "teamNumber": team_number,
                            "alliance": 1,
                            "position": i - 1,
                        }
                    )

        for session in converted_matches:
            item = QListWidgetItem()
            item.setText(
                f"Team: {session['teamNumber']} | Match: {session['match']} | Alliance: {session['alliance']} | Position: {session['position']}"
            )
            item.setData(Qt.ItemDataRole.UserRole, session)
            self.assign_match_ignored_teams.addItem(item)

            app.processEvents()

    def on_pit_teams(self, teams: list):
        self.assign_match_pit_teams = teams

    def closeEvent(self, event: QCloseEvent) -> None:
        """
        Application close event

        Args:
            a0 (QCloseEvent | None): Qt close event
        """
        self.serial.close()
        event.accept()


if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)

    app = QApplication(sys.argv)
    app.setWindowIcon(QIcon("icons/mercs.png"))
    app.setApplicationVersion(__version__)
    app.setApplicationName("6369 Scouting Data Transfer")

    settings = QSettings("Mercs", "ScoutingDataTransfer")
    with open("style.qss", "r", encoding="utf-8") as file:
        qdarktheme.setup_theme(additional_qss=file.read(), custom_colors={
        "[dark]": {
            "primary": "#FFB3A9"
        }
    })
    qtawesome.dark(app)
    win = MainWindow()
    sys.exit(app.exec())
