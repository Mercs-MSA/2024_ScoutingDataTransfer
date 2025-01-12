"""
Constant values for scouting transfer
"""

import typing
import enum

from PySide6.QtSerialPort import QSerialPort

FIELDS = {
    "pit": {
        "form": "pit",
        "team": "INTEGER",
        "scouters": "TEXT",
        "length": "INTEGER",
        "width": "INTEGER",
        "height": "INTEGER",
        "weight": "INTEGER",
        "drivebase": "TEXT",
        "autonExists": "BOOLEAN",
    }
}

BAUDS: typing.Final = [
    300,
    600,
    900,
    1200,
    2400,
    3200,
    4800,
    9600,
    19200,
    38400,
    57600,
    115200,
    230400,
    460800,
    921600,
]

DATA_BITS: typing.Final = {
    "5 Data Bits": QSerialPort.DataBits.Data5,
    "6 Data Bits": QSerialPort.DataBits.Data6,
    "7 Data Bits": QSerialPort.DataBits.Data7,
    "8 Data Bits": QSerialPort.DataBits.Data8,
}

STOP_BITS: typing.Final = {
    "1 Stop Bits": QSerialPort.StopBits.OneStop,
    "1.5 Stop Bits": QSerialPort.StopBits.OneAndHalfStop,
    "2 Stop Bits": QSerialPort.StopBits.TwoStop,
}

PARITY: typing.Final = {
    "No Parity": QSerialPort.Parity.NoParity,
    "Even Parity": QSerialPort.Parity.EvenParity,
    "Odd Parity": QSerialPort.Parity.OddParity,
    "Mark Parity": QSerialPort.Parity.MarkParity,
    "Space Parity": QSerialPort.Parity.SpaceParity,
}

FLOW_CONTROL: typing.Final = {
    "No Flow Control": QSerialPort.FlowControl.NoFlowControl,
    "Software FC": QSerialPort.FlowControl.SoftwareControl,
    "Hardware FC": QSerialPort.FlowControl.HardwareControl,
}


class DataError(enum.Enum):
    """Potential error for worker"""

    DATA_MALFORMED = 0
    UNKNOWN_FORM = 1
    TEAM_NUMBER_NULL = 2
    MATCH_NUMBER_NULL = 3
