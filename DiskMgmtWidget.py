from __future__ import annotations

import sys
import typing
import logging

from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import *
from PyQt6.QtCore import *

from carousel import DiskWidget, CarouselWidget
import disk_detector
from disk_detector import Disk

ICON_ID_PAIRS = {"1": "icons/id-one.svg", "2": "icons/id-two.svg"}


# https://stackoverflow.com/questions/12523586/python-format-size-application-converting-b-to-kb-mb-gb-tb
def format_bytes(size):
    # 2**10 = 1024
    power = 2**10
    n = 0
    power_labels = {0: '', 1: 'K', 2: 'M', 3: 'G', 4: 'T'}
    while size > power:
        size /= power
        n += 1
    return f"{size:.1f}{power_labels[n] + 'B'}"


def default_disk_predicate(disk: disk_detector.Disk) -> tuple[bool, str, str]:
    if disk.mountpoint not in ["C:\\", "/"]:
        return True, f"{disk.mountpoint} fs:{disk.fstype} cap:{format_bytes(disk.capacity)}", "1"
    else:
        return False, "", "0"


class DiskMgmtWidget(QWidget):
    diskSelected = pyqtSignal(object, name="Disk Selected")  # workaround for Qt not liking NoneType
    diskFocused = pyqtSignal(object, name="Disk Focus in Dropdown")

    def __init__(self, detector=disk_detector.DiskDetector(), predicate=default_disk_predicate):
        super().__init__()

        self._main_layout = QVBoxLayout()
        self._main_layout.setContentsMargins(0, 0, 0, 0)
        self.setLayout(self._main_layout)

        self.blocked_mounts = ["C:\\", "/"]

        self._dd = detector
        self._disks: list[disk_detector.Disk] = []
        self._filtered_disks: list[disk_detector.Disk] = []
        self._last_focused_disk: disk_detector.Disk | None = None

        self._predicate: typing.Callable[[disk_detector.Disk], tuple[bool, str]] = predicate

        self._timer = QTimer(self)
        self._timer.setInterval(1000)
        self._timer.timeout.connect(self.update_disks)
        self._timer.start()

        self._title = QLabel("Disks")
        self._main_layout.addWidget(self._title)

        self._disks_dropdown = QComboBox()
        self._disks_dropdown.setIconSize(QSize(48, 48))
        self._disks_dropdown.setMinimumHeight(56)
        self._disks_dropdown.setObjectName("big_dropdown")
        self._disks_dropdown.currentTextChanged.connect(self._send_focused_disk)
        self._main_layout.addWidget(self._disks_dropdown)

        self._refresh = QPushButton("Refresh")
        self._refresh.clicked.connect(self.update_disks)
        self._refresh.setShortcut(Qt.Key.Key_F5)
        self._main_layout.addWidget(self._refresh)

        self._select = QPushButton("Select")
        self._select.clicked.connect(lambda:
                                     self.diskSelected.emit(self.get_selected_disk()))
        self._select.setEnabled(False)
        self._main_layout.addWidget(self._select)

        logging.debug(f"Disk widget initialized using {self._predicate.__name__}")

    def update_disks(self) -> None:
        current_index = self._disks_dropdown.currentIndex()
        self._disks_dropdown.clear()

        self._disks = self._dd.get_disks()
        filtered_disks = []
        drop_items = []

        if self._disks:
            for disk in self._disks:
                if self._predicate(disk)[0]:
                    widget = DiskWidget.DiskWidget()
                    widget.setMountpoint(self._predicate(disk)[1])
                    if self._predicate(disk)[2] in ICON_ID_PAIRS:
                        icon = ICON_ID_PAIRS[self._predicate(disk)[2]]
                    else:
                        icon = "icons/drive.svg"
                    filtered_disks.append(disk)
                    drop_items.append((QIcon(icon), self._predicate(disk)[1]))

        self._select.setEnabled(bool(filtered_disks))
        if not filtered_disks:
            self._send_focused_disk()

        self._filtered_disks = filtered_disks
        for item in drop_items:
            self._disks_dropdown.addItem(item[0], item[1])
        self._disks_dropdown.setCurrentIndex(max(current_index, 0))  # always try to keep one selected

    def set_timer_enabled(self, enabled: bool) -> None:
        if enabled:
            self._timer.start()
        else:
            self._timer.stop()

    def set_disk_predicate(self, predicate: typing.Callable[[disk_detector.Disk], tuple[bool, str]]) -> None:
        self._predicate = predicate

    def get_raw_disks(self) -> list[disk_detector.Disk]:
        return self._disks

    def get_disks(self) -> list[disk_detector.Disk]:
        return self._filtered_disks

    def get_selected_disk(self) -> Disk | list[Disk] | None:
        if len(self._filtered_disks) > 0:
            return self._filtered_disks[self._disks_dropdown.currentIndex()]
        else:
            return None

    def _send_focused_disk(self) -> None:
        if not self._filtered_disks:
            self.diskFocused.emit(None)
            self._last_focused_disk = None
            return

        if self._filtered_disks[self._disks_dropdown.currentIndex()] != self._last_focused_disk:
            self.diskFocused.emit(self._filtered_disks[self._disks_dropdown.currentIndex()])
            self._last_focused_disk = self._filtered_disks[self._disks_dropdown.currentIndex()]


if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    app = QApplication(sys.argv)
    widget = DiskMgmtWidget()
    widget.diskSelected.connect(print)  # print disk on selection
    widget.show()
    sys.exit(app.exec())
