"""
6369 Scouting Data Transfer
Transfer data form scouting tablets using qr code scanner
"""

import sys
import os
import json

from PyQt6.QtWidgets import (QApplication, QMainWindow, QHBoxLayout, QVBoxLayout,
                             QWidget, QSplitter, QLineEdit, QPushButton, QLabel,
                             QFileDialog)
from PyQt6.QtCore import QSettings, QSize
from PyQt6.QtGui import *
import qdarktheme
import qtawesome

import DiskMgmtWidget
import disk_detector


# https://stackoverflow.com/questions/12523586/python-format-size-application-converting-b-to-kb-mb-gb-tb
def format_bytes(size: int) -> str:
    """Convert bytes to str of KB, MB, etc

    Args:
        size (int): bytes

    Returns:
        str: Size string
    """
    power = 2**10
    n = 0
    power_labels = {0: "", 1: "K", 2: "M", 3: "G", 4: "T"}
    while size > power:
        size /= power
        n += 1
    return f"{size:.1f}{power_labels[n] + 'B'}"


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
                f"cap:{format_bytes(disk.capacity)}",
                str(opts["id"]),
            )
        if opts["display"]:
            return (
                True,
                f"ID: ?? {disk.mountpoint} fs:{disk.fstype} cap:{format_bytes(disk.capacity)}",
                "0",
            )

    return False, "", "??"


class MainWindow(QMainWindow):
    """Main Window"""

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("6369 Scouting Data Transfer")

        self.root_widget = QWidget()
        self.setCentralWidget(self.root_widget)

        self.root_layout = QHBoxLayout()
        self.root_widget.setLayout(self.root_layout)

        self.splitter = QSplitter()
        self.root_layout.addWidget(self.splitter)


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
        self.transfer_dir_textbox.textChanged.connect(self.validate_transfer_dir)
        self.transfer_dir_layout.addWidget(self.transfer_dir_textbox)

        self.transfer_dir_picker = QPushButton("Pick Dir")
        self.transfer_dir_picker.clicked.connect(self.select_transfer_dir)
        self.transfer_dir_layout.addWidget(self.transfer_dir_picker)

        self.transfer_dir_icon = QLabel()
        self.transfer_dir_icon.setPixmap(qtawesome.icon("mdi6.alert", color="#f44336").pixmap(QSize(24, 24)))
        self.transfer_dir_layout.addWidget(self.transfer_dir_icon)

        self.drive_layout.addStretch()

        self.disk_widget = DiskMgmtWidget.DiskMgmtWidget(predicate=scouting_disk_predicate)
        self.drive_layout.addWidget(self.disk_widget)

        self.drive_layout.addStretch()

        # Scan manager (right side)
        self.scanner_widget = QWidget()
        self.splitter.addWidget(self.scanner_widget)

        self.scanner_layout = QVBoxLayout()
        self.scanner_widget.setLayout(self.scanner_layout)

        self.show()

    def select_transfer_dir(self):
        self.transfer_dir_textbox.setText(str(QFileDialog.getExistingDirectory(self, "Select Directory")))

    def validate_transfer_dir(self):
        valid = os.path.isdir(self.transfer_dir_textbox.text())
        if valid:
            self.transfer_dir_icon.setPixmap(qtawesome.icon("mdi6.check-circle", color="#4caf50").pixmap(QSize(24, 24)))
        else:
            self.transfer_dir_icon.setPixmap(qtawesome.icon("mdi6.alert", color="#f44336").pixmap(QSize(24, 24)))


if __name__ == "__main__":
    app = QApplication(sys.argv)
    settings = QSettings('Mercs', 'ScoutingDataTransfer')
    qdarktheme.setup_theme(additional_qss="#big_dropdown{height: 56px}")
    win = MainWindow()
    sys.exit(app.exec())
