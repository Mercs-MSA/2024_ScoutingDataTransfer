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
    def __init__(self, data: list[dict[str, str]], columns: list, column_types: list, parent=None):
        QStandardItemModel.__init__(self, parent)
        self._data = data
        self._columns = columns
        self._column_types = column_types
        
        for row in data:
            data_row = [QStandardItem(str(x)) for x in row.values()]
            self.appendRow(data_row)
        return
    
    def rowCount(self, _=None):
        return len(self._data)
    
    def columnCount(self, _=None):
        return len(self._columns)
    
    def load_data(self, data: list[dict[str, str]]):
        self._data = data
        self.clear()
        for row in data:
            data_row = [QStandardItem(str(x)) for x in row.values()]
            self.appendRow(data_row)
                
    def headerData(self, section: int, orientation: Qt.Orientation, role: int = ...) -> Any:
        if orientation == Qt.Orientation.Horizontal and role == Qt.ItemDataRole.DisplayRole:
            return self._columns[section]