"""
Qt data model for a pandas DataFrame
"""

import math
from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtGui import QStandardItem, QStandardItemModel, QIcon
import qtawesome


# The same as PandasModel, but uses a list of dicts, key=header value, value=val
class ListDictModel(QStandardItemModel):
    def __init__(
        self, data: list[dict[str, str]], columns: list, column_types: list, parent=None
    ):
        QStandardItemModel.__init__(self, parent)
        self._data = data
        self._columns = columns
        self._column_types = column_types

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

    def headerData(
        self, section: int, orientation: Qt.Orientation, role: int = ...
    ) -> Any:
        if (
            orientation == Qt.Orientation.Horizontal
            and role == Qt.ItemDataRole.DisplayRole
        ):
            return self._columns[section]
