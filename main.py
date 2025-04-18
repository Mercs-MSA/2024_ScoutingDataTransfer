"""
6369 Scouting Data Transfer
Transfer data form scouting tablets using qr code scanner
"""

import pybase64 as base64
from functools import partial
import hashlib
import io
import json
from pathlib import Path
import sys
import os
from loguru import logger
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
    QListWidget,
    QListWidgetItem,
    QSplitter,
    QProgressDialog,
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
    QUrl,
)
from PySide6.QtGui import (
    QCloseEvent,
    QPixmap,
    QIcon,
    QCursor,
    QAction,
    QFont,
    QImage,
    QDesktopServices,
)
from PySide6.QtSerialPort import QSerialPort, QSerialPortInfo
import qdarktheme
import qtawesome

from PIL import Image
from pillow_heif import register_heif_opener

import statbotics

import minify_html

import assigner
import data_manager
import data_models
import constants
import installer
import nav
import utils
import viewer
import widgets
import wizards
from utils import report_versions

import jinja2

__version__: typing.Final = "2025.4.1-worldsfix"

settings: QSettings | None = None
win: QMainWindow | None = None

register_heif_opener()  # add support for heif images


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
        data = list(
            utils.convert_types(
                self.data.strip("\r\n").split(constants.SCANNER_DELIMITER)
            )
        )
        form = data[0]
        logger.info(f"Data transfer started on form {form}")

        if form not in constants.FIELDS:
            logger.error(f"Unknown form: {form}")
            self.on_data_error.emit(constants.DataError.UNKNOWN_FORM)
            self.finished.emit(form)
            return

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

        if len(formatted_data) != len(header):
            logger.error(
                f"Data length mismatch: {len(formatted_data)} != {len(header)}"
            )
            self.on_data_error.emit(constants.DataError.LENGTH_MISMATCH)
            self.finished.emit(form)
            return

        database.add_data(formatted_data)
        self.finished.emit(form)

    def on_repeated_data(self, form: str, team: int):
        """
        Display a warning for importing a repeat
        """

        logger.warning(f"Attempting to import repeated data team number: {team}")

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


class ReportWorker(QObject):
    finished = Signal(str)
    progress = Signal(int)

    def __init__(
        self,
        form,
        rowid,
        team,
        event,
        database,
        filepath,
        include_pictures: bool = False,
    ):
        super().__init__()
        self.form = form
        self.rowid = rowid
        self.team = team
        self.eventcode = event
        self.database = database
        self.filepath = filepath
        self.include_pictures = include_pictures

    def run(self):
        # generate template
        template_loader = jinja2.FileSystemLoader("templates")
        template_env = jinja2.Environment(loader=template_loader)

        def include_file(name, *args):
            """Helper function for jinja2 includes"""
            return template_env.get_template(name).render(*args)

        template = jinja2.Template(
            constants.REPORT_CONSTRUCTORS[self.form],
            extensions=["jinja2.ext.do"],
        )

        rowdata = {}
        for row in self.database.get_data(self.form):
            if row["rowid"] == int(self.rowid):
                rowdata = row
                break

        imbuffer = QBuffer()
        qtawesome.icon("mdi6.alert", color="#ffeb3b").pixmap(QSize(30, 30)).save(
            imbuffer, "PNG"
        )
        rowdata["warnBase64Icon"] = (
            f"data:image/png;base64,{imbuffer.data().toBase64().data().decode()}"
        )

        imbuffer = QBuffer()
        qtawesome.icon("mdi6.close-thick", color="#f44336").pixmap(QSize(30, 30)).save(
            imbuffer, "PNG"
        )
        rowdata["xBase64Icon"] = (
            f"data:image/png;base64,{imbuffer.data().toBase64().data().decode()}"
        )

        imbuffer = QBuffer()
        qtawesome.icon("mdi6.check-bold", color="#8bc34a").pixmap(QSize(30, 30)).save(
            imbuffer, "PNG"
        )
        rowdata["checkBase64Icon"] = (
            f"data:image/png;base64,{imbuffer.data().toBase64().data().decode()}"
        )

        imbuffer = QBuffer()
        QPixmap("icons/logo16.png").save(imbuffer, "PNG")
        rowdata["logo16Base64"] = (
            f"data:image/png;base64,{imbuffer.data().toBase64().data().decode()}"
        )

        imbuffer = QBuffer()
        qtawesome.icon("mdi6.close", color="#ffffff").pixmap(QSize(30, 30)).save(
            imbuffer, "PNG"
        )
        rowdata["closeBase64Icon"] = (
            f"data:image/png;base64,{imbuffer.data().toBase64().data().decode()}"
        )

        # Add include_file function to template context
        rowdata["include_file"] = lambda *args: include_file(*args, rowdata)

        # Add event code
        if "event" not in rowdata:
            rowdata["event"] = self.eventcode

        rowdata["generator"] = "report"

        # add images
        if self.include_pictures:
            imagedata = self.database.get_data("robot_pictures")
            rowdata["images"] = []
            # get by team
            for image in imagedata:
                if image["team"] == int(self.team):
                    data = json.loads(image["picture"])
                    for pic in data["picture"]:
                        rowdata["images"].append(pic)
                        logger.debug(
                            f"Added image to report with MD5 - {hashlib.md5(pic.encode()).hexdigest()}"
                        )

        if self.filepath:
            with open(self.filepath, "w") as file:
                file.write(
                    minify_html.minify(
                        template.render(rowdata), minify_js=True, minify_css=True
                    )
                )
        else:
            self.finished.emit("")
            return

        self.finished.emit(self.filepath)


