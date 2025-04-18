"""
Constant values for scouting transfer
"""

import typing
import enum

from PySide6.QtSerialPort import QSerialPort
from PySide6.QtCore import QSize

# Database fields
# Update this to add more tables (forms), or database fields (form items)

#!# IMPORTANT
# *# Unsupported field names (used internally by the program)
### - rowid, timestamp, warnBase64Icon, xBase64Icon, checkBase64Icon, logo16Base64, include_file, generator
# *# Required fields: `form` (index 0 - TEXT), `team` (index 1 - INTEGER)

FIELDS = {
    "pit": {
        "form": "TEXT",
        "team": "INTEGER",
        "scouters": "TEXT",
        "width": "INTEGER",
        "length": "INTEGER",
        "weight": "INTEGER",
        "lOne": "BOOLEAN",
        "lTwo": "BOOLEAN",
        "lThree": "BOOLEAN",
        "lFour": "BOOLEAN",
        "processor": "BOOLEAN",
        "barge": "BOOLEAN",
        "descore": "BOOLEAN",
        "deepClimb": "BOOLEAN",
        "shallowClimb": "BOOLEAN",
        "groundIntake": "BOOLEAN",
        "coralCycle": "BOOLEAN",
        "algaeCycle": "BOOLEAN",
        "defense": "BOOLEAN",
        "feed": "BOOLEAN",
        "driverYears": "INTEGER",
        "operatorYears": "INTEGER",
        "coachYears": "INTEGER",
        "isCoachAdult": "BOOLEAN",
        "drivebase": "TEXT",
        "repairability": "DOUBLE",
        "humanPlayerLocation": "TEXT",
        "autonExists": "BOOLEAN",
        "notes": "TEXT",
        "autonExit": "BOOLEAN",
        "autonStrategy": "TEXT",
        "canAutoLeft": "BOOLEAN",
        "canAutoMid": "BOOLEAN",
        "canAutoRight": "BOOLEAN",
        "autonL4Num": "INTEGER",
        "autonL3Num": "INTEGER",
        "autonL2Num": "INTEGER",
        "autonL1Num": "INTEGER",
        "autonUpperAlgaeDescore": "INTEGER",
        "autonLowerAlgaeDescore": "INTEGER",
        "autonProcessor": "INTEGER",
        "autonNetScore": "INTEGER",
        "kitbotType": "TEXT",
        "isModifiedKit": "BOOLEAN",
    },

    "match": {
        "form": "TEXT",
        "team": "TEXT",
        "scouter": "TEXT",
        "alliance": "TEXT",
        "match": "INTEGER",

        "startPos": "TEXT",
        "autoLeave": "BOOLEAN",
        "autoL4Scored": "INTEGER",
        "autoL3Scored": "INTEGER",
        "autoL2Scored": "INTEGER",
        "autoL1Scored": "INTEGER",
        "autoL4Missed": "INTEGER",
        "autoL3Missed": "INTEGER",
        "autoL2Missed": "INTEGER",
        "autoL1Missed": "INTEGER",
        "autoNetScored": "INTEGER",
        "autoProcessorScored": "INTEGER",
        "autoNetMissed": "INTEGER",
        "autoProcessorMissed": "INTEGER",
        "autoAlgaeDescored": "INTEGER",

        "teleL4Scored": "INTEGER",
        "teleL3Scored": "INTEGER",
        "teleL2Scored": "INTEGER",
        "teleL1Scored": "INTEGER",
        "teleL4Missed": "INTEGER",
        "teleL3Missed": "INTEGER",
        "teleL2Missed": "INTEGER",
        "teleL1Missed": "INTEGER",
        "teleNetScored": "INTEGER",
        "teleProcessorScored": "INTEGER",
        "teleNetMissed": "INTEGER",
        "teleProcessorMissed": "INTEGER",
        "teleAlgaeDescored": "INTEGER",

        "endgamePos": "TEXT",
        "climbTime": "INTEGER",
        "yellowCard": "BOOLEAN",
        "redCard": "BOOLEAN",
        "noShow": "BOOLEAN",
        "disabled": "BOOLEAN",
        "performedDefense": "BOOLEAN",
        "penalties": "INTEGER",
        "isMarkedForReview": "BOOLEAN",
        "comments": "TEXT",
    },
}

