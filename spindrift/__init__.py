"""
Spindrift - CNC Protocol Implementation Library
"""

__version__ = "0.1.0"

# Import main classes for easy access
from .cnc import (
    CNC, Position, FeedInfo, SpindleInfo, ToolInfo, LaserInfo, CNCState,
    SwitchStates, SwitchLevels, SensorStates, WorkCoordinateSystem
)
from .xmodem import XMODEMProtocol

__all__ = [
    "CNC",
    "Position",
    "FeedInfo",
    "SpindleInfo",
    "ToolInfo",
    "LaserInfo",
    "CNCState",
    "SwitchStates",
    "SwitchLevels",
    "SensorStates",
    "WorkCoordinateSystem",
    "XMODEMProtocol",
]
