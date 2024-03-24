"""
Qt data model for a pandas DataFrame
"""

import math

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QStandardItem, QStandardItemModel, QIcon
import qtawesome

import pandas


class PandasModel(QStandardItemModel):
    """
    Qt data model for a pandas DataFrame
    """

    def __init__(self, data: pandas.DataFrame, parent=None):
        QStandardItemModel.__init__(self, parent)
        self._data = data
        for row in data.values.tolist():
            data_row = [QStandardItem(str(x)) for x in row]
            self.appendRow(data_row)
        return

    def rowCount(self, _=None):
        return len(self._data.values)

    def columnCount(self, _=None):
        return self._data.columns.size

    def load_data(self, data: pandas.DataFrame):
        self._data = data
        for i, row in enumerate(self._data.values.tolist()):
            for j, value in enumerate(row):
                item = self.item(i, j)
                if isinstance(value, float) and math.isnan(value):
                    icon = qtawesome.icon("mdi6.null")
                elif isinstance(value, bool):
                    icon = qtawesome.icon("mdi6.circle", color="#4caf50" if value else "#f44336")
                elif isinstance(value, float):
                    icon = qtawesome.icon("mdi6.decimal")
                elif isinstance(value, int):
                    icon = qtawesome.icon("mdi6.pound")
                elif isinstance(value, str) and j == 0:
                    icon = qtawesome.icon("mdi6.apple-keyboard-command")
                elif isinstance(value, str):
                    icon = qtawesome.icon("mdi6.code-string")
                else:
                    icon = QIcon()

                if item:
                    item.setText(str(value))
                    item.setIcon(icon)
                else:
                    stditem = QStandardItem(str(value))
                    stditem.setIcon(icon)
                    self.setItem(i, j, stditem)

    def headerData(self, x, orientation, role):
        if (
            orientation == Qt.Orientation.Horizontal
            and role == Qt.ItemDataRole.DisplayRole
        ):
            return self._data.columns[x]
        if (
            orientation == Qt.Orientation.Vertical
            and role == Qt.ItemDataRole.DisplayRole
        ):
            return self._data.index[x]
        return None
