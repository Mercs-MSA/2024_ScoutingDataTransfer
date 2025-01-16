"""
6369 Scouting Data Transfer
Transfer data form scouting tablets using qr code scanner
"""

import base64
from functools import partial
import json
from pathlib import Path
import sys
import os
import logging
import typing

from PySide6.QtWidgets import (
    QApplication,
    QMainWindow,
    QHBoxLayout,
    QVBoxLayout,
    QWidget,
    QFrame,
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
    QMenu,
    QSizePolicy,
    QScrollArea,
)
from PySide6.QtCore import (
    QSettings,
    QSize,
    QIODevice,
    Qt,
    Signal,
    QObject,
    QModelIndex,
    QThread,
    QBuffer,
    QByteArray,
)
from PySide6.QtGui import QCloseEvent, QPixmap, QIcon, QCursor, QAction, QFont, QImage
from PySide6.QtSerialPort import QSerialPort, QSerialPortInfo
import qdarktheme
import qtawesome

import statbotics

import assigner
import data_manager
import data_models
import constants
import utils
import widgets
import jinja2

import wizards

__version__: typing.Final = "2025.0.0-b0"

settings: QSettings | None = None
win: QMainWindow | None = None


class DataWorker(QObject):
    finished = Signal(str)
    on_data_error = Signal(constants.DataError)

    def __init__(self, data: str, savedir: str) -> None:
        super().__init__()
        self.data = data
        self.savedir = savedir

    def run(
        self,
        database: data_manager.DataManager,
    ):
        data = list(utils.convert_types(self.data.strip("\r\n").split("||")))
        form = data[0]
        logging.info("Data transfer started on form %s", str(form))

        header = list(constants.FIELDS[form].keys())

        formatted_data = {}
        for field, value in zip(header, data):
            formatted_data[field] = value

        clean_data = database.get_data(form)
        for row in clean_data:
            row.pop("rowid")
            row.pop("timestamp")

        if formatted_data in clean_data:
            if (
                not self.on_repeated_data(form, formatted_data["team"])
                == QMessageBox.StandardButton.Yes
            ):
                self.finished.emit(form)
                return

        database.add_data(formatted_data)
        self.finished.emit(form)

        # logging.info("transfering data to %s", directory)

        # create directory structure
        # if not os.path.exists(directory):
        #     msg = QMessageBox(win)
        #     msg.setIcon(QMessageBox.Icon.Critical)
        #     msg.setText(f"Directory {directory}\ndoes not exist\nData import cancelled")
        #     msg.setWindowTitle("Data Error")
        #     msg.setStandardButtons(QMessageBox.StandardButton.Ok)
        #     msg.exec()
        #     return
        # for form in data_frames:
        #     if not os.path.exists(os.path.join(directory, form)):
        #         os.mkdir(os.path.join(directory, form))

        #     data_frames[form].to_csv(
        #         os.path.join(directory, form, f"{event_id}_{form}_total.csv"),
        #         index=False,
        #     )
        # TODO: Implement csv export

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


