"""
Qt data model for a pandas DataFrame
"""

import math
from typing import Any

from PySide6.QtWidgets import QMessageBox
from PySide6.QtCore import Qt
from PySide6.QtGui import QStandardItem, QStandardItemModel, QIcon
import qtawesome

import constants


class ScoutingFormModel(QStandardItemModel):
    def __init__(
        self, data: list[dict[str, str]], columns: list, column_types: list, form: str, parent=None
    ):
        QStandardItemModel.__init__(self, parent)
        self._data = data
        self._columns = columns
        self._column_types = column_types
        self.form = form

        self.load_data(data)
        return

    def rowCount(self, _=None):
        return len(self._data)

    def columnCount(self, _=None):
        return len(self._columns)

    def load_data(self, data: list[dict[str, str]]):
        self._data = data
        self.clear()
        for row in data:
            items = []
            for i, value in enumerate(row.values()):
                item = QStandardItem(str(value))
                # set item icon
                if isinstance(value, float) and math.isnan(value):
                    icon = qtawesome.icon("mdi6.null")
                elif self._column_types[i] == "BOOLEAN":
                    icon = qtawesome.icon(
                        "mdi6.circle", color="#4caf50" if value else "#f44336"
                    )
                elif isinstance(value, float):
                    icon = qtawesome.icon("mdi6.decimal")
                elif isinstance(value, int):
                    icon = qtawesome.icon("mdi6.pound")
                elif isinstance(value, str):
                    icon = qtawesome.icon("mdi6.code-string")
                else:
                    icon = QIcon()
                item.setIcon(icon)
                items.append(item)
            # data_row = [QStandardItem(str(x)) for x in row.values()]
            # self.appendRow(data_row)
            self.appendRow(items)

    def setData(self, index, value, role=Qt.ItemDataRole.EditRole):
        if index.column() == 0:  # Reject updates to the first column
            QMessageBox.critical(
                self.parent(),
                "Error",
                "Cannot edit form identifier column"
            )
            return False  # Explicitly reject the update
        

        if list(constants.FIELDS[self.form].values())[index.column()] in ["INT", "INTEGER", "TINYINT", "SMALLINT", "MEDIUMINT", "BIGINT", "UNSIGNED BIG INT", "INT2", "INT8"]:
            try:
                int(value)
            except ValueError:
                QMessageBox.warning(self.parent(), "Invalid Input", "Please enter a valid integer.")
                return False

        QStandardItemModel.setData(self, index, value, role)

        # Update the icon
        if role == Qt.ItemDataRole.EditRole:
            item = self.itemFromIndex(index)
            if isinstance(value, float) and math.isnan(value):
                item.setIcon(qtawesome.icon("mdi6.null"))
            elif self._column_types[index.column()] == "BOOLEAN":
                item.setIcon(
                    qtawesome.icon(
                        "mdi6.circle", color="#4caf50" if bool(int(value)) else "#f44336"
                    )
                )
            elif self._column_types[index.column()] == "FLOAT":
                item.setIcon(qtawesome.icon("mdi6.decimal"))
            elif self._column_types[index.column()] == "INTEGER":
                item.setIcon(qtawesome.icon("mdi6.pound"))
            elif self._column_types[index.column()] == "TEXT":
                item.setIcon(qtawesome.icon("mdi6.code-string"))
            else:
                item.setIcon(QIcon())
            # switch out item
            self.setItem(index.row(), index.column(), item)

        return True

    def headerData(
        self, section: int, orientation: Qt.Orientation, role: int = ...
    ) -> Any:
        if (
            orientation == Qt.Orientation.Horizontal
            and role == Qt.ItemDataRole.DisplayRole
        ):
            return self._columns[section]
