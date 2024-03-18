from PyQt6.QtGui import QPixmap
from PyQt6.QtWidgets import QApplication, QFrame, QVBoxLayout, QLabel


class DiskWidget(QFrame):
    def __init__(self):
        super().__init__()
        self._root_layout = QVBoxLayout()
        self.setLayout(self._root_layout)

        self.icon = QLabel()
        self.icon.setPixmap(QPixmap("../icons/drive.svg"))
        self._root_layout.addWidget(self.icon)

        self.mountpoint_label = QLabel("")
        self._root_layout.addWidget(self.mountpoint_label)

    def setIcon(self, pixmap: QPixmap) -> None:
        self.icon.setPixmap(pixmap)

    def setMountpoint(self, mp: str) -> None:
        self.mountpoint_label.setText(mp)

    def setSelected(self, selected: bool) -> None:
        if selected:
            self.setStyleSheet("QFrame { background-color: red; }")
        else:
            self.setStyleSheet("")


if __name__ == '__main__':
    app = QApplication([])
    widget = DiskWidget()
    widget.show()
    app.exec()
