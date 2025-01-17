"""
Constant values for scouting transfer
"""

import typing
import enum

from PySide6.QtSerialPort import QSerialPort
from PySide6.QtCore import QSize

# Database fields
# Update this to add more tables (forms), or database fields (form items)
FIELDS = {
    "pit": {
        "form": "TEXT",
        "team": "INTEGER",
        "scouters": "TEXT",
        "length": "INTEGER",
        "width": "INTEGER",
        "height": "INTEGER",
        "weight": "INTEGER",
        "lOne": "BOOLEAN",
        "lTwo": "BOOLEAN",
        "lThree": "BOOLEAN",
        "lFour": "BOOLEAN",
        "driverYears": "INTEGER",
        "operatorYears": "INTEGER",
        "coachYears": "INTEGER",
        "isCoachAdult": "BOOLEAN",
        "drivebase": "TEXT",
        "autonExists": "BOOLEAN",
    }
}

# Sidebar
# All forms MUST have a sidebar constructor
# Each constructor is written in HTML and CSS
# Jinja2 syntax is allowed and required for accessing fields
# `include_file` is a custom function that includes a file from the `templates` directory
SIDEBAR_CONSTRUCTORS = {
    "pit": """
    {{ include_file('pit.html') }}
    """
}

# Sidebar Renderer
# 0 = Basic html text renderer, 1 = Web renderer
SIDEBAR_RENDERER = 1

# Picture Save Max Resolution
# Max resolution for saving pictures, will use original image's aspect ratio
PICTURE_SAVE_MAX_RESOLUTION = QSize(512, 512)

# Picture Display Max Resolution
# Max resolution for displaying pictures, will use original image's aspect ratio
PICTURE_DISPLAY_MAX_RESOLUTION = QSize(300, 300)

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


CUSTOM_COLORS_DARK: dict[str, str | dict[str, str]] | None = {
    "background": "#111114",
    "primary": "#FFB3A9",
}


class DataError(enum.Enum):
    """Potential error for worker"""

    LENGTH_MISMATCH = 0
    UNKNOWN_FORM = 1
    TEAM_NUMBER_NULL = 2
    MATCH_NUMBER_NULL = 3
