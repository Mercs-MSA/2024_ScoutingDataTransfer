"""
Constant values for scouting transfer
"""

import typing
import enum

from PyQt6.QtSerialPort import QSerialPort

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

PIT_DATA_HEADER: typing.Final = [
    "form",
    "event",
    "teamNumber",
    "botLength",
    "botWidth",
    "botHeight",
    "botWeight",
    "drivebase",
    "drivebaseAlt",
    "climber",
    "climberAlt",
    "isKitbot",
    "intakeInBumper",
    "speakerScore",
    "ampScore",
    "trapScore",
    "groundPickup",
    "sourcePickup",
    "turretShoot",
    "extendShoot",
    "hasBlocker",
    "hasAutoAim",
    "hasAuton",
    "autonSpeakerNotes",
    "autonAmpNotes",
    "autonConsistency",
    "autonVersatility",
    "autonRoutes",
    "autonPrefStart",
    "autonStrat",
    "repairability",
    "maneuverability",
    "teleopStrat",
]

QUAL_DATA_HEADER: typing.Final = [
    "form",
    "event",
    "teamNumber",
    "matchNumber",
    "startingPosition",
    "hasAuton",
    "autonLeave",
    "autonCrossCenter",
    "autonAStop",
    "autonPreload",
    "autonSpeakerNotesScored",
    "autonSpeakerNotesMissed",
    "autonAmpNotesScored",
    "autonAmpNotesMissed",
    "autonWingNotes",
    "autonCenterNotes",
    "teleopFloorPickup",
    "teleopSourcePickup",
    "teleopAmpScored",
    "teleopAmpMissed",
    "teleopSpeakerScored",
    "teleopSpeakerMissed",
    "teleopDroppedNotes",
    "teleopFedNotes",
    "teleopAmps",
    "endgameClimbSpeed",
    "endgameClimbPos",
    "endgameDidTheyTrap",
    "endgameDidTheyHarmony",
    "endgameDefenseBot",
    "endgameDriverRating",
    "endgameDefenseRating",
    "endgameHighnote",
    "endgameCoOp",
    "endgameDidTheyGetACard",
    "endgameDidTheyNoShow",
    "endgameComments",
]

PLAYOFF_DATA_HEADER: typing.Final = [
    "form",
    "event",
    "teamNumber",
    "matchNumber",
    "startingPosition",
    "hasAuton",
    "autonLeave",
    "autonCrossCenter",
    "autonAStop",
    "autonPreload",
    "autonSpeakerNotesScored",
    "autonSpeakerNotesMissed",
    "autonAmpNotesScored",
    "autonAmpNotesMissed",
    "autonWingNotes",
    "autonCenterNotes",
    "teleopFloorPickup",
    "teleopSourcePickup",
    "teleopAmpScored",
    "teleopAmpMissed",
    "teleopSpeakerScored",
    "teleopSpeakerMissed",
    "teleopDroppedNotes",
    "teleopFedNotes",
    "teleopAmps",
    "endgameClimbSpeed",
    "endgameClimbPos",
    "endgameDidTheyTrap",
    "endgameDidTheyHarmony",
    "endgameDefenseBot",
    "endgameDriverRating",
    "endgameDefenseRating",
    "endgameHighnote",
    "endgameCoOp",
    "endgameDidTheyGetACard",
    "endgameDidTheyNoShow",
    "endgameComments",
]


class DataError(enum.Enum):
    """ Potential error for worker """
    DATA_MALFORMED = 0
    UNKNOWN_FORM = 1
    TEAM_NUMBER_NULL = 2
    MATCH_NUMBER_NULL = 3