class MainWindow(QMainWindow):
    """Main Window"""

    HOME_IDX, ASSIGN_IDX, APPMGMT_IDX, PICTURES_IDX, SETTINGS_IDX, ABOUT_IDX = range(6)

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
        self.progress_dialog: QProgressDialog | None = None

        self.is_scanning = False

        self.image_viewer: viewer.ImageViewer | None = None

        db_name: str | None = None
        if settings:
            if settings.contains("sqliteFile"):
                db_name = settings.value("sqliteFile", type=str)  # type: ignore

        self.database = data_manager.DataManager()
        self.database.on_message.connect(self.on_database_error)
        self.database.on_data_updated.connect(self.on_database_update)
        if db_name:
            logger.info(f"Loading db at: {db_name}")
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
        if constants.ENABLE_ASSIGNMENT_GENERATOR:
            self.nav_layout.addWidget(self.nav_button_assign)
            self.nav_layout.addStretch()
        self.navigation_buttons.append(self.nav_button_assign)

        self.nav_button_appmgmt = QToolButton()
        self.nav_button_appmgmt.setCheckable(True)
        self.nav_button_appmgmt.setSizePolicy(
            QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Minimum
        )
        self.nav_button_appmgmt.setText("Tablet\nAppMgmt")
        self.nav_button_appmgmt.setToolButtonStyle(
            Qt.ToolButtonStyle.ToolButtonTextUnderIcon
        )
        self.nav_button_appmgmt.setIconSize(QSize(40, 40))
        self.nav_button_appmgmt.setIcon(qtawesome.icon("mdi6.application-export"))
        self.nav_button_appmgmt.setToolButtonStyle(
            Qt.ToolButtonStyle.ToolButtonTextUnderIcon
        )
        self.nav_button_appmgmt.clicked.connect(lambda: self.nav(self.APPMGMT_IDX))
        if constants.ENAGLE_APPMGMT:
            self.nav_layout.addWidget(self.nav_button_appmgmt)
            self.nav_layout.addStretch()
        self.navigation_buttons.append(self.nav_button_appmgmt)

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

        self.home_widget = QSplitter()
        self.home_widget.setOrientation(Qt.Orientation.Vertical)
        self.app_widget.insertWidget(self.HOME_IDX, self.home_widget)

        # Scan manager
        self.scanner_widget = QWidget()
        self.home_widget.addWidget(self.scanner_widget)

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
        self.serial_connect.clicked.connect(self.toggle_connection)
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

        # Data manager (left side)
        self.data_view_tabs = QTabWidget()
        self.home_widget.addWidget(self.data_view_tabs)

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
            logger.debug(
                f"Data updated: {form}, {topl.row()}, {list(constants.FIELDS[form].keys())[topl.column()-2]}, {topl.model().data(topl, Qt.ItemDataRole.EditRole)}"
            )
            self.reload_sidebars()

        def table_menu(
            form: str, model: data_models.ScoutingFormModel, table: QTableView, *_args
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
                        table,
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
            view_export.clicked.connect(partial(self.export_csv, form))
            view_bar.addWidget(view_export)

            view_report = QToolButton()
            view_report.setText("Generate Report")
            view_report.setIcon(qtawesome.icon("mdi6.file-document-multiple-outline"))
            view_report.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
            view_report.setIconSize(QSize(28, 28))
            view_report.setFixedHeight(32)
            view_report.clicked.connect(partial(self.generate_report, form))
            view_bar.addWidget(view_report)

            view_side_by_side = QHBoxLayout()
            view_layout.addLayout(view_side_by_side)

            view = QTableView()
            view.setAlternatingRowColors(True)
            view.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
            view.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
            view.setModel(model)
            view.setHorizontalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)

            view.dataChanged = partial(table_data_edit, form)  # type: ignore

            view.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
            view.customContextMenuRequested.connect(
                partial(table_menu, form, model, view)
            )
            view_side_by_side.addWidget(view, 7)

            sidebar = widgets.Sidebar()
            sidebar.close_action.connect(partial(view.clearSelection))
            sidebar.edit_images_action.connect(self.edit_pictures)
            view_side_by_side.addWidget(sidebar, 3)
            self.data_sidebars[form] = sidebar
            old = view.selectionChanged
            view.selectionChanged = partial(selection_change, old, form, view, sidebar)

            self.data_viewers[form] = view

        # * ASSIGN * #

        if constants.ENABLE_ASSIGNMENT_GENERATOR:
            assign = assigner.AssignerWidget(app, self.sbapi)
            assign.on_api_error.connect(self.on_api_error)
            self.app_widget.insertWidget(self.ASSIGN_IDX, assign)
        else:
            self.app_widget.insertWidget(self.ASSIGN_IDX, QWidget())

        # * AppMgmt * #
        if constants.ENAGLE_APPMGMT:
            self.appmgmt_widget = installer.Downloader()
            self.app_widget.insertWidget(self.APPMGMT_IDX, self.appmgmt_widget)
        else:
            self.app_widget.insertWidget(self.APPMGMT_IDX, QWidget())

        # * PICTURES * #
        self.pictures_widget = QWidget()
        self.app_widget.insertWidget(self.PICTURES_IDX, self.pictures_widget)

        self.pictures_layout = QHBoxLayout()
        self.pictures_widget.setLayout(self.pictures_layout)

        self.pictures_left_pane = QFrame()
        self.pictures_left_pane.setFrameShape(QFrame.Shape.Box)
        self.pictures_layout.addWidget(self.pictures_left_pane, 1)

        self.pictures_left_layout = QVBoxLayout()
        self.pictures_left_pane.setLayout(self.pictures_left_layout)

        self.pictures_topbar = QHBoxLayout()
        self.pictures_left_layout.addLayout(self.pictures_topbar)

        self.pictures_add_team = QPushButton("Add Team")
        self.pictures_add_team.setIcon(qtawesome.icon("mdi6.plus"))
        self.pictures_add_team.setIconSize(QSize(24, 24))
        self.pictures_add_team.clicked.connect(self.add_new_picture_team)
        self.pictures_topbar.addWidget(self.pictures_add_team)

        self.pictures_add = QPushButton("Add Picture")
        self.pictures_add.setIcon(qtawesome.icon("mdi6.plus"))
        self.pictures_add.setIconSize(QSize(24, 24))
        self.pictures_add.clicked.connect(self.add_picture)
        self.pictures_topbar.addWidget(self.pictures_add)

        self.pictures_topbar.addStretch()

        self.pictures_team_browser = nav.TeamExplorerWidget()
        self.pictures_team_browser.team_open.connect(self.load_team_pictures_panel)
        self.pictures_team_browser.team_delete.connect(self.remove_picture_team)
        self.pictures_left_layout.addWidget(self.pictures_team_browser)
        self.reload_picture_teams()

        self.pictures_right_pane = QStackedWidget()
        self.pictures_right_pane.setFrameShape(QFrame.Shape.Box)
        self.pictures_layout.addWidget(self.pictures_right_pane, 3)

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

        self.pictures_right_browser = QFrame()
        self.pictures_right_browser.setFrameShape(QFrame.Shape.NoFrame)
        self.pictures_right_pane.insertWidget(1, self.pictures_right_browser)

        self.pictures_right_scroll_layout = QVBoxLayout()
        self.pictures_right_browser.setLayout(self.pictures_right_scroll_layout)

        self.pictures_right_team_label = QLabel("Team 0000")
        self.pictures_right_team_label.setFont(
            QFont(self.pictures_right_team_label.font().family(), 22, QFont.Weight.Bold)
        )
        self.pictures_right_scroll_layout.addWidget(self.pictures_right_team_label)

        self.pictures_browser_list = QListWidget()
        self.pictures_right_scroll_layout.addWidget(self.pictures_browser_list)
        # large icons
        self.pictures_browser_list.setViewMode(QListWidget.ViewMode.ListMode)
        self.pictures_browser_list.setIconSize(constants.PICTURE_BROWSER_MAX_RESOLUTION)
        self.pictures_browser_list.setMovement(QListWidget.Movement.Static)
        self.pictures_browser_list.setVerticalScrollMode(
            QAbstractItemView.ScrollMode.ScrollPerPixel
        )
        self.pictures_browser_list.setSelectionMode(
            QListWidget.SelectionMode.NoSelection
        )
        self.pictures_browser_list.setMinimumWidth(
            constants.PICTURE_BROWSER_MAX_RESOLUTION.width() + 300
        )
        self.pictures_browser_list.setSpacing(10)

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

        self.settings_report_box = QGroupBox("Report Generation")
        self.settings_layout.addWidget(self.settings_report_box)

        self.report_layout = QVBoxLayout()
        self.settings_report_box.setLayout(self.report_layout)

        self.report_images_checkbox = QCheckBox("Include Images")
        self.report_images_checkbox.setChecked(
            settings.value("reportImages", type=bool, defaultValue=False)
        )
        self.report_images_checkbox.stateChanged.connect(self.set_report_images)
        self.report_layout.addWidget(self.report_images_checkbox)

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
            if len(self.data_viewers[sidebar].selectionModel().selectedRows()) == 0:
                continue
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

            try:
                template_loader = jinja2.FileSystemLoader("templates")
                template_env = jinja2.Environment(loader=template_loader)

                def include_file(name, *args):
                    """Helper function for jinja2 includes"""
                    return template_env.get_template(name).render(*args)

                template = jinja2.Template(
                    constants.SIDEBAR_CONSTRUCTORS[sidebar],
                    extensions=["jinja2.ext.do"],
                )

                rowdata = self.database.get_datapoint(sidebar, int(rowid))
                if not rowdata:
                    return

                imbuffer = QBuffer()
                qtawesome.icon("mdi6.alert", color="#ffeb3b").pixmap(
                    QSize(30, 30)
                ).save(imbuffer, "PNG")
                rowdata["warnBase64Icon"] = (
                    f"data:image/png;base64,{imbuffer.data().toBase64().data().decode()}"
                )

                imbuffer = QBuffer()
                qtawesome.icon("mdi6.close-thick", color="#f44336").pixmap(
                    QSize(30, 30)
                ).save(imbuffer, "PNG")
                rowdata["xBase64Icon"] = (
                    f"data:image/png;base64,{imbuffer.data().toBase64().data().decode()}"
                )

                imbuffer = QBuffer()
                qtawesome.icon("mdi6.check-bold", color="#8bc34a").pixmap(
                    QSize(30, 30)
                ).save(imbuffer, "PNG")
                rowdata["checkBase64Icon"] = (
                    f"data:image/png;base64,{imbuffer.data().toBase64().data().decode()}"
                )

                imbuffer = QBuffer()
                QPixmap("icons/logo16.png").save(imbuffer, "PNG")
                rowdata["logo16Base64"] = (
                    f"data:image/png;base64,{imbuffer.data().toBase64().data().decode()}"
                )

                # Add include_file function to template context
                rowdata["include_file"] = lambda *args: include_file(*args, rowdata)

                # Add event code
                if "event" not in rowdata:
                    rowdata["event"] = self.event_entry.currentText()

                rowdata["generator"] = "sidebar"

                self.data_sidebars[sidebar].set_html(template.render(rowdata))

                data = self.database.get_pictures(
                    self.data_viewers[sidebar]
                    .selectionModel()
                    .selectedRows()[0]
                    .siblingAtColumn(
                        list(constants.FIELDS[sidebar].keys()).index("team") + 2
                    )
                    .data()
                )

                if data:
                    pms = []
                    pics = json.loads(data["picture"])["picture"]
                    for x in pics:
                        pm = QPixmap()
                        pm.loadFromData(base64.b64decode(x.split(",")[1]))
                        pms.append(pm)

                    self.data_sidebars[sidebar].set_pixmaps(pms)
                else:
                    self.data_sidebars[sidebar].set_pixmaps(
                        [QPixmap("icons/generic_robot.png")]
                    )
            except (
                jinja2.exceptions.TemplateSyntaxError,
                jinja2.exceptions.TemplatesNotFound,
                jinja2.exceptions.TemplateError,
            ) as e:
                self.data_sidebars[sidebar].set_html("Failure to load template!")
                logger.error(f"Failed to load template; {repr(e)}")

    def reload_picture_teams(self):
        self.pictures_team_browser.clear_teams()
        for entry in self.database.get_data("robot_pictures"):
            self.pictures_team_browser.add_team(
                str(entry["team"]), qtawesome.icon("mdi6.robot"), entry["team"]
            )

    def edit_pictures(self, team: int):
        self.nav(self.PICTURES_IDX)
        self.load_team_pictures_panel(team)

    def load_team_pictures_panel(self, team: int | str):
        data = self.database.get_pictures(int(team))
        if not data:
            self.add_new_picture_team()
            return

        self.pictures_right_pane.setCurrentIndex(1)
        self.pictures_right_team_label.setText(f"Team {team}")
        self.pictures_browser_list.clear()
        for image in json.loads(data["picture"])["picture"]:
            # create pixmap from base64
            pixmap = QPixmap()
            pixmap.loadFromData(
                base64.b64decode(image.replace("data:image/png;base64,", ""))
            )
            item = QListWidgetItem()
            item.setSizeHint(
                QSize(300, constants.PICTURE_BROWSER_MAX_RESOLUTION.height() + 20)
            )
            item.setIcon(QIcon(pixmap))

            widget = QWidget()

            layout = QVBoxLayout()
            widget.setLayout(layout)

            top_layout = QHBoxLayout()
            layout.addLayout(top_layout)

            image_text = QLabel(f"Robot Image\nTeam {team}")
            image_text.setAlignment(Qt.AlignmentFlag.AlignCenter)
            top_layout.addWidget(image_text)

            # delete, view buttons
            delete_button = QPushButton("Delete")
            delete_button.clicked.connect(
                partial(self.delete_picture, int(team), image)
            )
            layout.addWidget(delete_button)

            view_button = QPushButton("View")
            view_button.clicked.connect(partial(self.view_image, int(team), image))
            layout.addWidget(view_button)

            self.pictures_browser_list.addItem(item)
            self.pictures_browser_list.setItemWidget(item, widget)

    def view_image(self, team: int | str, data: str):
        team = int(team)

        pixmap = QPixmap()
        pixmap.loadFromData(
            base64.b64decode(data.replace("data:image/png;base64,", ""))
        )

        if self.image_viewer:
            self.image_viewer.close()
        self.image_viewer = viewer.ImageViewer(pixmap, team)
        self.image_viewer.show()

    def delete_picture(self, team: int, base64: str):
        if (
            not QMessageBox.question(
                self,
                "Delete Picture",
                f"Are you sure you want to delete this picture for team {team}?",
                QMessageBox.StandardButton.Yes,
                QMessageBox.StandardButton.No,
            )
            == QMessageBox.StandardButton.Yes
        ):
            return

        data = self.database.get_data("robot_pictures")
        rowid = [x["rowid"] for x in data if x["team"] == team][0]
        pictures = json.loads([x for x in data if x["team"] == team][0]["picture"])[
            "picture"
        ]
        pictures.remove(base64)
        self.database.update_data(
            "robot_pictures", rowid, "picture", json.dumps({"picture": pictures})
        )
        self.load_team_pictures_panel(team)

    def add_picture(self):
        # retrieve selected team
        team = self.pictures_team_browser.get_selected_team()
        if team is None:
            return

        # open file(s) dialog, png, jpg, jpeg, bmp, heic
        files, _ = QFileDialog.getOpenFileNames(
            self,
            "Select Picture(s)",
            "",
            "Images (*.png *.jpg *.jpeg *.bmp *.heic)",
        )

        if not files:
            return

        # load images
        pixmaps = []
        for file in files:
            # convert heic
            if file.lower().endswith(".heic"):
                try:
                    # Open HEIC file with Pillow
                    heic_image = Image.open(file)

                    # Convert to RGB (HEIC might be in a different color space)
                    rgb_image = heic_image.convert("RGB")

                    # Convert PIL Image to bytes
                    buffer = io.BytesIO()
                    rgb_image.save(buffer, format="PNG")
                    buffer.seek(0)

                    # Create QImage from bytes
                    image_data = buffer.getvalue()
                    qimage = QImage.fromData(image_data)
                    pixmap = QPixmap.fromImage(qimage)

                except Exception as e:
                    logger.error(f"Error converting HEIC file: {e}")
                    continue
            else:
                # Handle regular image formats
                pixmap = QPixmap(file)
            pixmaps.append(pixmap)

        # save images to db
        blobs = []
        for pixmap in pixmaps:
            buffer = QBuffer()
            pixmap.scaled(
                constants.PICTURE_SAVE_MAX_RESOLUTION,
                aspectMode=Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                mode=Qt.TransformationMode.SmoothTransformation,
            ).save(buffer, "PNG")
            blobs.append(
                f"data:image/png;base64,{buffer.data().toBase64().data().decode()}"
            )

        data = self.database.get_data("robot_pictures")
        rowid = [x["rowid"] for x in data if x["team"] == team][0]
        pictures = json.loads([x for x in data if x["team"] == team][0]["picture"])[
            "picture"
        ]
        pictures.extend(blobs)
        self.database.update_data(
            "robot_pictures", rowid, "picture", json.dumps({"picture": pictures})
        )

        self.load_team_pictures_panel(team)
        self.reload_sidebars()

    def add_new_picture_team(self):
        self.pictures_right_pane.setCurrentIndex(0)
        existing_teams = [x["team"] for x in self.database.get_data("robot_pictures")]
        wizard = wizards.NewPicturesTeamWizard(existing_teams, self)
        if not wizard.exec():
            return

        team = int(wizard.get_team_number())
        pixmaps = wizard.get_pixmaps()

        blobs = []
        for pixmap in pixmaps:
            buffer = QBuffer()
            pixmap.scaled(
                constants.PICTURE_SAVE_MAX_RESOLUTION,
                aspectMode=Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                mode=Qt.TransformationMode.SmoothTransformation,
            ).save(buffer, "PNG")
            blobs.append(
                f"data:image/png;base64,{buffer.data().toBase64().data().decode()}"
            )

        self.database.add_robot_pictures(team, blobs)
        self.reload_sidebars()
        self.reload_picture_teams()

    def remove_picture_team(self, team: int):
        ret = QMessageBox.question(
            self,
            "Delete Team",
            f"Are you sure you want to delete all pictures for team {team}?",
            QMessageBox.StandardButton.Yes,
            QMessageBox.StandardButton.No,
        )
        if ret == QMessageBox.StandardButton.Yes:
            # find rowid of team
            rowid = [
                x["rowid"]
                for x in self.database.get_data("robot_pictures")
                if x["team"] == team
            ][0]
            self.database.delete_row("robot_pictures", rowid)
            self.reload_sidebars()
            self.reload_picture_teams()

    def on_database_error(self, msg: str, kind: data_manager.MessageType):
        match kind:
            case data_manager.MessageType.FATAL:
                QMessageBox.critical(self, "Database Fatal Error", msg)
            case data_manager.MessageType.ERROR:
                QMessageBox.warning(self, "Database Error", msg)
            case data_manager.MessageType.WARN:
                QMessageBox.information(self, "Database Warning", msg)

    def on_database_update(self):
        logger.debug("Database Updated")
        if settings.value("csvAutoExport", defaultValue=True, type=bool):  # type: ignore
            if not os.path.exists(settings.value("csvDir", type=str)):  # type: ignore
                try:
                    os.makedirs(settings.value("csvDir", type=str))  # type: ignore
                    logger.info(
                        f"Created directory for auto-export {settings.value('csvDir', type=str)}"  # type: ignore
                    )
                except Exception as e:
                    QMessageBox.critical(
                        self,
                        "Error Creating Directory for Auto-Export",
                        f"Could not create directory: {repr(e)}",
                        QMessageBox.StandardButton.Ok,
                        QMessageBox.StandardButton.Ok,
                    )
                    logger.error(f"Error creating directory for auto-export: {repr(e)}")

            try:
                for form in constants.FIELDS.keys():
                    if not os.path.exists(
                        Path(settings.value("csvDir", type=str), form)
                    ):  # type: ignore
                        os.mkdir(Path(settings.value("csvDir", type=str), form))  # type: ignore
                        logger.info(
                            f"Created directory for auto-export {Path(settings.value('csvDir', type=str), form)}"  # type: ignore
                        )
                    # save csv
                    csv_data = self.database.to_csv(
                        form,
                        headers=settings.value(
                            "csvHeaders", type=bool, defaultValue=True
                        ),  # type: ignore
                        identifiers=settings.value(  # type: ignore
                            "csvIdentifiers", type=bool, defaultValue=False
                        ),  # type: ignore
                    )
                    with open(
                        Path(settings.value("csvDir", type=str), form) / f"{form}.csv",
                        "w",  # type: ignore
                    ) as f:
                        f.write(csv_data)
                        logger.info(
                            f"Saved {form} to {Path(settings.value('csvDir', type=str), form, f'{form}.csv')}"  # type: ignore
                        )
            except PermissionError as e:
                QMessageBox.critical(
                    self,
                    "Error Saving CSV",
                    f"Could not save CSV: {repr(e)}",
                    QMessageBox.StandardButton.Ok,
                    QMessageBox.StandardButton.Ok,
                )
                logger.error(f"Error saving CSV: {repr(e)}")

    def delete_db_row(
        self,
        form: str,
        rowid: int,
        table: QTableView,
        model: data_models.ScoutingFormModel,
    ):
        logger.debug(f"Deleting row {rowid} from {form} with rowid {rowid}")
        self.database.delete_row(form, rowid)
        logger.debug(f"Deleted row {rowid} from {form} with rowid {rowid}")
        model.removeRow(table.selectionModel().selectedRows()[0].row())
        logger.debug(
            f"Reloaded table after DEL row {rowid} from {form} with rowid {rowid}"
        )

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

    def generate_report(self, form: str):
        # get selected row
        if len(self.data_viewers[form].selectionModel().selectedRows()) == 0:
            QMessageBox.warning(
                self,
                "No Row Selected",
                "Please select a row to generate a report for",
                QMessageBox.StandardButton.Ok,
                QMessageBox.StandardButton.Ok,
            )
            return

        rowid = (
            self.data_viewers[form]
            .selectionModel()
            .selectedRows()[0]
            .siblingAtColumn(0)
            .data()
        )

        team = (
            self.data_viewers[form]
            .selectionModel()
            .selectedRows()[0]
            .siblingAtColumn(list(constants.FIELDS[form].keys()).index("team") + 2)
            .data()
        )

        if form == "match":
            no_show = int(
                (
                    self.data_viewers[form]
                    .selectionModel()
                    .selectedRows()[0]
                    .siblingAtColumn(
                        list(constants.FIELDS[form].keys()).index("noShow") + 2
                    )
                    .data()
                )
            )
            match = (
                self.data_viewers[form]
                .selectionModel()
                .selectedRows()[0]
                .siblingAtColumn(list(constants.FIELDS[form].keys()).index("match") + 2)
                .data()
            ) + "_"
            if no_show:
                start = "_noShow"
            else:
                start = "_" + (
                    self.data_viewers[form]
                    .selectionModel()
                    .selectedRows()[0]
                    .siblingAtColumn(
                        list(constants.FIELDS[form].keys()).index("startPos") + 2
                    )
                    .data()
                )
        else:
            match = ""
            start = ""

        include_pictures = settings.value("reportImages", type=bool, defaultValue=True)  # type: ignore

        # Create a progress dialog

        filepath, _ = QFileDialog.getSaveFileName(
            None,
            "Export to HTML",
            f"{form}_{match}{team}{start}_{self.event_entry.currentText()}.html",
            "HTML File (*.html)",
        )

        if filepath:
            self.progress_dialog = QProgressDialog(
                "Generating report...", "Cancel", 0, 0, self
            )
            self.progress_dialog.setMinimumDuration(0)
            self.progress_dialog.setValue(0)
            self.progress_dialog.show()

            self.worker_thread = QThread()
            self.data_worker = ReportWorker(
                form,
                rowid,
                team,
                self.event_entry.currentText(),
                self.database,
                filepath,
                include_pictures,
            )
            self.data_worker.finished.connect(self.on_report_finished)
            self.worker_thread.started.connect(self.data_worker.run)
            self.data_worker.moveToThread(self.worker_thread)
            self.data_worker.finished.connect(self.worker_thread.quit)
            self.worker_thread.start()

    def on_report_finished(self, filepath):
        if self.progress_dialog:
            self.progress_dialog.close()
        if filepath:
            if (
                QMessageBox.question(
                    self,
                    "Open Report",
                    "Would you like to open the report in your default browser?",
                    QMessageBox.StandardButton.Yes,
                    QMessageBox.StandardButton.No,
                )
                == QMessageBox.StandardButton.Yes
            ):
                QDesktopServices.openUrl(QUrl.fromLocalFile(filepath))

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
            QScroller.grabGesture(
                self.pictures_browser_list.viewport(),
                QScroller.ScrollerGestureType.TouchGesture,
            )
            QScroller.grabGesture(
                self.pictures_team_browser.list_widget.viewport(),
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

    def set_report_images(self, enabled: bool):
        if settings:
            settings.setValue("reportImages", enabled)

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
        if not settings:
            return

        baud = int(self.serial_baud.currentText())
        self.serial.setBaudRate(baud)
        settings.setValue("baud", baud)

    def change_data_bits(self):
        """
        Set data bits from combo box
        """
        if not settings:
            return

        bits = constants.DATA_BITS[self.serial_bits.currentText()]
        self.serial.setDataBits(bits)
        settings.setValue("databits", self.serial_bits.currentText())

    def change_stop_bits(self):
        """
        Set stop bits from combo box
        """
        if not settings:
            return

        stop_bits = constants.STOP_BITS[self.serial_stop.currentText()]
        self.serial.setStopBits(stop_bits)
        settings.setValue("stopbits", self.serial_stop.currentText())

    def change_flow(self):
        """
        Set flow control from combo box
        """
        if not settings:
            return

        flow = constants.FLOW_CONTROL[self.serial_flow.currentText()]
        self.serial.setFlowControl(flow)
        settings.setValue("flow", self.serial_flow.currentText())

    def change_parity(self):
        """
        Set parity type from combo box
        """
        if not settings:
            return

        parity = constants.PARITY[self.serial_parity.currentText()]
        self.serial.setParity(parity)
        settings.setValue("parity", self.serial_parity.currentText())

    def toggle_connection(self):
        """
        Attempt to connect to serial port
        """

        if self.serial_connect.text() == "Disconnect":
            self.serial.close()
            self.set_serial_options_enabled(True)
            self.connection_icon.setIcon(qtawesome.icon("mdi6.serial-port"))
            self.serial_connect.setText("Connect")
            return

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

        ok = self.serial.open(QIODevice.OpenModeFlag.ReadWrite)
        if ok:
            logger.info("Connected to serial")
            self.set_serial_options_enabled(False)
            self.connection_icon.setIcon(
                qtawesome.icon("mdi6.qrcode-scan", color="#03a9f4")
            )
        else:
            logger.error(f"Can't connect to serial port, {self.serial.error().name}")
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
        if self.data_buffer.endswith(constants.SCANNER_NEWLINE):
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
        else:
            QMessageBox.warning(
                self, "Scanner", "Scanner is currently scanning, scan rejected"
            )

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
        logger.error(f"Data rx error: {errcode.name}")
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
        self.serial_refresh.setEnabled(ena)
        self.serial_port.setEnabled(ena)
        self.serial_baud.setEnabled(ena)
        self.serial_bits.setEnabled(ena)
        self.serial_stop.setEnabled(ena)
        self.serial_flow.setEnabled(ena)
        self.serial_parity.setEnabled(ena)

    def emulate_scan(self):
        with open("example_scan.txt", "r", encoding="utf-8") as file:
            scans = file.readlines()
            for scan in scans:
                print(scan)
                self.on_data_retrieved(scan.strip("\r\n ") + "\r\n")

    def closeEvent(self, event: QCloseEvent) -> None:
        """
        Application close event

        Args:
            event (QCloseEvent | None): Qt close event
        """
        self.serial.close()
        event.accept()


def spinup():
    logger.info(f"Scouting Transfer App Version {__version__}")
    report_versions(logger)

    with open("style.qss", "r", encoding="utf-8") as file:
        qdarktheme.setup_theme(
            additional_qss=file.read(), custom_colors=constants.CUSTOM_COLORS_DARK
        )
    qtawesome.dark(app)
    MainWindow()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setWindowIcon(QIcon("icons/mercs.png"))
    app.setApplicationVersion(__version__)
    app.setApplicationName("6369 Scouting Data Transfer")

    settings = QSettings("Mercs", "ScoutingDataTransfer")
    spinup()

    sys.exit(app.exec())
