from enum import Enum
from typing import Any
from PySide6.QtCore import QObject, Signal
from PySide6.QtSql import QSqlDatabase, QSqlQuery

import constants


class MessageType(Enum):
    INFO = 0
    WARN = 1
    ERROR = 2
    FATAL = 3


class DataManager(QObject):
    on_message = Signal(str, MessageType)

    def __init__(
        self,
        database_kind="QSQLITE",
        database_name="scouting.sqlite",
        tables: list[str] = list(constants.FIELDS.keys()),
    ):
        super().__init__()
        self.db = QSqlDatabase.addDatabase(database_kind)
        self.db.setDatabaseName(database_name)
        if not self.db.open():
            self.on_message.emit(
                f"Failed to open database: {self.db.lastError().text()}",
                MessageType.FATAL,
            )
            return

        self.query = QSqlQuery()

        # create empty tables
        for table in tables:
            self.query.prepare(
                f"CREATE TABLE IF NOT EXISTS {table} (id INTEGER PRIMARY KEY AUTOINCREMENT, timestamp DATETIME DEFAULT CURRENT_TIMESTAMP)"
            )
            if not self.query.exec():
                self.on_message.emit(
                    f"Failed to create table {table}: {self.query.lastError().text()}",
                    MessageType.ERROR,
                )

    def set_fields(self, table: str, fields: dict[str, str]):
        """Set fields supported in database

        Args:
            table (str): Name of form/table
            fields (dict[str, str]): Keys=field names, values=type
        """
        self.query.prepare(f"PRAGMA table_info({table})")
        if not self.query.exec():
            self.on_message.emit(
                f"Failed to get table info: {self.query.lastError().text()}",
                MessageType.ERROR,
            )
            return

        # Get existing field rows
        existing_fields = []
        while self.query.next():
            existing_fields.append(self.query.value("name"))

        # Add new fields to table
        for field, field_type in fields.items():
            if field not in existing_fields:
                self.query.prepare(
                    f"ALTER TABLE {table} ADD COLUMN {field} {field_type}"
                )
                if not self.query.exec():
                    self.on_message.emit(
                        f"Failed to add field {field}: {self.query.lastError().text()}",
                        MessageType.ERROR,
                    )

        for field, field_type in fields.items():
            if field not in existing_fields:
                self.query.prepare(
                    f"ALTER TABLE {table} ADD COLUMN {field} {field_type}"
                )
                if not self.query.exec():
                    self.on_message.emit(
                        f"Failed to add field {field}: {self.query.lastError().text()}",
                        MessageType.ERROR,
                    )

    def add_data(self, data: dict[str, Any]):
        """Add new data to database

        Args:
            data (dict[str, Any]): Key=field names, values=data
        """
        table = data["form"]
        fields = constants.FIELDS[table]
        values = ", ".join(
            [
                f"'{data[field]}'" if isinstance(data[field], str) else str(data[field])
                for field in fields.keys()
            ]
        )
        query = f"INSERT INTO {table} ({', '.join(fields.keys())}) VALUES ({values})"
        if not self.query.exec(query):
            self.on_message.emit(
                f"Failed to insert data: {self.query.lastError().text()}",
                MessageType.ERROR,
            )

    def get_data(self, form: str) -> list[dict[str, Any]]:
        """Get all data from a form

        Args:
            form (str): Name of form/table

        Returns:
            list[dict[str, Any]]: List of data
        """
        query = f"SELECT * FROM {form}"
        self.query.exec(query)
        data = []
        while self.query.next():
            row = {}
            for i, field in enumerate(constants.FIELDS[form]):
                row[field] = self.query.value(i + 2)
            data.append(row)
        return data
