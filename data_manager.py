from enum import Enum
import json
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
    on_data_updated = Signal()

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
                f"CREATE TABLE IF NOT EXISTS {table} (rowid INTEGER PRIMARY KEY AUTOINCREMENT, timestamp DATETIME DEFAULT CURRENT_TIMESTAMP)"
            )
            if not self.query.exec():
                self.on_message.emit(
                    f"Failed to create table {table}: {self.query.lastError().text()}",
                    MessageType.ERROR,
                )

        # robot pictures
        self.query.prepare(
            "CREATE TABLE IF NOT EXISTS robot_pictures (rowid INTEGER PRIMARY KEY AUTOINCREMENT, timestamp DATETIME DEFAULT CURRENT_TIMESTAMP, team INTEGER, picture BLOB)"
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
            self.on_message.emit(
                "DB not initialized\nCreate a new database in settings",
                MessageType.FATAL,
            )
            return

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

        # Check for extra fields
        for field in existing_fields:
            if field not in fields and field not in ["rowid", "timestamp"]:
                self.on_message.emit(
                    f"Extra field '{field}' found in table '{table}', database cleanup recommended",
                    MessageType.WARN,
                )

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
            self.on_message.emit(
                "DB not initialized\nCreate a new database in settings",
                MessageType.FATAL,
            )
            return

        table = data["form"]
        fields = constants.FIELDS[table]
        values = ", ".join(
            [
                f"'{data[field]}'"
                if isinstance(data[field], str)
                else "NULL"
                if data[field] is None
                else str(data[field])
                for field in fields.keys()
            ]
        )
        query = f"INSERT INTO {table} ({', '.join(fields.keys())}) VALUES ({values})"
        print(query)
        if not self.query.exec(query):
            self.on_message.emit(
                f"Failed to insert data: {self.query.lastError().text()}",
                MessageType.ERROR,
            )

        self.on_data_updated.emit()

    def get_data(self, form: str) -> list[dict[str, Any]]:
        """Get all data from a form

        Args:
            form (str): Name of form/table

        Returns:
            list[dict[str, Any]]: List of data
        """
        if not self.query:
            self.on_message.emit(
                "DB not initialized\nCreate a new database in settings",
                MessageType.FATAL,
            )
            return []

        query = f"SELECT * FROM {form}"
        self.query.exec(query)
        data = []
        while self.query.next():
            row = {}
            row["rowid"] = self.query.value("rowid")
            row["timestamp"] = self.query.value("timestamp")
            for field in (
                constants.FIELDS[form]
                if form != "robot_pictures"
                else ["team", "picture"]
            ):
                row[field] = self.query.value(field)
            data.append(row)
        return data

    def get_datapoint(self, form: str, rowid: int) -> dict[str, Any] | None:
        """Get all data from a form

        Args:
            form (str): Name of form/table

        Returns:
            list[dict[str, Any]]: List of data
        """
        if not self.query:
            self.on_message.emit(
                "DB not initialized\nCreate a new database in settings",
                MessageType.FATAL,
            )
            return {}

        query = f"SELECT * FROM {form} WHERE rowid={rowid}"
        self.query.exec(query)
        if not self.query.next():
            return None
        row = {}
        row["rowid"] = self.query.value("rowid")
        row["timestamp"] = self.query.value("timestamp")
        for field in (
            constants.FIELDS[form] if form != "robot_pictures" else ["team", "picture"]
        ):
            row[field] = self.query.value(field)
        return row

    def get_pictures(self, team: int) -> dict[str, Any] | None:
        """Get all data from a form

        Args:
            form (str): Name of form/table

        Returns:
            list[dict[str, Any]]: List of data
        """
        if not self.query:
            self.on_message.emit(
                "DB not initialized\nCreate a new database in settings",
                MessageType.FATAL,
            )
            return {}

        query = f"SELECT * FROM robot_pictures WHERE team={team}"
        self.query.exec(query)
        if not self.query.next():
            return None
        row = {}
        row["rowid"] = self.query.value("rowid")
        row["timestamp"] = self.query.value("timestamp")
        row["team"] = self.query.value("team")
        row["picture"] = self.query.value("picture")
        return row

    def add_robot_pictures(self, team: int, pictures: list[bytes]):
        """Add robot pictures to database

        Args:
            team (int): Team number
            pictures (list[bytes]): List of pictures as bytes
        """
        if not self.query:
            self.on_message.emit(
                "DB not initialized\nCreate a new database in settings",
                MessageType.FATAL,
            )
            return

        pics = {"picture": []}
        for picture in pictures:
            pics["picture"].append(picture)

        self.query.prepare("INSERT INTO robot_pictures (team, picture) VALUES (?, ?)")
        self.query.addBindValue(team)
        self.query.addBindValue(json.dumps(pics))
        if not self.query.exec():
            self.on_message.emit(
                f"Failed to insert robot pictures: {self.query.lastError().text()}",
                MessageType.ERROR,
            )

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
            self.on_message.emit(
                "DB not initialized\nCreate a new database in settings",
                MessageType.FATAL,
            )
            return False

        value_str = f"'{value}'" if isinstance(value, str) else str(value)
        self.query.prepare(
            f"UPDATE {form} SET {field} = {value_str} WHERE rowid = {row}"
        )

        ret: bool = self.query.exec()
        self.on_data_updated.emit()
        return ret

    def delete_row(self, form: str, row: int) -> bool:
        """Delete a specific row

        Args:
            form (str): Name of form/table
            row (int): Id of row

        Returns:
            bool: True if delete successful, False otherwise
        """
        if not self.query:
            self.on_message.emit(
                "DB not initialized\nCreate a new database in settings",
                MessageType.FATAL,
            )
            return False

        query = f"DELETE FROM {form} WHERE rowid = {row}"
        ret: bool = self.query.exec(query)
        self.on_data_updated.emit()
        return ret

    def to_csv(self, form: str, headers: bool = True, identifiers: bool = False) -> str:
        """Convert the database to csv

        Args:
            form (str): Form id
            headers (bool, optional): Export data headers. Defaults to True.
        """
        if not self.query:
            self.on_message.emit(
                "DB not initialized\nCreate a new database in settings",
                MessageType.FATAL,
            )
            return ""

        query = f"SELECT * FROM {form}"
        self.query.exec(query)
        data = []
        while self.query.next():
            row = {}
            for i, field in enumerate(constants.FIELDS[form]):
                row[field] = self.query.value(i + (0 if identifiers else 2))
            data.append(row)
        # convert list of dicts to csv
        csv_data = []
        if headers:
            csv_data.append(list(constants.FIELDS[form].keys()))
        csv_data.extend([list(row.values()) for row in data])
        csv_str = "\n".join(
            [
                ",".join([f'"{x}"' if "," in x else x for x in map(str, row)])
                for row in csv_data
            ]
        )
        return csv_str
