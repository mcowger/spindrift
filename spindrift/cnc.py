"""
CNC Core Class - Tracks the state of the CNC mill

This module provides the core CNC class that tracks the state of the mill,
including position, feedrate, spindle speed, tool number, and other relevant state.
It can handle updates from both mock servers and real CNC machines.
"""

import re
import math
import time
from datetime import datetime
from dataclasses import dataclass, field
from typing import Optional, Dict, Any
from enum import Enum


class CNCState(Enum):
    """CNC machine states"""

    IDLE = "Idle"
    RUN = "Run"
    TOOL = "Tool"
    ALARM = "Alarm"
    HOME = "Home"
    HOLD = "Hold"
    WAIT = "Wait"
    DISABLE = "Disable"
    SLEEP = "Sleep"
    PAUSE = "Pause"
    NOT_CONNECTED = "N/A"


@dataclass
class Position:
    """Represents a position in 3D space with optional rotary axis"""

    x: float = 0.0
    y: float = 0.0
    z: float = 0.0
    a: float = 0.0
    b: float = 0.0

    def __str__(self):
        return f"X:{self.x:.4f} Y:{self.y:.4f} Z:{self.z:.4f} A:{self.a:.4f} B:{self.b:.4f}"


@dataclass
class FeedInfo:
    """Feed rate information"""

    current: float = 0.0
    target: float = 0.0
    override: int = 100

    def __str__(self):
        return f"Current:{self.current:.1f} Target:{self.target:.1f} Override:{self.override}%"


@dataclass
class SpindleInfo:
    """Spindle information"""

    current_rpm: float = 0.0
    target_rpm: float = 0.0
    override: int = 100
    vacuum_mode: int = 0
    temperature: float = 0.0
    bed_temperature: float = 0.0

    def __str__(self):
        return f"RPM:{self.current_rpm:.1f}/{self.target_rpm:.1f} Temp:{self.temperature:.1f}°C"


@dataclass
class ToolInfo:
    """Tool information"""

    current_tool: int = -1
    tool_length_offset: float = 0.0
    target_tool: int = -1

    def __str__(self):
        return f"Tool:{self.current_tool} TLO:{self.tool_length_offset:.4f} Target:{self.target_tool}"


@dataclass
class LaserInfo:
    """Laser information"""

    mode: int = 0
    state: int = 0
    testing: int = 0
    power: float = 0.0
    scale: float = 100.0

    def __str__(self):
        return f"Mode:{self.mode} State:{self.state} Power:{self.power:.1f}% Scale:{self.scale:.1f}%"


@dataclass
class WorkCoordinateSystem:
    """Work coordinate system information"""

    active_wcs: str = "G54"
    g54: Position = field(default_factory=Position)
    g55: Position = field(default_factory=Position)
    g56: Position = field(default_factory=Position)
    g57: Position = field(default_factory=Position)
    g58: Position = field(default_factory=Position)
    g59: Position = field(default_factory=Position)


@dataclass
class SwitchStates:
    """Switch states from diagnose command"""

    spindle: int = 0
    spindle_fan: int = 0
    vacuum: int = 0
    light: int = 0
    tool_sensor_pwr: int = 0
    air: int = 0
    wp_charge_pwr: int = 0
    laser: int = 0

    def __str__(self):
        return f"Spindle:{self.spindle} Fan:{self.spindle_fan} Vacuum:{self.vacuum} Light:{self.light}"


@dataclass
class SwitchLevels:
    """Switch level values from diagnose command"""

    spindle: int = 0
    spindle_fan: int = 0
    vacuum: int = 0
    laser: int = 0

    def __str__(self):
        return f"Spindle:{self.spindle} Fan:{self.spindle_fan} Vacuum:{self.vacuum} Laser:{self.laser}"


@dataclass
class SensorStates:
    """Sensor states from diagnose command"""

    # Endstop sensors
    x_min: int = 0
    x_max: int = 0
    y_min: int = 0
    y_max: int = 0
    z_max: int = 0
    cover: int = 0

    # Probe sensors
    probe: int = 0
    calibrate: int = 0

    # ATC sensors
    atc_home: int = 0
    tool_sensor: int = 0

    # Emergency stop
    e_stop: int = 0

    def __str__(self):
        return f"Endstops(X:{self.x_min}/{self.x_max} Y:{self.y_min}/{self.y_max} Z:{self.z_max}) Probe:{self.probe} E-Stop:{self.e_stop}"