# Sidebar
# All forms MUST have a sidebar constructor
# Each constructor is written in HTML and CSS
# Jinja2 syntax is allowed and required for accessing fields
# `include_file` is a custom function that includes a file from the `templates` directory
SIDEBAR_CONSTRUCTORS = {
    "pit": """
    {{ include_file('pit.html') }}
    """,
    "match": """
    {{ include_file('match.html') }}
    """,
}

# Report
# All forms MUST have a report constructor
# Each constructor is written in HTML and CSS
# Jinja2 syntax is allowed and required for accessing fields
# `include_file` is a custom function that includes a file from the `templates` directory
REPORT_CONSTRUCTORS = {
    "pit": """
    {{ include_file('pit.html') }}
    """,
    "match": """
    {{ include_file('match.html') }}
    """,
}

# Sidebar Renderer
# 0 = Basic html text renderer, 1 = Web renderer
SIDEBAR_RENDERER = 0

# Picture Save Max Resolution
# Max resolution for saving pictures, will use original image's aspect ratio
PICTURE_SAVE_MAX_RESOLUTION = QSize(1280, 720)

# Picture Display Max Resolution
# Max resolution for displaying pictures, will use original image's aspect ratio
PICTURE_DISPLAY_MAX_RESOLUTION = QSize(350, 300)

# Picture Browser Max Resolution
# Max resolution for displaying pictures in the picture browser, will use original image's aspect ratio
PICTURE_BROWSER_MAX_RESOLUTION = QSize(250, 200)

# Image Viewer Navigator Scale
# Scale for the navigator in the image viewer window
IMAGE_VIEWER_NAVIGATOR_SCALE = 0.25

# Image Viewer Default Zoom
# Default zoom level in image viewer window
IMAGE_VIEWER_DEFAULT_ZOOM = 0.95

# Image Viewer Zoom Range
# Min/max zoom values
IMAGE_VIEWER_ZOOM_RANGE = (0.95, 3.0)

# Scanner Newline Character(s)
SCANNER_NEWLINE = "\n"

# Scanner Delimiter Character(s)
SCANNER_DELIMITER = "||"

# Enable Assignment Generator
# Whether or not to enable the assignment generator using the Statbotics API
ENABLE_ASSIGNMENT_GENERATOR = False

# Enable the ADB-powered tablet management features
ENAGLE_APPMGMT = True

# Collection app ID
COLLECTION_APP_ID = "com.mercs.scouting"

# Supported Baud Rates
# Any values *should* work, but these are the recommended defaults
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

# Serial Port Data bits
# Usually always 8 bits
DATA_BITS: typing.Final = {
    "5 Data Bits": QSerialPort.DataBits.Data5,
    "6 Data Bits": QSerialPort.DataBits.Data6,
    "7 Data Bits": QSerialPort.DataBits.Data7,
    "8 Data Bits": QSerialPort.DataBits.Data8,
}

# Serial Port Stop Bits
# Usually always 1 stop bit
STOP_BITS: typing.Final = {
    "1 Stop Bits": QSerialPort.StopBits.OneStop,
    "1.5 Stop Bits": QSerialPort.StopBits.OneAndHalfStop,
    "2 Stop Bits": QSerialPort.StopBits.TwoStop,
}

# Serial Port Parity
# Usually no parity
PARITY: typing.Final = {
    "No Parity": QSerialPort.Parity.NoParity,
    "Even Parity": QSerialPort.Parity.EvenParity,
    "Odd Parity": QSerialPort.Parity.OddParity,
    "Mark Parity": QSerialPort.Parity.MarkParity,
    "Space Parity": QSerialPort.Parity.SpaceParity,
}

# Serial Port Flow Control
# Usually no flow control
FLOW_CONTROL: typing.Final = {
    "No Flow Control": QSerialPort.FlowControl.NoFlowControl,
    "Software FC": QSerialPort.FlowControl.SoftwareControl,
    "Hardware FC": QSerialPort.FlowControl.HardwareControl,
}


# Custom theming options
# Only dark mode is supported
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
