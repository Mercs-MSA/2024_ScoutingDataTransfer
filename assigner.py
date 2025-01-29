import json
import os
import traceback
from datetime import datetime

import qtawesome
import statbotics
from PySide6.QtCore import QObject, Signal, Qt, QSize, QThread, QCoreApplication, QPoint
from PySide6.QtWidgets import (
    QTabWidget,
    QAbstractItemView,
    QListWidget,
    QPushButton,
    QHBoxLayout,
    QVBoxLayout,
    QLabel,
    QScrollArea,
    QWidget,
    QListWidgetItem,
    QMessageBox,
    QLineEdit,
    QInputDialog,
    QApplication,
    QFileDialog,
    QMenu,
    QProgressDialog,
)

import utils


class EventCodeWorker(QObject):
    finished = Signal(list)
    on_error = Signal(str)

    def __init__(self, api: statbotics.Statbotics, district: str) -> None:
        super().__init__()
        self.api = api
        self.district = district

    def run(self):
        try:
            events = self.api.get_events(datetime.now().year, district=self.district)
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
        self.eventcode = event

    def run(self):
        try:
            teams = self.api.get_team_events(
                event=self.eventcode, fields=["team", "team_name"]
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
        except (Exception, UserWarning):
            traceback.print_exc()
            self.on_error.emit(traceback.format_exc())
            self.finished.emit([])


class AssignerWidget(QTabWidget):
    on_api_error = Signal(str)

    def __init__(
        self, app: QApplication | QCoreApplication, sbapi: statbotics.Statbotics
    ):
        super().__init__()
        self.app = app
        self.sbapi = sbapi
        self.progress_dialog: QProgressDialog | None = None

        self.on_api_error.connect(
            lambda: self.progress_dialog.close() if self.progress_dialog else None
        )

        self.assign_pit_widget = QWidget()
        self.addTab(self.assign_pit_widget, "Pit")

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
        self.addTab(self.assign_match_widget, "Match")

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
            self, "Team Number", "Enter a valid team number"
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
            self.api_worker.on_error.connect(self.on_api_error.emit)
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
            self.api_worker.on_error.connect(self.on_api_error.emit)
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

            self.app.processEvents()

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

        self.progress_dialog = QProgressDialog("Loading Match List", "", 0, 100, self)
        self.progress_dialog.setCancelButton(None)
        self.progress_dialog.setWindowModality(Qt.WindowModality.WindowModal)
        self.progress_dialog.show()

        for idx, session in enumerate(converted_matches):
            item = QListWidgetItem()
            item.setText(
                f"Team: {session['teamNumber']} | Match: {session['match']} | Alliance: {session['alliance']} | Position: {session['position']}"
            )
            item.setData(Qt.ItemDataRole.UserRole, session)
            self.assign_match_ignored_teams.addItem(item)

            self.progress_dialog.setValue(round(idx / len(converted_matches) * 100))

            self.app.processEvents()

        self.progress_dialog.close()

    def on_pit_teams(self, teams: list):
        self.assign_match_pit_teams = teams
