# Mock CNC Server Documentation

## Table of Contents

- [Purpose and Overview](#purpose-and-overview)
- [Getting Started](#getting-started)
- [Command System Architecture](#command-system-architecture)
- [Supported Commands](#supported-commands)
- [Virtual Filesystem](#virtual-filesystem)
- [Known Limitations and Issues](#known-limitations-and-issues)
- [Testing and Development](#testing-and-development)
- [Technical Details](#technical-details)
- [Troubleshooting](#troubleshooting)

## Purpose and Overview

The Spindrift Mock CNC Server is a comprehensive TCP server that emulates a Carvera CNC machine for development and testing purposes. It provides realistic responses to G-codes, M-codes, and console commands, making it an essential tool for CNC application development, protocol validation, and automated testing.

The server implements the complete Carvera command protocol, including filesystem operations, XMODEM file transfers, status queries, and machine control commands. It maintains a virtual filesystem with configurable files and supports multiple concurrent connections, making it ideal for testing client applications without requiring physical hardware.

## Getting Started

### Prerequisites

- Python 3.8 or higher
- Poetry package manager
- Network access to localhost (default) or specified host

### Installation and Setup

The mock server is part of the Spindrift package. Ensure you have the project dependencies installed:

```bash
poetry install
```

### Running the Server

#### Basic Startup

Start the server with default settings (localhost:2222):

```bash
poetry run spindrift mock-server
```

Expected output:

```
[INFO    ] [14:30:15] Mock CNC Server started on 127.0.0.1:2222
```

#### Custom Host and Port

Specify custom network settings:

```bash
poetry run spindrift mock-server --host 0.0.0.0 --port 8080
```

#### Verbose Logging

Enable debug-level logging for detailed command tracing:

```bash
poetry run spindrift mock-server --verbose
```

With verbose mode, you'll see detailed command and response logging:

```
[DEBUG   ] [14:30:20] [RECV]: ?
[DEBUG   ] [14:30:20] [SEND]: <Idle|MPos:-1.0000,-1.0000,-1.0000,0.0000,0.0000|...>
```

#### Help and Options

View all available options:

```bash
poetry run spindrift mock-server --help
```

### Quick Test

Test the server with a simple command using netcat:

```bash
echo "version" | nc localhost 2222
```

Expected response:

```
version = 1.0.3c1.0.6
```

## Command System Architecture

The mock server's behavior is entirely driven by the `artifacts/commands.json` configuration file, which defines all supported commands and their responses.

### Commands.json Structure

Commands are organized into four main categories:

- **g_codes**: G-code commands (G0, G1, G2, etc.)
- **m_codes**: M-code commands (M3, M5, M6, etc.)
- **console_commands**: Text-based commands (help, version, ls, etc.)
- **host_commands**: Special protocol commands ($G, $I, ?, etc.)

### Command Definition Fields

Each command can include the following fields:

| Field               | Type    | Required | Description                           | Example                             |
| ------------------- | ------- | -------- | ------------------------------------- | ----------------------------------- |
| `name`              | string  | Yes      | Human-readable command name           | "Rapid Move"                        |
| `description`       | string  | Yes      | Detailed command description          | "Move to coordinates with tool off" |
| `parameters`        | array   | No       | List of accepted parameters           | ["X", "Y", "Z", "F"]                |
| `example`           | string  | No       | Usage example                         | "G0 X10 Y5 F100"                    |
| `response`          | string  | Yes      | Server response text                  | "ok"                                |
| `modal`             | boolean | No       | Whether command affects machine state | true                                |
| `sends_ok`          | boolean | No       | Send additional "ok" after response   | false                               |
| `time_ms`           | number  | No       | Artificial delay in milliseconds      | 100                                 |
| `instant`           | boolean | No       | Process without waiting for newline   | true                                |
| `eot_terminated`    | boolean | No       | Append EOT (0x04) to response         | true                                |
| `debug_output_only` | boolean | No       | Log only at DEBUG level               | true                                |

### Boolean Field Defaults

All boolean fields default to `false` when not specified:

- `modal`: false
- `sends_ok`: false
- `instant`: false
- `eot_terminated`: false
- `debug_output_only`: false

### Example Command Definition

```json
"G0": {
  "name": "Rapid Move",
  "description": "Move to coordinates with tool off",
  "parameters": ["X", "Y", "Z", "A", "F"],
  "example": "G0 X10 Y5 F100",
  "modal": true,
  "response": "ok",
  "time_ms": 150
}
```

## Supported Commands

The mock server supports hundreds of commands across all categories. Here are the key command groups:

### G-Codes (Motion Commands)

| Command | Name                      | Description                          | Modal | EOT | Debug |
| ------- | ------------------------- | ------------------------------------ | ----- | --- | ----- |
| G0      | Rapid Move                | Move to coordinates with tool off    | ☑     | ☐   | ☐     |
| G1      | Linear Move               | Move to coordinates with tool active | ☑     | ☐   | ☐     |
| G2      | Clockwise Arc             | Clockwise circular motion            | ☐     | ☐   | ☐     |
| G3      | Counter-clockwise Arc     | Counter-clockwise motion             | ☐     | ☐   | ☐     |
| G4      | Dwell                     | Dwell for specified time             | ☐     | ☐   | ☐     |
| G10     | Set Coordinates           | Set workspace coordinates            | ☐     | ☐   | ☐     |
| G17     | XY Plane                  | Select XYZ plane                     | ☑     | ☐   | ☐     |
| G18     | XZ Plane                  | Select XZY plane                     | ☑     | ☐   | ☐     |
| G19     | YZ Plane                  | Select YZX plane                     | ☑     | ☐   | ☐     |
| G20     | Inch Mode                 | Inch mode coordinates                | ☑     | ☐   | ☐     |
| G21     | Millimeter Mode           | Millimeter mode coordinates          | ☑     | ☐   | ☐     |
| G28     | Home                      | Goto clearance position              | ☐     | ☐   | ☐     |
| G32     | Delta Calibration         | Grid probe and compensation          | ☐     | ☐   | ☐     |
| G38.2   | Probe Toward              | Probe toward workpiece               | ☐     | ☐   | ☐     |
| G38.3   | Probe Toward (No Error)   | Probe toward, no error               | ☐     | ☐   | ☐     |
| G38.4   | Probe Away                | Probe away from workpiece            | ☐     | ☐   | ☐     |
| G38.5   | Probe Away (No Error)     | Probe away, no error                 | ☐     | ☐   | ☐     |
| G53     | Machine Coordinate System | Execute in MCS coordinates           | ☐     | ☐   | ☐     |
| G54     | Work Coordinate System 1  | Use workspace G54                    | ☑     | ☐   | ☐     |
| G55     | Work Coordinate System 2  | Use workspace G55                    | ☑     | ☐   | ☐     |
| G56     | Work Coordinate System 3  | Use workspace G56                    | ☑     | ☐   | ☐     |
| G57     | Work Coordinate System 4  | Use workspace G57                    | ☑     | ☐   | ☐     |
| G58     | Work Coordinate System 5  | Use workspace G58                    | ☑     | ☐   | ☐     |
| G59     | Work Coordinate System 6  | Use workspace G59                    | ☑     | ☐   | ☐     |
| G90     | Absolute Mode             | Absolute positioning                 | ☑     | ☐   | ☐     |
| G91     | Relative Mode             | Relative positioning                 | ☑     | ☐   | ☐     |
| G92     | Set Position              | Set current position                 | ☐     | ☐   | ☐     |
| G92.1   | Clear G92 Offsets         | Clear G92 and G30 offsets            | ☐     | ☐   | ☐     |
| G92.4   | Set Machine Position      | Manually set homing                  | ☐     | ☐   | ☐     |

### M-Codes (Machine Commands)

| Command | Name                 | Description                       | Modal | EOT | Debug |
| ------- | -------------------- | --------------------------------- | ----- | --- | ----- |
| M3      | Spindle On (CW)      | Start spindle clockwise           | ☐     | ☐   | ☐     |
| M5      | Spindle Off          | Stop spindle                      | ☐     | ☐   | ☐     |
| M6      | Auto Tool Change     | Auto tool change                  | ☐     | ☐   | ☐     |
| M7      | Starts the airflow   | Start airflow                     | ☐     | ☐   | ☐     |
| M9      | Set Position         | Stop airflow                      | ☐     | ☐   | ☐     |
| M30     | End of the program   | End program, no action            | ☐     | ☐   | ☐     |
| M105    | Read Temperature     | Read spindle temperature          | ☐     | ☐   | ☐     |
| M220    | Set Feed Rate Scale  | Set feed rate override            | ☐     | ☐   | ☐     |
| M223    | Set Spindle Scale    | Set spindle speed override        | ☐     | ☐   | ☐     |
| M321    | Laser Mode On        | Enable laser mode                 | ☐     | ☐   | ☐     |
| M322    | Laser Mode Off       | Disable laser mode                | ☐     | ☐   | ☐     |
| M323    | Laser Test On        | Enable laser test mode            | ☐     | ☐   | ☐     |
| M324    | Laser Test Off       | Disable laser test mode           | ☐     | ☐   | ☐     |
| M325    | Set Laser Scale      | Set laser power scale             | ☐     | ☐   | ☐     |
| M331    | Vacuum Mode On       | Enable vacuum mode                | ☐     | ☐   | ☐     |
| M332    | Vacuum Mode Off      | Disable vacuum mode               | ☐     | ☐   | ☐     |
| M370    | Clear Auto Leveling  | Clear auto leveling data          | ☐     | ☐   | ☐     |
| M471    | Pair Workpiece       | Pair workpiece sensor             | ☐     | ☐   | ☐     |
| M490.1  | Clamp Tool           | Clamp tool in spindle             | ☐     | ☐   | ☐     |
| M490.2  | Unclamp Tool         | Unclamp tool from spindle         | ☐     | ☐   | ☐     |
| M491    | Calibrate Tool       | Calibrate tool length             | ☐     | ☐   | ☐     |
| M493.2  | Set Tool             | Set current tool without changing | ☐     | ☐   | ☐     |
| M495    | Auto Level/Probe     | Auto leveling and probing         | ☐     | ☐   | ☐     |
| M495.3  | XYZ Probe            | 3-axis probe operation            | ☐     | ☐   | ☐     |
| M496.1  | Go to Clearance      | Move to clearance position        | ☐     | ☐   | ☐     |
| M496.2  | Go to Work Origin    | Move to work origin               | ☐     | ☐   | ☐     |
| M496.3  | Go to Anchor1        | Move to anchor point 1            | ☐     | ☐   | ☐     |
| M496.4  | Go to Anchor2        | Move to anchor point 2            | ☐     | ☐   | ☐     |
| M496.5  | Go to Path Origin    | Move to path origin               | ☐     | ☐   | ☐     |
| M801    | Vacuum On            | Turn on vacuum                    | ☐     | ☐   | ☐     |
| M802    | Vacuum Off           | Turn off vacuum                   | ☐     | ☐   | ☐     |
| M811    | Spindle Fan On       | Turn on spindle fan               | ☐     | ☐   | ☐     |
| M812    | Spindle Fan Off      | Turn off spindle fan              | ☐     | ☐   | ☐     |
| M821    | Light On             | Turn on work light                | ☐     | ☐   | ☐     |
| M822    | Light Off            | Turn off work light               | ☐     | ☐   | ☐     |
| M831    | Tool Sensor On       | Turn on tool sensor               | ☐     | ☐   | ☐     |
| M832    | Tool Sensor Off      | Turn off tool sensor              | ☐     | ☐   | ☐     |
| M841    | Workpiece Charge On  | Turn on workpiece charge          | ☐     | ☐   | ☐     |
| M842    | Workpiece Charge Off | Turn off workpiece charge         | ☐     | ☐   | ☐     |
| M851    | External Control On  | Turn on external control          | ☐     | ☐   | ☐     |
| M852    | External Control Off | Turn off external control         | ☐     | ☐   | ☐     |

### Console Commands

| Command    | Name                    | Description                  | Modal | EOT | Debug |
| ---------- | ----------------------- | ---------------------------- | ----- | --- | ----- |
| help       | Help                    | Give a list of commands      | ☐     | ☐   | ☐     |
| version    | Version                 | Display firmware version     | ☐     | ☐   | ☐     |
| mem        | Memory Info             | Returns RAM usage info       | ☐     | ☐   | ☐     |
| ls         | List Files              | List files in directory      | ☐     | ☑   | ☐     |
| cd         | Change Directory        | Change current folder        | ☐     | ☐   | ☐     |
| pwd        | Print Working Directory | Show current folder          | ☐     | ☐   | ☐     |
| cat        | Display File            | Output file contents         | ☐     | ☑   | ☐     |
| rm         | Remove File             | Remove a file                | ☐     | ☑   | ☐     |
| mv         | Move File               | Move/rename a file           | ☐     | ☑   | ☐     |
| mkdir      | Make Directory          | Create a new directory       | ☐     | ☑   | ☐     |
| play       | Play File               | Execute file line by line    | ☐     | ☐   | ☐     |
| progress   | Show Progress           | Display play command status  | ☐     | ☐   | ☐     |
| abort      | Abort                   | Stop execution of play       | ☐     | ☐   | ☐     |
| suspend    | Suspend                 | Suspend job in progress      | ☐     | ☐   | ☐     |
| resume     | Resume                  | Resume suspended job         | ☐     | ☐   | ☐     |
| reset      | Reset                   | Reset smoothie               | ☐     | ☐   | ☐     |
| config-get | Get Config              | Output config setting value  | ☐     | ☐   | ☐     |
| config-set | Set Config              | Change config setting value  | ☐     | ☐   | ☐     |
| time       | Set Time                | Set time in unix epoch       | ☐     | ☐   | ☐     |
| model      | Device                  | Return device model          | ☐     | ☐   | ☐     |
| ftype      | File Type               | Upload/download file format  | ☐     | ☐   | ☐     |
| upload     | Upload File             | Upload via XMODEM protocol   | ☐     | ☐   | ☐     |
| download   | Download File           | Download via XMODEM protocol | ☐     | ☐   | ☐     |

### Host Commands

| Command | Name                | Description              | Modal | EOT | Debug | Instant | Sends OK |
| ------- | ------------------- | ------------------------ | ----- | --- | ----- | ------- | -------- |
| $G      | Get State           | Get GCODE State          | ☐     | ☐   | ☐     | ☐       | ☑        |
| $I      | Get State (Instant) | Same as $G but instant   | ☐     | ☐   | ☐     | ☑       | ☐        |
| $H      | Home                | Home all axes            | ☐     | ☐   | ☐     | ☐       | ☑        |
| $J      | Jog                 | Issue jog command        | ☐     | ☐   | ☐     | ☐       | ☑        |
| $S      | Switch State        | Return switch states     | ☐     | ☐   | ☐     | ☐       | ☐        |
| $X      | Release Alarm       | Release ALARM state      | ☐     | ☐   | ☐     | ☐       | ☐        |
| $#      | Get WCS             | Return WCS states/values | ☐     | ☐   | ☐     | ☐       | ☑        |
| ?       | Status Query        | Machine status           | ☐     | ☐   | ☑     | ☑       | ☐        |
| !       | Feed Hold           | Pause/hold operation     | ☐     | ☐   | ☐     | ☐       | ☑        |
| ~       | Cycle Start         | Resume from feed hold    | ☐     | ☐   | ☐     | ☐       | ☑        |
| ^X      | Soft Reset          | Soft reset (Control-X)   | ☐     | ☐   | ☐     | ☐       | ☑        |

**Legend:**

- ☑ = Feature enabled
- ☐ = Feature disabled
- Modal = Command affects machine state
- EOT = Response terminated with ASCII EOT (0x04)
- Debug = Logged only at DEBUG level
- Instant = Processed without waiting for newline

## Virtual Filesystem

The mock server implements a non-persistent virtual filesystem that simulates the SD card and internal storage of a real Carvera machine.

### Filesystem Structure

```
/
├── sd/                    # SD card mount point
│   ├── config.txt        # Machine configuration file
│   └── gcodes/           # G-code files directory
│       ├── samplegcode.nc
│       ├── T1.gcode
│       └── T2.cnc
└── ud/                   # Internal storage
    └── temp/
        └── temp_file.tmp
```

### File Metadata Structure

Each file in the virtual filesystem contains:

```json
{
  "path": "/sd/config.txt",
  "size": 2886,
  "contents": "file content here...",
  "md5": "calculated_hash",
  "timestamp": "20250624132627",
  "timestamp_parsed": "datetime_object"
}
```

### Directory Representation

Directories are stored with special metadata:

- **size**: -1 (indicates directory)
- **path**: Ends with trailing slash (e.g., "/sd/gcodes/")
- **contents**: Empty string
- **md5**: Empty string

### Supported Filesystem Commands

#### ls [directory] [-s]

List directory contents. Use `-s` flag to show file sizes.

```bash
ls /sd
ls -s /sd/gcodes
```

#### pwd

Show current working directory.

```bash
pwd
```

#### cd [directory]

Change current working directory.

```bash
cd /sd
cd gcodes
cd ..
```

#### cat [file] [limit]

Display file contents. Optional limit parameter for line count.

```bash
cat /sd/config.txt
cat /sd/config.txt 10
```

#### mv [source] [destination]

Move or rename files and directories.

```bash
mv oldname.gcode newname.gcode
mv /sd/file.txt /ud/file.txt
```

#### rm [file]

Remove files from the filesystem.

```bash
rm /sd/old_file.gcode
```

#### mkdir [directory]

Create new directories.

```bash
mkdir /sd/new_folder
```

### XMODEM File Transfer

The server supports XMODEM protocol for file uploads and downloads:

#### upload [filename]

Upload a file using XMODEM protocol:

```bash
upload /sd/new_file.gcode
```

#### download [filename]

Download a file using XMODEM protocol:

```bash
download /sd/config.txt
```

**Note**: XMODEM operations use 8K block mode and run in separate threads to avoid blocking the main server.

## Known Limitations and Issues

While the mock server provides comprehensive CNC machine emulation, there are some known limitations:

### Filesystem Operations

- **mkdir display**: Directory creation works correctly, but new directories may not immediately appear in `ls` output until server restart
- **File persistence**: Virtual filesystem is non-persistent - all changes are lost when the server restarts

### XMODEM File Transfer

- **Upload functionality**: XMODEM uploads work correctly and files are added to the virtual filesystem
- **Download functionality**: XMODEM downloads function properly but may generate harmless error messages in server logs
- **Compression handling**: The server declines the `lz` compression option during XMODEM negotiations

### G-code Simulation

- **Static coordinates**: G-code movement commands are accepted and acknowledged but do not update machine coordinates
- **No motion simulation**: The server does not simulate actual machine movement or calculate new positions
- **Tool state**: Tool changes and spindle commands are acknowledged but do not affect machine status

### Machine Status

- **Static status**: The status query (`?`) always returns the same machine state regardless of commands sent
- **No state tracking**: Machine modes (G90/G91, G20/G21, etc.) are not tracked or reflected in status responses
- **Fixed coordinates**: Position values remain constant at predefined values

### Connection Handling

- **Connection limit**: Maximum of 2 concurrent connections (matches real hardware)
- **Timeout behavior**: 10-second inactivity timeout may be aggressive for some testing scenarios

## Testing and Development

### Unit Tests

Run the complete test suite:

```bash
poetry run pytest
```

Run specific test categories:

```bash
poetry run pytest tests/test_mock_server.py
poetry run pytest tests/test_xmodem.py
```

### Manual Testing Tools

#### Using netcat (nc)

Quick command testing:

```bash
echo "version" | nc localhost 2222
echo "ls /sd" | nc localhost 2222
echo "?" | nc localhost 2222
```

#### Using telnet

Interactive session:

```bash
telnet localhost 2222
```

Then type commands interactively:

```
version
ls /sd
pwd
cd /sd/gcodes
ls
```

#### Multiple commands in one session:

```bash
(echo "version"; echo "ls /sd"; echo "pwd") | nc localhost 2222
```

### Application Testing

#### Carvera Controller App

The official Carvera controller application will successfully connect to and interact with the mock server:

1. Start the mock server: `poetry run spindrift mock-server`
2. Configure the controller app to connect to `localhost:2222`
3. The app should connect successfully and display machine status
4. Most controller functions will work, including file browsing and command sending

#### Custom CNC Applications

The mock server is ideal for testing custom CNC applications:

- **Protocol validation**: Verify your application sends correct G-codes and M-codes
- **Error handling**: Test how your application handles various error responses
- **File operations**: Test filesystem browsing and file management features
- **Connection management**: Verify proper connection handling and timeout behavior

### Debugging and Troubleshooting

#### Verbose Logging

Enable detailed logging to see all command and response traffic:

```bash
poetry run spindrift mock-server --verbose
```

This shows:

- All received commands with `[RECV]` prefix
- All sent responses with `[SEND]` prefix
- Debug-level information about internal operations
- XMODEM protocol details during file transfers

#### Log Format Interpretation

```
[INFO    ] [14:30:15] Mock CNC Server started on 127.0.0.1:2222
[INFO    ] [14:30:20] Client connected from ('127.0.0.1', 52341)
[INFO    ] [14:30:20] [RECV]: version
[INFO    ] [14:30:20] [SEND]: version = 1.0.3c1.0.6
[DEBUG   ] [14:30:25] [RECV]: ?
[DEBUG   ] [14:30:25] [SEND]: <Idle|MPos:-1.0000,-1.0000,-1.0000...>
```

- **[INFO]**: Standard operations and important events
- **[DEBUG]**: Detailed command tracing (only with `--verbose`)
- **[RECV]**: Commands received from clients
- **[SEND]**: Responses sent to clients
- **Timestamps**: All log entries include precise timestamps

#### Common Issues and Solutions

**Connection Refused**

- Ensure the server is running: `poetry run spindrift mock-server`
- Check if port 2222 is available: `netstat -an | grep 2222`
- Try a different port: `--port 8080`

**Commands Not Recognized**

- Verify command syntax matches examples in this documentation
- Check `artifacts/commands.json` for exact command definitions
- Use verbose mode to see what the server receives

**XMODEM Transfer Issues**

- XMODEM operations are complex - check server logs for detailed error information
- Ensure your XMODEM client uses 8K block mode
- File transfer errors are often due to client-side XMODEM implementation issues

**Timeout Disconnections**

- Server disconnects after 10 seconds of inactivity (matches real hardware)
- Send periodic status queries (`?`) to keep connection alive
- This behavior is intentional and cannot be disabled

## Technical Details

### Connection Management

- **Maximum Connections**: 2 concurrent connections (matches real Carvera hardware)
- **Connection Timeout**: 10-second inactivity timeout with automatic disconnect
- **Connection Tracking**: Server maintains active connection set for proper cleanup
- **Error Handling**: Graceful handling of client disconnections and network errors

### Protocol Implementation

- **Line Endings**: Server uses LF (`\n`) line endings for all responses
- **EOT Termination**: Specific commands (ls, rm, cat, mv, mkdir) append ASCII EOT (0x04) character
- **Command Parsing**: Case-insensitive G-codes and M-codes, exact-match console commands
- **Response Timing**: Configurable delays per command (minimum 100ms, default from commands.json)

### Threading Model

- **Main Server**: Asyncio-based TCP server for handling multiple connections
- **XMODEM Operations**: Separate threads for blocking file transfer operations
- **Thread Safety**: Proper synchronization between async server and blocking XMODEM code
- **Event Loop Management**: Uses `asyncio.to_thread()` and `asyncio.run_coroutine_threadsafe()`

### Memory and Performance

- **Virtual Filesystem**: In-memory file storage with configurable file contents
- **Command Lookup**: Efficient dictionary-based command resolution
- **Logging**: Configurable log levels with colored output formatting
- **Resource Cleanup**: Proper cleanup of connections, threads, and file handles

### Network Configuration

- **Default Binding**: localhost:2222 (matches real Carvera default)
- **Custom Binding**: Configurable host and port via command-line arguments
- **IPv4 Support**: Standard TCP/IPv4 socket implementation
- **Firewall Considerations**: Ensure port 2222 (or custom port) is accessible

### File System Behavior

- **Path Normalization**: Automatic path resolution and validation
- **Directory Navigation**: Per-connection working directory tracking
- **File Metadata**: Comprehensive metadata including timestamps, sizes, and MD5 hashes
- **Timestamp Format**: YYYYMMDDHHMMSS format for all file timestamps

### Logging System

- **Log Levels**: INFO (default) and DEBUG (verbose mode)
- **Colored Output**: Color-coded log levels for better readability
- **Message Formatting**: Consistent `[LEVEL] [HH:MM:SS] message` format
- **Debug Filtering**: Commands with `debug_output_only=true` log only at DEBUG level

### Configuration Files

- **commands.json**: Complete command definitions and responses
- **virtual_files.json**: Virtual filesystem initial state
- **Extensibility**: Easy to add new commands or modify existing responses

## Troubleshooting

### Performance Issues

If the server seems slow or unresponsive:

- Check system resources (CPU, memory)
- Reduce command timing delays in commands.json
- Use `--verbose` to identify bottlenecks
- Ensure no other processes are using port 2222

### Memory Usage

The server loads all virtual files into memory:

- Large files in virtual_files.json will increase memory usage
- Consider reducing file sizes for testing scenarios
- Monitor memory usage with system tools if needed

### Network Issues

For connection problems:

- Verify firewall settings allow connections to port 2222
- Test with `telnet localhost 2222` to verify basic connectivity
- Check for port conflicts with `netstat -an | grep 2222`
- Try binding to `0.0.0.0` instead of `localhost` for remote access

### Development Tips

- Use version control to track changes to commands.json and virtual_files.json
- Create separate virtual_files.json configurations for different test scenarios
- Use the `--verbose` flag during development to understand command flow
- Test with both the official Carvera app and custom clients for compatibility

---

## Summary

The Spindrift Mock CNC Server provides a comprehensive, realistic emulation of a Carvera CNC machine for development and testing purposes. With support for hundreds of commands, a virtual filesystem, XMODEM file transfers, and configurable behavior, it serves as an essential tool for CNC application development.

Key benefits:

- **No Hardware Required**: Test CNC applications without physical machine access
- **Realistic Behavior**: Matches real Carvera protocol and timing characteristics
- **Comprehensive Coverage**: Supports G-codes, M-codes, console commands, and file operations
- **Easy Configuration**: JSON-driven command definitions and responses
- **Development Friendly**: Detailed logging, error handling, and debugging features

For questions, issues, or contributions, refer to the main project documentation and issue tracker.