class CNC:
    """
    Core CNC class that tracks the state of the mill.

    This class handles:
    - Position tracking (machine and work coordinates)
    - Feed rate and spindle speed monitoring
    - Tool information
    - Laser state (if applicable)
    - Switch and sensor states
    - Parsing of status responses from CNC machine
    """

    def __init__(self):
        """Initialize CNC state"""
        # Machine state
        self.state = CNCState.NOT_CONNECTED

        # Position information
        self.machine_position = Position()
        self.work_position = Position()
        self.work_coordinate_offset = Position()

        # Motion information
        self.feed_info = FeedInfo()
        self.spindle_info = SpindleInfo()
        self.tool_info = ToolInfo()
        self.laser_info = LaserInfo()

        # Work coordinate systems
        self.wcs = WorkCoordinateSystem()

        # Additional state variables
        self.rotation_angle = 0.0
        self.active_coord_system = 0
        self.workpiece_voltage = 0.0
        self.max_delta = 0.0
        self.halt_reason = 1
        self.atc_state = 0

        # File playback information
        self.played_lines = -1
        self.played_percent = 0
        self.played_seconds = 0

        # Time tracking
        self._time_initialized: bool = False
        self._initial_epoch_time: Optional[float] = None
        self._system_time_at_init: Optional[float] = None

        # Switch and sensor states (from diagnose command)
        self.switches = SwitchStates()
        self.switch_levels = SwitchLevels()
        self.sensors = SensorStates()

    def parse_status_response(self, response: str) -> bool:
        """
        Parse status response from CNC machine (? command).

        Format: <Idle|MPos:-1.0000,-1.0000,-1.0000,0.0000,0.0000|WPos:287.6600,201.0800,78.1109,nan,0.0000|F:0.0,3000.0,100.0|S:0.0,12000.0,100.0,0,23.2,24.2|T:2,-7.208,-1|W:0.00|L:0, 0, 0, 0.0,100.0|C:2,1,0,1>

        Args:
            response: Status response string from CNC machine

        Returns:
            bool: True if parsing was successful, False otherwise
        """
        if not response or not isinstance(response, str):
            return False

        # Strip whitespace and check format
        response = response.strip()
        if not response.startswith("<") or not response.endswith(">"):
            return False

        try:
            # Remove angle brackets
            content = response[1:-1]

            # Split by pipe character
            parts = content.split("|")

            # First part is the state
            if parts:
                state_str = parts[0]
                try:
                    self.state = CNCState(state_str)
                except ValueError:
                    # Unknown state, keep as string for now
                    pass

            # Parse remaining parts
            for part in parts[1:]:
                if ":" not in part:
                    continue

                key, value = part.split(":", 1)
                self._parse_status_field(key, value)

            return True

        except Exception as e:
            # Log error in real implementation
            return False

    def _parse_status_field(self, key: str, value: str):
        """Parse individual field from status response"""
        try:
            if key == "MPos":
                # Machine position
                coords = [float(x) if x != "nan" else 0.0 for x in value.split(",")]
                self.machine_position.x = coords[0] if len(coords) > 0 else 0.0
                self.machine_position.y = coords[1] if len(coords) > 1 else 0.0
                self.machine_position.z = coords[2] if len(coords) > 2 else 0.0
                self.machine_position.a = coords[3] if len(coords) > 3 else 0.0
                self.machine_position.b = coords[4] if len(coords) > 4 else 0.0

            elif key == "WPos":
                # Work position
                coords = [float(x) if x != "nan" else 0.0 for x in value.split(",")]
                self.work_position.x = coords[0] if len(coords) > 0 else 0.0
                self.work_position.y = coords[1] if len(coords) > 1 else 0.0
                self.work_position.z = coords[2] if len(coords) > 2 else 0.0
                self.work_position.a = coords[3] if len(coords) > 3 else 0.0
                self.work_position.b = coords[4] if len(coords) > 4 else 0.0

                # Calculate work coordinate offset
                self._calculate_wco()

            elif key == "F":
                # Feed information
                feed_parts = value.split(",")
                self.feed_info.current = (
                    float(feed_parts[0]) if len(feed_parts) > 0 else 0.0
                )
                self.feed_info.target = (
                    float(feed_parts[1]) if len(feed_parts) > 1 else 0.0
                )
                self.feed_info.override = (
                    int(float(feed_parts[2])) if len(feed_parts) > 2 else 100
                )

            elif key == "S":
                # Spindle information
                spindle_parts = value.split(",")
                self.spindle_info.current_rpm = (
                    float(spindle_parts[0]) if len(spindle_parts) > 0 else 0.0
                )
                self.spindle_info.target_rpm = (
                    float(spindle_parts[1]) if len(spindle_parts) > 1 else 0.0
                )
                self.spindle_info.override = (
                    int(float(spindle_parts[2])) if len(spindle_parts) > 2 else 100
                )
                self.spindle_info.vacuum_mode = (
                    int(spindle_parts[3]) if len(spindle_parts) > 3 else 0
                )
                self.spindle_info.temperature = (
                    float(spindle_parts[4]) if len(spindle_parts) > 4 else 0.0
                )
                self.spindle_info.bed_temperature = (
                    float(spindle_parts[5]) if len(spindle_parts) > 5 else 0.0
                )

            elif key == "T":
                # Tool information
                tool_parts = value.split(",")
                self.tool_info.current_tool = (
                    int(tool_parts[0]) if len(tool_parts) > 0 else -1
                )
                self.tool_info.tool_length_offset = (
                    float(tool_parts[1]) if len(tool_parts) > 1 else 0.0
                )
                self.tool_info.target_tool = (
                    int(tool_parts[2]) if len(tool_parts) > 2 else -1
                )

            elif key == "W":
                # Workpiece voltage
                self.workpiece_voltage = float(value)

            elif key == "L":
                # Laser information
                laser_parts = value.split(",")
                self.laser_info.mode = (
                    int(laser_parts[0]) if len(laser_parts) > 0 else 0
                )
                self.laser_info.state = (
                    int(laser_parts[1]) if len(laser_parts) > 1 else 0
                )
                self.laser_info.testing = (
                    int(laser_parts[2]) if len(laser_parts) > 2 else 0
                )
                self.laser_info.power = (
                    float(laser_parts[3]) if len(laser_parts) > 3 else 0.0
                )
                self.laser_info.scale = (
                    float(laser_parts[4]) if len(laser_parts) > 4 else 100.0
                )

            elif key == "P":
                # Playback information
                play_parts = value.split(",")
                self.played_lines = int(play_parts[0]) if len(play_parts) > 0 else -1
                self.played_percent = int(play_parts[1]) if len(play_parts) > 1 else 0
                self.played_seconds = int(play_parts[2]) if len(play_parts) > 2 else 0

            elif key == "A":
                # ATC state
                self.atc_state = int(value)

            elif key == "O":
                # Max delta
                self.max_delta = float(value)

            elif key == "H":
                # Halt reason
                self.halt_reason = int(value)

            elif key == "R":
                # Rotation angle
                self.rotation_angle = float(value)

            elif key == "G":
                # Active coordinate system
                self.active_coord_system = int(value)

        except (ValueError, IndexError):
            # Skip malformed fields
            pass

    def _calculate_wco(self):
        """Calculate work coordinate offset from machine and work positions"""
        # Basic calculation - may need adjustment based on rotation
        self.work_coordinate_offset.x = round(
            self.machine_position.x
            - (
                math.cos(math.radians(self.rotation_angle)) * self.work_position.x
                - math.sin(math.radians(self.rotation_angle)) * self.work_position.y
            ),
            3,
        )
        self.work_coordinate_offset.y = round(
            self.machine_position.y
            - (
                math.sin(math.radians(self.rotation_angle)) * self.work_position.x
                + math.cos(math.radians(self.rotation_angle)) * self.work_position.y
            ),
            3,
        )
        self.work_coordinate_offset.z = round(
            self.machine_position.z - self.work_position.z, 3
        )
        self.work_coordinate_offset.a = round(
            self.machine_position.a - self.work_position.a, 3
        )

    def parse_diagnose_response(self, response: str) -> bool:
        """
        Parse diagnose response from CNC machine.

        Format: {S:0,5000|L:0,0|F:1,0|V:0,1|G:0|T:0|E:0,0,0,0,0,0|P:0,0|A:1,0}

        Args:
            response: Diagnose response string from CNC machine

        Returns:
            bool: True if parsing was successful, False otherwise
        """
        if not response or not isinstance(response, str):
            return False

        # Strip whitespace and check format
        response = response.strip()
        if not response.startswith("{") or not response.endswith("}"):
            return False

        try:
            # Remove braces
            content = response[1:-1]

            # Split by pipe character
            parts = content.split("|")

            # Parse each part
            for part in parts:
                if ":" not in part:
                    continue

                key, value = part.split(":", 1)
                self._parse_diagnose_field(key, value)

            return True

        except Exception as e:
            # Log error in real implementation
            return False

    def _parse_diagnose_field(self, key: str, value: str):
        """Parse individual field from diagnose response"""
        try:
            values = [int(x) for x in value.split(",")]

            if key == "S":
                # Spindle switch and level
                self.switches.spindle = values[0] if len(values) > 0 else 0
                self.switch_levels.spindle = values[1] if len(values) > 1 else 0

            elif key == "L":
                # Laser switch and level
                self.switches.laser = values[0] if len(values) > 0 else 0
                self.switch_levels.laser = values[1] if len(values) > 1 else 0

            elif key == "F":
                # Spindle fan switch and level
                self.switches.spindle_fan = values[0] if len(values) > 0 else 0
                self.switch_levels.spindle_fan = values[1] if len(values) > 1 else 0

            elif key == "V":
                # Vacuum switch and level
                self.switches.vacuum = values[0] if len(values) > 0 else 0
                self.switch_levels.vacuum = values[1] if len(values) > 1 else 0

            elif key == "G":
                # Light switch
                self.switches.light = values[0] if len(values) > 0 else 0

            elif key == "T":
                # Tool sensor power switch
                self.switches.tool_sensor_pwr = values[0] if len(values) > 0 else 0

            elif key == "R":
                # Air switch
                self.switches.air = values[0] if len(values) > 0 else 0

            elif key == "C":
                # Workpiece charge power switch
                self.switches.wp_charge_pwr = values[0] if len(values) > 0 else 0

            elif key == "E":
                # Endstop sensors
                self.sensors.x_min = values[0] if len(values) > 0 else 0
                self.sensors.x_max = values[1] if len(values) > 1 else 0
                self.sensors.y_min = values[2] if len(values) > 2 else 0
                self.sensors.y_max = values[3] if len(values) > 3 else 0
                self.sensors.z_max = values[4] if len(values) > 4 else 0
                self.sensors.cover = values[5] if len(values) > 5 else 0

            elif key == "P":
                # Probe sensors
                self.sensors.probe = values[0] if len(values) > 0 else 0
                self.sensors.calibrate = values[1] if len(values) > 1 else 0

            elif key == "A":
                # ATC sensors
                self.sensors.atc_home = values[0] if len(values) > 0 else 0
                self.sensors.tool_sensor = values[1] if len(values) > 1 else 0

            elif key == "I":
                # E-stop sensor
                self.sensors.e_stop = values[0] if len(values) > 0 else 0

        except (ValueError, IndexError):
            # Skip malformed fields
            pass

    def parse_state_response(self, response: str) -> bool:
        """
        Parse state response from CNC machine ($G or $I command).

        Format: [G0 G54 G17 G21 G90 G94 M0 M5 M9 T0 F3000.0000 S1.0000]

        Args:
            response: State response string from CNC machine

        Returns:
            bool: True if parsing was successful, False otherwise
        """
        if not response or not isinstance(response, str):
            return False

        # Strip whitespace and check format
        response = response.strip()
        if not response.startswith("[") or not response.endswith("]"):
            return False

        try:
            # Remove brackets and split by spaces
            content = response[1:-1]
            parts = content.split()

            for part in parts:
                if part.startswith("G"):
                    # G-code modal states
                    if part in ["G54", "G55", "G56", "G57", "G58", "G59"]:
                        self.wcs.active_wcs = part
                elif part.startswith("T"):
                    # Tool number
                    try:
                        tool_num = int(part[1:])
                        self.tool_info.current_tool = tool_num
                    except ValueError:
                        pass
                elif part.startswith("F"):
                    # Feed rate
                    try:
                        feed_rate = float(part[1:])
                        self.feed_info.target = feed_rate
                    except ValueError:
                        pass
                elif part.startswith("S"):
                    # Spindle speed
                    try:
                        spindle_speed = float(part[1:])
                        self.spindle_info.target_rpm = spindle_speed
                    except ValueError:
                        pass

            return True

        except Exception as e:
            # Log error in real implementation
            return False

    # Time management methods
    def set_time(self, epoch_time: float) -> bool:
        """
        Set the CNC time using Unix epoch format.

        Args:
            epoch_time: Time in Unix epoch format (seconds since January 1, 1970 UTC)

        Returns:
            bool: True if time was set successfully, False otherwise
        """
        try:
            # Validate the epoch time (reasonable range check)
            if epoch_time < 0 or epoch_time > 2147483647:  # Max 32-bit timestamp
                return False

            # Store the initial epoch time and current system time
            self._initial_epoch_time = epoch_time
            self._system_time_at_init = time.time()
            self._time_initialized = True

            return True
        except (ValueError, TypeError):
            return False

    def get_current_time(self) -> Optional[float]:
        """
        Get the current calculated time in Unix epoch format.

        Returns:
            Optional[float]: Current time in Unix epoch format, or None if not initialized
        """
        if (
            not self._time_initialized
            or self._initial_epoch_time is None
            or self._system_time_at_init is None
        ):
            return None

        # Calculate elapsed time since initialization
        current_system_time = time.time()
        elapsed_time = current_system_time - self._system_time_at_init

        # Return the initial time plus elapsed time
        return self._initial_epoch_time + elapsed_time

    def get_current_datetime(self) -> Optional[datetime]:
        """
        Get the current calculated time as a datetime object.

        Returns:
            Optional[datetime]: Current time as datetime object, or None if not initialized
        """
        current_time = self.get_current_time()
        if current_time is None:
            return None

        try:
            return datetime.fromtimestamp(current_time)
        except (ValueError, OSError):
            return None

    def is_time_initialized(self) -> bool:
        """
        Check if time has been initialized.

        Returns:
            bool: True if time has been initialized, False otherwise
        """
        return self._time_initialized

    # Communication stub methods (to be implemented later)
    def connect(self, connection_string: str) -> bool:
        """
        Connect to CNC machine.

        Args:
            connection_string: Connection details (USB port, IP address, etc.)

        Returns:
            bool: True if connection successful, False otherwise
        """
        # Stub implementation
        self.state = CNCState.IDLE
        return True

    def disconnect(self) -> bool:
        """
        Disconnect from CNC machine.

        Returns:
            bool: True if disconnection successful, False otherwise
        """
        # Stub implementation
        self.state = CNCState.NOT_CONNECTED
        return True

    def send_command(self, command: str) -> bool:
        """
        Send command to CNC machine.

        Args:
            command: G-code or console command to send

        Returns:
            bool: True if command sent successfully, False otherwise
        """
        # Stub implementation
        return True

    def query_status(self) -> bool:
        """
        Query current status from CNC machine (? command).

        Returns:
            bool: True if query sent successfully, False otherwise
        """
        # Stub implementation
        return True

    def query_diagnose(self) -> bool:
        """
        Query diagnose information from CNC machine.

        Returns:
            bool: True if query sent successfully, False otherwise
        """
        # Stub implementation
        return True

    def home_all_axes(self) -> bool:
        """
        Home all axes ($H command).

        Returns:
            bool: True if command sent successfully, False otherwise
        """
        # Stub implementation
        return True

    def jog(
        self, axis: str, distance: float, feed_rate: Optional[float] = None
    ) -> bool:
        """
        Jog specified axis by given distance.

        Args:
            axis: Axis to jog ('X', 'Y', 'Z', 'A')
            distance: Distance to jog (positive or negative)
            feed_rate: Optional feed rate for jog

        Returns:
            bool: True if command sent successfully, False otherwise
        """
        # Stub implementation
        return True

    def set_work_coordinate(
        self,
        x: Optional[float] = None,
        y: Optional[float] = None,
        z: Optional[float] = None,
        a: Optional[float] = None,
    ) -> bool:
        """
        Set work coordinate system origin.

        Args:
            x: X coordinate (None to leave unchanged)
            y: Y coordinate (None to leave unchanged)
            z: Z coordinate (None to leave unchanged)
            a: A coordinate (None to leave unchanged)

        Returns:
            bool: True if command sent successfully, False otherwise
        """
        # Stub implementation
        return True

    def __str__(self) -> str:
        """String representation of CNC state"""
        time_info = ""
        if self._time_initialized:
            current_time = self.get_current_time()
            if current_time:
                time_info = f"Time: {int(current_time)} (epoch)\n"

        return (
            f"CNC State: {self.state.value}\n"
            f"Machine Position: {self.machine_position}\n"
            f"Work Position: {self.work_position}\n"
            f"Feed: {self.feed_info}\n"
            f"Spindle: {self.spindle_info}\n"
            f"Tool: {self.tool_info}\n"
            f"Laser: {self.laser_info}\n"
            f"Switches: {self.switches}\n"
            f"Switch Levels: {self.switch_levels}\n"
            f"Sensors: {self.sensors}\n"
            f"{time_info}".rstrip()
        )

    def get_status_dict(self) -> Dict[str, Any]:
        """Get current status as dictionary for serialization"""
        return {
            "state": self.state.value,
            "machine_position": {
                "x": self.machine_position.x,
                "y": self.machine_position.y,
                "z": self.machine_position.z,
                "a": self.machine_position.a,
                "b": self.machine_position.b,
            },
            "work_position": {
                "x": self.work_position.x,
                "y": self.work_position.y,
                "z": self.work_position.z,
                "a": self.work_position.a,
                "b": self.work_position.b,
            },
            "feed_info": {
                "current": self.feed_info.current,
                "target": self.feed_info.target,
                "override": self.feed_info.override,
            },
            "spindle_info": {
                "current_rpm": self.spindle_info.current_rpm,
                "target_rpm": self.spindle_info.target_rpm,
                "override": self.spindle_info.override,
                "temperature": self.spindle_info.temperature,
            },
            "tool_info": {
                "current_tool": self.tool_info.current_tool,
                "tool_length_offset": self.tool_info.tool_length_offset,
                "target_tool": self.tool_info.target_tool,
            },
            "laser_info": {
                "mode": self.laser_info.mode,
                "state": self.laser_info.state,
                "power": self.laser_info.power,
                "scale": self.laser_info.scale,
            },
            "switches": {
                "spindle": self.switches.spindle,
                "spindle_fan": self.switches.spindle_fan,
                "vacuum": self.switches.vacuum,
                "light": self.switches.light,
                "tool_sensor_pwr": self.switches.tool_sensor_pwr,
                "air": self.switches.air,
                "wp_charge_pwr": self.switches.wp_charge_pwr,
                "laser": self.switches.laser,
            },
            "switch_levels": {
                "spindle": self.switch_levels.spindle,
                "spindle_fan": self.switch_levels.spindle_fan,
                "vacuum": self.switch_levels.vacuum,
                "laser": self.switch_levels.laser,
            },
            "sensors": {
                "x_min": self.sensors.x_min,
                "x_max": self.sensors.x_max,
                "y_min": self.sensors.y_min,
                "y_max": self.sensors.y_max,
                "z_max": self.sensors.z_max,
                "cover": self.sensors.cover,
                "probe": self.sensors.probe,
                "calibrate": self.sensors.calibrate,
                "atc_home": self.sensors.atc_home,
                "tool_sensor": self.sensors.tool_sensor,
                "e_stop": self.sensors.e_stop,
            },
        }