class MainWindow(QMainWindow):
    """Main Window"""

    HOME_IDX, ASSIGN_IDX, PICTURES_IDX, SETTINGS_IDX, ABOUT_IDX = range(5)

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

        self.data_worker = None
        self.api_worker = None
        self.worker_thread = None

        self.is_scanning = False

        db_name: str | None = None
        if settings:
            if settings.contains("sqliteFile"):
                db_name = settings.value("sqliteFile", type=str)  # type: ignore

        self.database = data_manager.DataManager()
        self.database.on_message.connect(self.on_database_error)
        self.database.on_data_updated.connect(self.on_database_update)
        if db_name:
            logging.info(f"Loading db at: {db_name}")
            self.database.connect_db_sqlite(database_name=db_name)
            self.database.initialize()
            for name, fields in constants.FIELDS.items():
                self.database.set_fields(name, fields)

        self.data_buffer = ""  # data may come in split up

        self.root_widget = QWidget()
        self.setCentralWidget(self.root_widget)

        self.root_layout = QHBoxLayout()
        self.root_widget.setLayout(self.root_layout)

        # App navigation

        self.nav_layout = QVBoxLayout()
        self.root_layout.addLayout(self.nav_layout)

        self.navigation_buttons: list[QToolButton] = []
        
        self.nav_layout.addStretch()

        self.nav_button_home = QToolButton()
        self.nav_button_home.setCheckable(True)
        self.nav_button_home.setSizePolicy(
            QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Minimum
        )
        self.nav_button_home.setText("Home")
        self.nav_button_home.setToolButtonStyle(
            Qt.ToolButtonStyle.ToolButtonTextUnderIcon
        )
        self.nav_button_home.setIconSize(QSize(40, 40))
        self.nav_button_home.setIcon(qtawesome.icon("mdi6.home"))
        self.nav_button_home.setChecked(True)
        self.nav_button_home.clicked.connect(lambda: self.nav(self.HOME_IDX))
        self.nav_layout.addWidget(self.nav_button_home)
        self.navigation_buttons.append(self.nav_button_home)

        self.nav_layout.addStretch()

        self.nav_button_assign = QToolButton()
        self.nav_button_assign.setCheckable(True)
        self.nav_button_assign.setSizePolicy(
            QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Minimum
        )
        self.nav_button_assign.setText("Assign")
        self.nav_button_assign.setToolButtonStyle(
            Qt.ToolButtonStyle.ToolButtonTextUnderIcon
        )
        self.nav_button_assign.setIconSize(QSize(40, 40))
        self.nav_button_assign.setIcon(qtawesome.icon("mdi6.clipboard-list"))
        self.nav_button_assign.setToolButtonStyle(
            Qt.ToolButtonStyle.ToolButtonTextUnderIcon
        )
        self.nav_button_assign.clicked.connect(lambda: self.nav(self.ASSIGN_IDX))
        self.nav_layout.addWidget(self.nav_button_assign)
        self.navigation_buttons.append(self.nav_button_assign)

        self.nav_layout.addStretch()

        self.nav_button_pictures = QToolButton()
        self.nav_button_pictures.setCheckable(True)
        self.nav_button_pictures.setSizePolicy(
            QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Minimum
        )
        self.nav_button_pictures.setText("Pictures")
        self.nav_button_pictures.setToolButtonStyle(
            Qt.ToolButtonStyle.ToolButtonTextUnderIcon
        )
        self.nav_button_pictures.setIconSize(QSize(40, 40))
        self.nav_button_pictures.setIcon(qtawesome.icon("mdi6.camera"))
        self.nav_button_pictures.setToolButtonStyle(
            Qt.ToolButtonStyle.ToolButtonTextUnderIcon
        )
        self.nav_button_pictures.clicked.connect(lambda: self.nav(self.PICTURES_IDX))
        self.nav_layout.addWidget(self.nav_button_pictures)
        self.navigation_buttons.append(self.nav_button_pictures)

        self.nav_layout.addStretch()

        self.nav_button_settings = QToolButton()
        self.nav_button_settings.setCheckable(True)
        self.nav_button_settings.setSizePolicy(
            QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Minimum
        )
        self.nav_button_settings.setText("Settings")
        self.nav_button_settings.setToolButtonStyle(
            Qt.ToolButtonStyle.ToolButtonTextUnderIcon
        )
        self.nav_button_settings.setIconSize(QSize(40, 40))
        self.nav_button_settings.setIcon(qtawesome.icon("mdi6.cog"))
        self.nav_button_settings.setToolButtonStyle(
            Qt.ToolButtonStyle.ToolButtonTextUnderIcon
        )
        self.nav_button_settings.clicked.connect(lambda: self.nav(self.SETTINGS_IDX))
        self.nav_layout.addWidget(self.nav_button_settings)
        self.navigation_buttons.append(self.nav_button_settings)

        self.nav_layout.addStretch()

        self.nav_button_about = QToolButton()
        self.nav_button_about.setCheckable(True)
        self.nav_button_about.setSizePolicy(
            QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Minimum
        )
        self.nav_button_about.setText("About")
        self.nav_button_about.setToolButtonStyle(
            Qt.ToolButtonStyle.ToolButtonTextUnderIcon
        )
        self.nav_button_about.setIconSize(QSize(40, 40))
        self.nav_button_about.setIcon(qtawesome.icon("mdi6.information"))
        self.nav_button_about.setToolButtonStyle(
            Qt.ToolButtonStyle.ToolButtonTextUnderIcon
        )
        self.nav_button_about.clicked.connect(lambda: self.nav(self.ABOUT_IDX))
        self.nav_layout.addWidget(self.nav_button_about)
        self.navigation_buttons.append(self.nav_button_about)

        self.nav_layout.addStretch()

        self.app_widget = QStackedWidget()
        self.root_layout.addWidget(self.app_widget)

        # * HOME * #

        self.home_widget = QWidget()
        self.app_widget.insertWidget(self.HOME_IDX, self.home_widget)

        self.home_layout = QVBoxLayout()
        self.home_widget.setLayout(self.home_layout)

        # Scan manager
        self.scanner_widget = QWidget()
        self.home_layout.addWidget(self.scanner_widget)

        self.scanner_layout = QHBoxLayout()
        self.scanner_widget.setLayout(self.scanner_layout)

        self.scanner_layout.addStretch()

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

        self.connection_icon = qtawesome.IconWidget()
        self.connection_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.connection_icon.setIconSize(QSize(72, 72))
        self.connection_icon.setIcon(qtawesome.icon("mdi6.serial-port"))
        self.scanner_layout.addWidget(self.connection_icon)

        self.scanner_layout.addStretch()

        self.hline = QFrame()
        self.hline.setFrameShape(QFrame.Shape.HLine)
        self.home_layout.addWidget(self.hline)

        # Data manager (left side)
        self.data_view_tabs = QTabWidget()
        self.home_layout.addWidget(self.data_view_tabs)

        self.data_models: list[data_models.ScoutingFormModel] = []
        self.data_viewers: dict[str, QTableView] = {}
        self.data_sidebars: dict[str, widgets.Sidebar] = {}

        def table_data_edit(form: str, topl: QModelIndex, _: QModelIndex, __: list):
            # ensure that the new data can be saved with the same type

            self.database.update_data(
                form,
                topl.siblingAtColumn(0).data(),
                list(constants.FIELDS[form].keys())[topl.column() - 2],
                topl.model().data(topl, Qt.ItemDataRole.EditRole),
            )
            logging.debug(
                f"Data updated: {form}, {topl.row()}, {list(constants.FIELDS[form].keys())[topl.column()-2]}, {topl.model().data(topl, Qt.ItemDataRole.EditRole)}"
            )
            self.reload_sidebars()

        def table_menu(
            form: str, model: data_models.ScoutingFormModel, table: QTableView
        ):
            if table.selectedIndexes():
                menu = QMenu(self)

                delete_action = QAction("Delete Row", self)
                delete_action.triggered.connect(
                    lambda: self.delete_db_row(
                        form,
                        table.selectionModel()
                        .selectedRows()[0]
                        .siblingAtColumn(0)
                        .data(),
                        model,
                    )
                    if QMessageBox.question(
                        self,
                        "Delete Row",
                        f"Are you sure you want to delete ID {table.selectionModel().selectedRows()[0].siblingAtColumn(0).data()}?",
                    )
                    == QMessageBox.StandardButton.Yes
                    else None
                )

                deselect_action = QAction("Deselect Row", self)
                deselect_action.triggered.connect(
                    lambda: table.selectionModel().clearSelection()
                )

                menu.addAction(delete_action)
                menu.addAction(deselect_action)

                menu.popup(QCursor.pos())

        def selection_change(
            root,
            form: str,
            table: QTableView,
            sidebar: widgets.Sidebar,
            selected,
            deselected,
        ):
            root(selected, deselected)

            if len(table.selectionModel().selectedRows()) == 0:
                sidebar.set_selected(False)
                return
            sidebar.set_selected(True)
            self.reload_sidebars()

        for form in constants.FIELDS.keys():
            model = data_models.ScoutingFormModel(
                self.database.get_data(form),
                list(constants.FIELDS[form].keys()),
                list(constants.FIELDS[form].values()),
                form,
                self,
            )
            self.data_models.append(model)

            view_widget = QWidget()
            self.data_view_tabs.addTab(view_widget, form.capitalize())

            view_layout = QVBoxLayout()
            view_layout.setContentsMargins(0, 0, 0, 0)
            view_widget.setLayout(view_layout)

            view_bar = QHBoxLayout()
            view_layout.addLayout(view_bar)

            view_bar.addStretch()

            view_export = QToolButton()
            view_export.setText("Export CSV")
            view_export.setIcon(qtawesome.icon("mdi6.microsoft-excel"))
            view_export.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
            view_export.setIconSize(QSize(28, 28))
            view_export.setFixedHeight(32)
            view_export.clicked.connect(lambda: self.export_csv(form))
            view_bar.addWidget(view_export)

            view_side_by_side = QHBoxLayout()
            view_layout.addLayout(view_side_by_side)

            view = QTableView()
            view.setAlternatingRowColors(True)
            view.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
            view.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
            view.setModel(model)
            view.setHorizontalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)

            view.dataChanged = lambda *args, **kwargs: table_data_edit(
                form, *args, **kwargs
            )

            view.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
            view.customContextMenuRequested.connect(
                lambda: table_menu(form, model, view)
            )
            view_side_by_side.addWidget(view)

            sidebar = widgets.Sidebar()
            sidebar.close_action.connect(partial(view.clearSelection))
            sidebar.edit_images_action.connect(self.edit_pictures)
            view_side_by_side.addWidget(sidebar)
            self.data_sidebars[form] = sidebar
            old = view.selectionChanged
            view.selectionChanged = lambda selected, deselected: selection_change(
                old, form, view, sidebar, selected, deselected
            )

            self.data_viewers[form] = view

        # * ASSIGN * #
        self.app_widget.insertWidget(
            self.ASSIGN_IDX, assigner.AssignerWidget(app, self.sbapi)
        )

        # * PICTURES * #
        self.pictures_widget = QWidget()
        self.app_widget.insertWidget(self.PICTURES_IDX, self.pictures_widget)

        self.pictures_layout = QHBoxLayout()
        self.pictures_widget.setLayout(self.pictures_layout)

        self.pictures_left_pane = QFrame()
        self.pictures_left_pane.setFrameShape(QFrame.Shape.Box)
        self.pictures_layout.addWidget(self.pictures_left_pane)

        self.pictures_left_layout = QVBoxLayout()
        self.pictures_left_pane.setLayout(self.pictures_left_layout)

        self.pictures_topbar = QHBoxLayout()
        self.pictures_left_layout.addLayout(self.pictures_topbar)

        self.pictures_add = QPushButton("Add")
        self.pictures_add.setIcon(qtawesome.icon("mdi6.plus"))
        self.pictures_add.setIconSize(QSize(24, 24))
        self.pictures_add.clicked.connect(self.add_new_picture_team)
        self.pictures_topbar.addWidget(self.pictures_add)

        self.pictures_load = QPushButton("Load")
        self.pictures_load.setIcon(qtawesome.icon("mdi6.folder-open"))
        self.pictures_load.setIconSize(QSize(24, 24))
        self.pictures_topbar.addWidget(self.pictures_load)

        self.pictures_topbar.addStretch()

        self.pictures_team_scroll = QScrollArea()
        self.pictures_team_scroll.setWidgetResizable(True)
        self.pictures_team_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.pictures_left_layout.addWidget(self.pictures_team_scroll)

        self.pictures_scroll_widget = QWidget()
        self.pictures_team_scroll.setWidget(self.pictures_scroll_widget)

        self.pictures_scroll_layout = QVBoxLayout()
        self.pictures_scroll_widget.setLayout(self.pictures_scroll_layout)

        for entry in self.database.get_data("robot_pictures"):
            entry_widget = widgets.TeamEntryWidget(entry["team"])
            entry_widget.clicked.connect(self.load_team_pictures_panel)
            self.pictures_scroll_layout.addWidget(entry_widget)

        self.pictures_right_pane = QStackedWidget()
        self.pictures_right_pane.setFrameShape(QFrame.Shape.Box)
        self.pictures_layout.addWidget(self.pictures_right_pane)

        self.pictures_right_unselected_widget = QWidget()
        self.pictures_right_pane.insertWidget(0, self.pictures_right_unselected_widget)

        self.pictures_right_unselected_layout = QVBoxLayout()
        self.pictures_right_unselected_widget.setLayout(
            self.pictures_right_unselected_layout
        )

        self.pictures_right_unselected_layout.addWidget(
            QLabel("Select a team to view pictures"),
            alignment=Qt.AlignmentFlag.AlignCenter,
        )

        self.pictures_right_scroll = QScrollArea()
        self.pictures_right_scroll.setWidgetResizable(True)
        self.pictures_right_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.pictures_right_pane.insertWidget(1, self.pictures_right_scroll)

        self.pictures_right_scroll_widget = QWidget()
        self.pictures_right_scroll.setWidget(self.pictures_right_scroll_widget)

        self.pictures_right_scroll_layout = QVBoxLayout()
        self.pictures_right_scroll_widget.setLayout(self.pictures_right_scroll_layout)

        self.pictures_right_team_label = QLabel("Team 0000")
        self.pictures_right_team_label.setFont(
            QFont(self.pictures_right_team_label.font().family(), 22, QFont.Weight.Bold)
        )
        self.pictures_right_scroll_layout.addWidget(self.pictures_right_team_label)

        # * SETTINGS * #
        self.settings_widget = QWidget()
        self.app_widget.insertWidget(self.SETTINGS_IDX, self.settings_widget)

        self.settings_layout = QVBoxLayout()
        self.settings_widget.setLayout(self.settings_layout)

        self.settings_data_box = QGroupBox("Data")
        self.settings_layout.addWidget(self.settings_data_box)

        self.data_layout = QVBoxLayout()
        self.settings_data_box.setLayout(self.data_layout)

        self.csv_dir_label = QLabel("CSV Auto-Export Directory")
        self.data_layout.addWidget(self.csv_dir_label)

        self.csv_dir_layout = QHBoxLayout()
        self.data_layout.addLayout(self.csv_dir_layout)

        self.csv_dir_textbox = QLineEdit()

        if settings.contains("csvDir"):
            self.csv_dir_textbox.setText(settings.value("csvDir"))

        self.csv_dir_textbox.textChanged.connect(self.update_csv_dir)
        self.csv_dir_layout.addWidget(self.csv_dir_textbox)

        self.csv_dir_picker = QPushButton("Pick Dir")
        self.csv_dir_picker.clicked.connect(self.select_csv_dir)
        self.csv_dir_layout.addWidget(self.csv_dir_picker)

        self.csv_dir_icon = QLabel()
        self.csv_dir_layout.addWidget(self.csv_dir_icon)

        valid = os.path.isdir(self.csv_dir_textbox.text())
        if valid:
            self.csv_dir_icon.setPixmap(
                qtawesome.icon("mdi6.check-circle", color="#4caf50").pixmap(
                    QSize(24, 24)
                )
            )
        else:
            self.csv_dir_icon.setPixmap(
                qtawesome.icon("mdi6.alert", color="#f44336").pixmap(QSize(24, 24))
            )

        self.csv_opts_label = QLabel("CSV Export Options")
        self.data_layout.addWidget(self.csv_opts_label)

        self.csv_opts_layout = QHBoxLayout()
        self.data_layout.addLayout(self.csv_opts_layout)

        self.csv_enable_headers = QCheckBox("Headers")
        self.csv_enable_headers.setToolTip("Save headers with CSV files")
        self.csv_enable_headers.setChecked(
            settings.value("csvHeaders", type=bool, defaultValue=True)
        )  # type: ignore
        self.csv_enable_headers.stateChanged.connect(self.set_csv_enable_headers)
        self.csv_opts_layout.addWidget(self.csv_enable_headers)

        self.csv_enable_auto = QCheckBox("Auto-Export")
        self.csv_enable_auto.setToolTip(
            "Automatically export csv files to the set directory"
        )
        self.csv_enable_auto.setChecked(
            settings.value("csvAutoExport", type=bool, defaultValue=True)
        )  # type: ignore
        self.csv_enable_auto.stateChanged.connect(self.set_csv_auto_export)
        self.csv_opts_layout.addWidget(self.csv_enable_auto)

        self.csv_enable_identifiers = QCheckBox("Identifiers")
        self.csv_enable_identifiers.setToolTip(
            "Include SQL id and timestamps in CSV exports"
        )
        self.csv_enable_identifiers.setChecked(
            settings.value("csvIdentifiers", type=bool, defaultValue=False)
        )  # type: ignore
        self.csv_enable_identifiers.stateChanged.connect(
            self.set_csv_enable_identifiers
        )
        self.csv_opts_layout.addWidget(self.csv_enable_identifiers)

        self.sqlite_file_label = QLabel("SQLite Database Location")
        self.data_layout.addWidget(self.sqlite_file_label)

        self.sqlite_file_layout = QHBoxLayout()
        self.data_layout.addLayout(self.sqlite_file_layout)

        self.sqlite_file_textbox = QLineEdit()
        self.sqlite_file_textbox.setReadOnly(True)
        self.sqlite_file_layout.addWidget(self.sqlite_file_textbox)

        if settings.contains("sqliteFile"):
            self.sqlite_file_textbox.setText(settings.value("sqliteFile"))

        self.sqlite_file_picker = QPushButton("Create DB")
        self.sqlite_file_picker.clicked.connect(self.select_sqlite_file)
        self.sqlite_file_layout.addWidget(self.sqlite_file_picker)

        self.sqlite_file_icon = QLabel()
        self.sqlite_file_layout.addWidget(self.sqlite_file_icon)

        valid = os.path.isfile(self.sqlite_file_textbox.text())
        if valid:
            self.sqlite_file_icon.setPixmap(
                qtawesome.icon("mdi6.check-circle", color="#4caf50").pixmap(
                    QSize(24, 24)
                )
            )
        else:
            self.sqlite_file_icon.setPixmap(
                qtawesome.icon("mdi6.alert", color="#f44336").pixmap(QSize(24, 24))
            )

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
            # noinspection PyTypeChecker
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
            "2024_ScoutingDataCollection</a> using a USB Serial based QR/Barcode scanner."
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
        self.update_serial_ports()

        if settings and settings.contains("touchui"):
            # noinspection PyTypeChecker
            self.set_touch_mode(settings.value("touchui", type=bool))
            # noinspection PyTypeChecker
            self.settings_touchui.setChecked(settings.value("touchui", type=bool))

    def reload_sidebars(self):
            for sidebar in self.data_sidebars:
                rowid = (
                    self.data_viewers[sidebar]
                    .selectionModel()
                    .selectedRows()[0]
                    .siblingAtColumn(0)
                    .data()
                )
                if sidebar == "pit":
                    self.data_sidebars[sidebar].set_team_number(
                        self.data_viewers[sidebar]
                        .selectionModel()
                        .selectedRows()[0]
                        .siblingAtColumn(
                            list(constants.FIELDS[sidebar].keys()).index("team") + 2
                        )
                        .data()
                    )

                template_loader = jinja2.FileSystemLoader("templates")
                template_env = jinja2.Environment(loader=template_loader)

                def include_file(name, *args):
                    """Helper function for jinja2 includes"""
                    return template_env.get_template(name).render(*args)

                template = jinja2.Template(
                    constants.SIDEBAR_CONSTRUCTORS[sidebar],
                    extensions=["jinja2.ext.do"],
                )

                rowdata = {}
                for row in self.database.get_data(sidebar):
                    if row["rowid"] == int(rowid):
                        rowdata = row
                        break

                imbuffer = QBuffer()
                qtawesome.icon("mdi6.alert", color="#ffeb3b").pixmap(
                    QSize(30, 30)
                ).save(imbuffer, "PNG")
                rowdata["warnBase64Icon"] = (
                    f"data:image/png;base64,{imbuffer.data().toBase64().data().decode()}"
                )

                # Add include_file function to template context
                rowdata["include_file"] = lambda *args: include_file(*args, rowdata)

                self.data_sidebars[sidebar].set_html(template.render(rowdata))

                if int(
                    self.data_viewers[sidebar]
                    .selectionModel()
                    .selectedRows()[0]
                    .siblingAtColumn(
                        list(constants.FIELDS[sidebar].keys()).index("team") + 2
                    )
                    .data()
                ) in [x["team"] for x in self.database.get_data("robot_pictures")]:
                    pms = []
                    pics = json.loads(
                        [
                            x
                            for x in self.database.get_data("robot_pictures")
                            if x["team"]
                            == int(
                                self.data_viewers[sidebar]
                                .selectionModel()
                                .selectedRows()[0]
                                .siblingAtColumn(
                                    list(constants.FIELDS[sidebar].keys()).index("team")
                                    + 2
                                )
                                .data()
                            )
                        ][0]["picture"]
                    )["picture"]
                    for x in pics:
                        pm = QPixmap()
                        pm.loadFromData(
                            base64.b64decode(x.replace("data:image/png;base64,", ""))
                        )
                        pms.append(pm)

                    self.data_sidebars[sidebar].set_pixmaps(pms)
                else:
                    self.data_sidebars[sidebar].set_pixmaps(
                        [QPixmap("icons/generic_robot.png")]
                    )


    def edit_pictures(self, team: int):
        self.nav(self.PICTURES_IDX)
        self.load_team_pictures_panel(team)

    def load_team_pictures_panel(self, team: int | str):
        if int(team) in [x["team"] for x in self.database.get_data("robot_pictures")]:
            self.pictures_right_pane.setCurrentIndex(1)
            self.pictures_right_team_label.setText(f"Team {team}")
        else:
            self.add_new_picture_team()

    def add_new_picture_team(self):
        self.pictures_right_pane.setCurrentIndex(0)
        wizard = wizards.NewPicturesTeamWizard(self)
        if not wizard.exec():
            return
        
        team = int(wizard.get_team_number())
        pixmaps = wizard.get_pixmaps()

        blobs = []
        for pixmap in pixmaps:
            buffer = QBuffer()
            pixmap.save(buffer, "PNG")
            blobs.append(
                f"data:image/png;base64,{buffer.data().toBase64().data().decode()}"
            )

        if int(team) in [x["team"] for x in self.database.get_data("robot_pictures")]:
            QMessageBox.critical(
                self,
                "Team Already Has Pictures",
                f"Team {team} already has pictures",
            )
            return


        self.database.add_robot_pictures(team, blobs)
        self.reload_sidebars()

    def on_database_error(self, msg: str, kind: data_manager.MessageType):
        match kind:
            case data_manager.MessageType.FATAL:
                QMessageBox.critical(self, "Database Fatal Error", msg)
            case data_manager.MessageType.ERROR:
                QMessageBox.warning(self, "Database Error", msg)
            case data_manager.MessageType.WARN:
                QMessageBox.information(self, "Database Warning", msg)

    def on_database_update(self):
        logging.debug("Database Updated")
        if settings.value("csvAutoExport", defaultValue=True, type=bool):
            if not os.path.exists(settings.value("csvDir", type=str)):
                try:
                    os.makedirs(settings.value("csvDir", type=str))
                    logging.info(
                        f"Created directory for auto-export {settings.value('csvDir', type=str)}"
                    )
                except Exception as e:
                    QMessageBox.critical(
                        self,
                        "Error Creating Directory for Auto-Export",
                        f"Could not create directory: {repr(e)}",
                    )
                    logging.error(
                        f"Error creating directory for auto-export: {repr(e)}"
                    )

            for form in constants.FIELDS.keys():
                if not os.path.exists(Path(settings.value("csvDir", type=str), form)):
                    os.mkdir(Path(settings.value("csvDir", type=str), form))
                    logging.info(
                        f"Created directory for auto-export {Path(settings.value('csvDir', type=str), form)}"
                    )
                # save csv
                csv_data = self.database.to_csv(
                    form,
                    headers=settings.value("csvHeaders", type=bool, defaultValue=True),  # type: ignore
                    identifiers=settings.value(
                        "csvIdentifiers", type=bool, defaultValue=False
                    ),  # type: ignore
                )
                with open(
                    Path(settings.value("csvDir", type=str), form) / f"{form}.csv", "w"
                ) as f:
                    f.write(csv_data)
                    logging.info(
                        f"Saved {form} to {Path(settings.value('csvDir', type=str), form, f'{form}.csv')}"
                    )

    def delete_db_row(
        self, form: str, rowid: int, table: data_models.ScoutingFormModel
    ):
        logging.debug(f"Deleted row {rowid} from {form} with rowid {rowid}")
        self.database.delete_row(form, rowid)
        table.load_data(self.database.get_data(form))

    def select_sqlite_file(self):
        filepath, _ = QFileDialog.getSaveFileName(
            self,
            "Select SQLite Database",
            f"scouting-frc-{settings.value('event', defaultValue='unknown')}.sqlite",
            "SQLite Database (*.sqlite)",
            options=QFileDialog.Option.DontConfirmOverwrite,
        )
        if filepath:
            self.sqlite_file_textbox.setText(filepath)
            if settings:
                settings.setValue("sqliteFile", filepath)
            self.database.connect_db_sqlite(filepath)
            self.database.initialize()
            for name, fields in constants.FIELDS.items():
                self.database.set_fields(name, fields)

            for model in self.data_models:
                model.load_data(self.database.get_data(model.form))

            valid = os.path.isfile(filepath)
            if valid:
                self.sqlite_file_icon.setPixmap(
                    qtawesome.icon("mdi6.check-circle", color="#4caf50").pixmap(
                        QSize(24, 24)
                    )
                )
            else:
                self.sqlite_file_icon.setPixmap(
                    qtawesome.icon("mdi6.alert", color="#f44336").pixmap(QSize(24, 24))
                )

    def export_csv(self, form: str):
        csv = self.database.to_csv(
            form,
            headers=settings.value("csvHeaders", type=bool, defaultValue=True),  # type: ignore
            identifiers=settings.value("csvIdentifiers", type=bool, defaultValue=False),  # type: ignore
        )

        filepath, _ = QFileDialog.getSaveFileName(
            self,
            "Export to CSV",
            f"{form}.csv",
            "CSV File (*.csv)",
        )
        if filepath:
            with open(filepath, "w") as file:
                file.write(csv)

    def nav(self, page: int):
        """Navigate to a page in app_widget using buttons"""

        for button in self.navigation_buttons:
            button.setChecked(False)

        self.app_widget.setCurrentIndex(page)
        self.navigation_buttons[page].setChecked(True)

    def set_csv_enable_headers(self, enabled: bool):
        if settings:
            settings.setValue("csvHeaders", enabled)

    def set_csv_auto_export(self, enabled: bool):
        if settings:
            settings.setValue("csvAutoExport", enabled)

    def set_csv_enable_identifiers(self, enabled: bool):
        if settings:
            settings.setValue("csvIdentifiers", enabled)

    def set_touch_mode(self, enabled: bool):
        if enabled:
            self.setStyleSheet(
                "QPushButton { height: 30px; font-size: 14px; }"
                "QToolButton { font-size: 14px; }"
                "QComboBox { height: 38px; }"
                "QLineEdit { height: 36px; }"
                "QCheckBox::indicator { width: 32px; height: 32px; }"
                "QTabBar::tab { font-size: 16px; }"
                "QScrollBar:vertical:handle { width: 20px; }"
                "QScrollBar:horizontal:handle { height: 20px; }"
            )
            for viewport in self.data_viewers.values():
                QScroller.grabGesture(
                    viewport.viewport(),
                    QScroller.ScrollerGestureType.TouchGesture,
                )
        else:
            self.setStyleSheet("")
            for viewport in self.data_viewers.values():
                QScroller.ungrabGesture(
                    viewport.viewport(),
                )

        if settings:
            settings.setValue("touchui", enabled)

    def on_event_changed(self):
        if settings:
            settings.setValue("event", self.event_entry.currentText())

    def select_csv_dir(self) -> None:
        """
        Pick file for transfer directory
        """

        self.csv_dir_textbox.setText(
            str(QFileDialog.getExistingDirectory(self, "Select Directory"))
        )
        if settings:
            settings.setValue("csvDir", self.csv_dir_textbox.text())

    def update_csv_dir(self) -> None:
        """
        Check if transfer dir is valid and set to persistent storage
        """

        valid = os.path.isdir(self.csv_dir_textbox.text())
        if valid:
            self.csv_dir_icon.setPixmap(
                qtawesome.icon("mdi6.check-circle", color="#4caf50").pixmap(
                    QSize(24, 24)
                )
            )
        else:
            self.csv_dir_icon.setPixmap(
                qtawesome.icon("mdi6.alert", color="#f44336").pixmap(QSize(24, 24))
            )
        if settings:
            settings.setValue("csvDir", self.csv_dir_textbox.text())

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

        if self.serial_connect.text() == "Disconnect":
            self.serial.close()
            self.set_serial_options_enabled(True)
            self.connection_icon.setIcon(qtawesome.icon("mdi6.serial-port"))
            self.serial_connect.setText("Connect")

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

        self.serial_connect.setText("Disconnect")

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
        self.data_buffer += bytes(data.data()).decode()
        if self.data_buffer.endswith("\n"):
            self.on_data_retrieved(self.data_buffer)
            self.data_buffer = ""

    def on_data_retrieved(self, data: str):
        if not self.is_scanning:
            self.is_scanning = True

            self.worker_thread = QThread()

            self.data_worker = DataWorker(data, self.csv_dir_textbox.text())
            self.data_worker.finished.connect(self.on_data_transfer_complete)
            self.data_worker.on_data_error.connect(self.on_data_error)
            self.data_worker.moveToThread(self.worker_thread)
            self.worker_thread.started.connect(
                lambda: self.data_worker.run(self.database)
                if self.data_worker
                else None
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

                self.api_worker = assigner.EventCodeWorker(self.sbapi, district)
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
        msg = QMessageBox(self)
        msg.setIcon(QMessageBox.Icon.Critical)
        msg.setText("Error from fetch operation")
        msg.setWindowTitle("API")
        msg.setDetailedText(stack)
        msg.setStandardButtons(QMessageBox.StandardButton.Ok)
        msg.exec()

    def on_data_transfer_complete(self, form: str):
        self.connection_icon.setIcon(
            qtawesome.icon("mdi6.qrcode-scan", color="#03a9f4")
        )

        for model in self.data_models:
            model.load_data(self.database.get_data(model.form))

        self.is_scanning = False

    def show_port_ref_error(self):
        """
        Display a serial port list refresh error
        """
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

    def closeEvent(self, event: QCloseEvent) -> None:
        """
        Application close event

        Args:
            event (QCloseEvent | None): Qt close event
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
        qdarktheme.setup_theme(
            additional_qss=file.read(), custom_colors=constants.CUSTOM_COLORS_DARK
        )
    qtawesome.dark(app)
    win = MainWindow()
    sys.exit(app.exec())
