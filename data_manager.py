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
        tables: list[str] = list(constants.FIELDS.keys()),
    ):
        super().__init__()
        self.db = None

        self.query: QSqlQuery | None = None
        self.tables = tables

    def connect_db_sqlite(self, database_name="scouting.sqlite"):
        if self.db:
            self.db.commit()
            self.db.close()
            self.db.removeDatabase(self.db.databaseName())
        if self.query:
            self.query.clear()
            self.query.finish()

        self.db = QSqlDatabase.addDatabase("QSQLITE")
        self.db.setDatabaseName(database_name)

        if not self.db.open():
            self.on_message.emit(
                f"Failed to open database: {self.db.lastError().text()}",
                MessageType.FATAL,
            )
            return

    def initialize(self):
        if not self.db:
            raise RuntimeError("DB not created")
    
        self.query = QSqlQuery(self.db)

        # create empty tables
        for table in self.tables:
            self.query.prepare(
                f"CREATE TABLE IF NOT EXISTS {table} (id INTEGER PRIMARY KEY AUTOINCREMENT, timestamp DATETIME DEFAULT CURRENT_TIMESTAMP)"
            )
            if not self.query.exec():
                self.on_message.emit(
                    f"Failed to create table {table}: {self.query.lastError().text()}",
                    MessageType.ERROR,
                )

        # robot pictures
        self.query.prepare(
            "CREATE TABLE IF NOT EXISTS robot_pictures (id INTEGER PRIMARY KEY AUTOINCREMENT, timestamp DATETIME DEFAULT CURRENT_TIMESTAMP, team INTEGER, picture BLOB)"
        )
        if not self.query.exec():
            self.on_message.emit(
                f"Failed to create robot_pictures table: {self.query.lastError().text()}",
                MessageType.ERROR,
            )

        # data

    def set_fields(self, table: str, fields: dict[str, str]):
        """Set fields supported in database

        Args:
            table (str): Name of form/table
            fields (dict[str, str]): Keys=field names, values=type
        """
        if not self.query:
            raise RuntimeError("DB not initialized")

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
                    f"ALTER TABLE '{table}' ADD COLUMN '{field}' '{field_type}'"
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
        if not self.query:
            raise RuntimeError("DB not initialized")

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
        if not self.query:
            raise RuntimeError("DB not initialized")

        query = f"SELECT * FROM {form}"
        self.query.exec(query)
        data = []
        while self.query.next():
            row = {}
            row["id"] = self.query.value(0)
            row["timestamp"] = self.query.value(1)
            for i, field in enumerate(constants.FIELDS[form]):
                row[field] = self.query.value(i + 2)
            data.append(row)
        return data

    def update_data(self, form: str, row: int, field: str, value: Any) -> bool:
        """Update a specific field in a row

        Args:
            form (str): Name of form/table
            row (int): Id of row
            field (str): Name of field
            value (Any): New value

        Returns:
            bool: True if update successful, False otherwise
        """
        if not self.query:
            raise RuntimeError("DB not initialized")

        value_str = f"'{value}'" if isinstance(value, str) else str(value)
        self.query.prepare(f"UPDATE {form} SET {field} = {value_str} WHERE id = {row}")
        return self.query.exec()

    def delete_row(self, form: str, row: int) -> bool:
        """Delete a specific row

        Args:
            form (str): Name of form/table
            row (int): Id of row

        Returns:
            bool: True if delete successful, False otherwise
        """
        if not self.query:
            raise RuntimeError("DB not initialized")

        query = f"DELETE FROM {form} WHERE id = {row}"
        return self.query.exec(query)
