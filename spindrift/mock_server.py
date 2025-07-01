"""
Mock CNC Server

A TCP server that simulates a CNC machine by responding to commands
with canned responses based on the commands.json configuration.
"""

import asyncio
import json
import logging
import os
import re
import time
import hashlib
import io
from pathlib import Path
from typing import Dict, Any, Optional, Tuple, List

from .logging_config import setup_logging, ColoredFormatter
from .xmodem import XMODEMProtocol


def _format_multiline_log(message: str, prefix: str) -> str:
    """
    Format multi-line messages for logging with proper alignment.

    Args:
        message: The message to format (may contain newlines)
        prefix: The prefix (e.g., "RECV", "SEND") for the first line

    Returns:
        Formatted message with aligned continuation lines
    """
    if "\n" not in message:
        return f"[{ColoredFormatter.COLORS[prefix]}{prefix}{ColoredFormatter.COLORS['RESET']}]: {message}"

    lines = message.split("\n")

    # Calculate padding: [LEVEL    ] [HH:MM:SS] [PREFIX]:
    # [INFO    ] = 10 chars, [HH:MM:SS] = 10 chars, [PREFIX]: varies
    # Total base padding: 10 + 1 + 10 + 1 = 22 chars
    # Plus [prefix]: = len(prefix) + 2 brackets + 1 colon + 1 space = len(prefix) + 4
    padding_length = 22 + len(prefix) + 4
    padding = " " * padding_length

    # Format first line with full prefix
    result_lines = [
        f"[{ColoredFormatter.COLORS[prefix]}{prefix}{ColoredFormatter.COLORS['RESET']}]: {lines[0]}"
    ]

    # Format continuation lines with padding
    for line in lines[1:]:
        result_lines.append(f"{padding}{line}")

    return "\n".join(result_lines)


class MockCNCServer:
    """Mock CNC server that responds to commands with canned responses."""

    def __init__(self, host: str = "localhost", port: int = 2222):
        self.host = host
        self.port = port
        self.commands = self._load_commands()
        self.active_connection = None
        self.logger = logging.getLogger(__name__)

        # Time tracking
        self._time_initialized = False
        self._initial_epoch_time = None
        self._system_time_at_init = None

        # Virtual filesystem
        self.virtual_files = self._load_virtual_files()
        self.connection_cwd = {}  # Per-connection current working directory

    def _load_commands(self) -> Dict[str, Any]:
        """Load command definitions from commands.json."""
        commands_file = Path(__file__).parent.parent / "artifacts" / "commands.json"
        with open(commands_file, "r") as f:
            return json.load(f)

    def _load_virtual_files(self) -> Dict[str, Dict[str, Any]]:
        """Load virtual filesystem from virtual_files.json."""
        virtual_files_file = (
            Path(__file__).parent.parent / "artifacts" / "virtual_files.json"
        )
        try:
            with open(virtual_files_file, "r") as f:
                files_data = json.load(f)
                # Handle both array format and object format
                if isinstance(files_data, list):
                    # Array format - convert to dict keyed by path
                    return {file_info["path"]: file_info for file_info in files_data}
                elif isinstance(files_data, dict) and "files" in files_data:
                    # Object format with "files" key
                    return {
                        file_info["path"]: file_info
                        for file_info in files_data["files"]
                    }
                else:
                    # Direct dict format
                    return files_data
        except (FileNotFoundError, json.JSONDecodeError, KeyError) as e:
            self.logger.warning(f"Could not load virtual files: {e}")
            return {}

    def _parse_command(
        self, command_line: str
    ) -> Tuple[Optional[str], Optional[Dict[str, Any]]]:
        """Parse a command line and return the command key and definition."""
        command_line = command_line.strip()

        # Check host commands first (they have specific patterns)
        for cmd_key, cmd_def in self.commands.get("host_commands", {}).items():
            if command_line.startswith(cmd_key):
                return cmd_key, cmd_def

        # Check console commands
        cmd_parts = command_line.split()
        if cmd_parts:
            base_cmd = cmd_parts[0].lower()
            for cmd_key, cmd_def in self.commands.get("console_commands", {}).items():
                if cmd_key.lower() == base_cmd:
                    return cmd_key, cmd_def

        # Check G-codes (case insensitive)
        g_match = re.match(r"^(G\d+(?:\.\d+)?)", command_line.upper())
        if g_match:
            g_code = g_match.group(1)
            if g_code in self.commands.get("g_codes", {}):
                return g_code, self.commands["g_codes"][g_code]

        # Check M-codes (case insensitive)
        m_match = re.match(r"^(M\d+(?:\.\d+)?)", command_line.upper())
        if m_match:
            m_code = m_match.group(1)
            if m_code in self.commands.get("m_codes", {}):
                return m_code, self.commands["m_codes"][m_code]

        return None, None

    def _set_time(self, epoch_time: float) -> bool:
        """Set the server time using Unix epoch format."""
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

    def _get_current_time(self) -> Optional[float]:
        """Get the current calculated time in Unix epoch format."""
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

    # Virtual filesystem utility methods
    def _get_connection_cwd(self, client_addr: str) -> str:
        """Get current working directory for a connection."""
        return self.connection_cwd.get(client_addr, "/")

    def _set_connection_cwd(self, client_addr: str, path: str) -> None:
        """Set current working directory for a connection."""
        self.connection_cwd[client_addr] = path

    def _normalize_path(self, path: str, client_addr: str) -> str:
        """Normalize a path (resolve relative paths, clean up)."""
        if not path.startswith("/"):
            # Relative path - resolve against current working directory
            cwd = self._get_connection_cwd(client_addr)
            path = os.path.join(cwd, path)

        # Normalize the path (remove . and .. components)
        return os.path.normpath(path)

    def _get_directory_contents(self, dir_path: str) -> List[str]:
        """Get contents of a directory from virtual filesystem."""
        dir_path = dir_path.rstrip("/")
        if dir_path == "":
            dir_path = "/"

        contents = set()

        for file_path in self.virtual_files.keys():
            # Check if this file is in the requested directory
            if file_path.startswith(dir_path + "/") or (
                dir_path == "/" and file_path.startswith("/")
            ):
                # Get the relative path from the directory
                if dir_path == "/":
                    relative_path = file_path[1:]  # Remove leading /
                else:
                    relative_path = file_path[
                        len(dir_path) + 1 :
                    ]  # Remove dir_path + /

                # Get the first component (file or subdirectory name)
                if "/" in relative_path:
                    # This is a subdirectory
                    subdir_name = relative_path.split("/")[0]
                    contents.add(subdir_name + "/")
                else:
                    # This is a file in the directory
                    contents.add(relative_path)

        return sorted(list(contents))

    def _file_exists(self, file_path: str) -> bool:
        """Check if a file exists in the virtual filesystem."""
        return file_path in self.virtual_files

    def _directory_exists(self, dir_path: str) -> bool:
        """Check if a directory exists in the virtual filesystem."""
        dir_path = dir_path.rstrip("/")
        if dir_path == "":
            return True  # Root directory always exists

        # Check if any file starts with this directory path
        for file_path in self.virtual_files.keys():
            if file_path.startswith(dir_path + "/"):
                return True
        return False

    def _handle_time_command(self, command_line: str, cmd_def: Dict[str, Any]) -> str:
        """Handle the time command - either set time or query current time."""
        # Check if this is a time setting command (has = and a number)
        if "=" in command_line:
            # Extract the time value from command like "time = 1751357510"
            try:
                parts = command_line.split("=")
                if len(parts) == 2:
                    time_str = parts[1].strip()
                    epoch_time = float(time_str)

                    if self._set_time(epoch_time):
                        self.logger.info(f"Time set to {epoch_time} (epoch)")
                        return ""  # Empty response as per commands.json
                    else:
                        return "ERROR: Invalid time value"
                else:
                    return "ERROR: Invalid time format"
            except (ValueError, IndexError):
                return "ERROR: Invalid time format"
        else:
            # This is a time query - return current time
            current_time = self._get_current_time()
            if current_time is not None:
                # Return time in epoch format as integer
                return str(int(current_time))
            else:
                return "ERROR: Time not initialized"

    def _handle_filesystem_command(
        self, command_line: str, cmd_key: str, client_addr: str
    ) -> str:
        """Handle filesystem commands (ls, pwd, cd, cat, mv, rm)."""
        parts = command_line.split()

        if cmd_key == "ls":
            return self._handle_ls_command(parts, client_addr)
        elif cmd_key == "pwd":
            return self._handle_pwd_command(client_addr)
        elif cmd_key == "cd":
            return self._handle_cd_command(parts, client_addr)
        elif cmd_key == "cat":
            return self._handle_cat_command(parts, client_addr)
        elif cmd_key == "mv":
            return self._handle_mv_command(parts, client_addr)
        elif cmd_key == "rm":
            return self._handle_rm_command(parts, client_addr)
        else:
            return "ERROR: Unknown filesystem command"

    def _handle_ls_command(self, parts: List[str], client_addr: str) -> str:
        """Handle ls command."""
        show_sizes = "-s" in parts

        # Find the directory path (skip command and flags)
        dir_path = None
        for part in parts[1:]:  # Skip 'ls'
            if not part.startswith("-"):
                dir_path = part
                break

        if dir_path is None:
            dir_path = self._get_connection_cwd(client_addr)
        else:
            dir_path = self._normalize_path(dir_path, client_addr)

        if not self._directory_exists(dir_path):
            return f"ERROR: Directory not found: {dir_path}"

        contents = self._get_directory_contents(dir_path)
        if not contents:
            return ""  # Empty directory

        if show_sizes:
            # Include file sizes
            result_lines = []
            for item in contents:
                if item.endswith("/"):
                    # Directory - no size
                    result_lines.append(item)
                else:
                    # File - include size
                    file_path = self._normalize_path(
                        os.path.join(dir_path, item), client_addr
                    )
                    if file_path in self.virtual_files:
                        size = self.virtual_files[file_path]["size"]
                        result_lines.append(f"{item} ({size} bytes)")
                    else:
                        result_lines.append(item)
            return "\n".join(result_lines)
        else:
            return "\n".join(contents)

    def _handle_pwd_command(self, client_addr: str) -> str:
        """Handle pwd command."""
        return self._get_connection_cwd(client_addr)

    def _handle_cd_command(self, parts: List[str], client_addr: str) -> str:
        """Handle cd command."""
        if len(parts) < 2:
            return "ERROR: cd requires a directory path"

        new_path = self._normalize_path(parts[1], client_addr)

        if not self._directory_exists(new_path):
            return f"ERROR: Directory not found: {new_path}"

        self._set_connection_cwd(client_addr, new_path)
        return ""  # cd command returns empty response per commands.json

    def _handle_cat_command(self, parts: List[str], client_addr: str) -> str:
        """Handle cat command."""
        if len(parts) < 2:
            return "ERROR: cat requires a file path"

        file_path = self._normalize_path(parts[1], client_addr)

        if not self._file_exists(file_path):
            return f"ERROR: File not found: {file_path}"

        file_info = self.virtual_files[file_path]
        contents = file_info["contents"]

        # Handle optional line limit
        if len(parts) >= 3:
            try:
                limit = int(parts[2])
                lines = contents.split("\n")
                if limit > 0 and limit < len(lines):
                    contents = "\n".join(lines[:limit])
            except ValueError:
                pass  # Ignore invalid limit, show full file

        return contents

    def _handle_mv_command(self, parts: List[str], client_addr: str) -> str:
        """Handle mv command."""
        if len(parts) < 3:
            return "ERROR: mv requires source and destination paths"

        source_path = self._normalize_path(parts[1], client_addr)
        dest_path = self._normalize_path(parts[2], client_addr)

        if not self._file_exists(source_path):
            return f"ERROR: Source file not found: {source_path}"

        # Move the file in virtual filesystem
        file_info = self.virtual_files[source_path].copy()
        file_info["path"] = dest_path

        # Update the virtual filesystem
        del self.virtual_files[source_path]
        self.virtual_files[dest_path] = file_info

        return "ok"

    def _handle_rm_command(self, parts: List[str], client_addr: str) -> str:
        """Handle rm command."""
        if len(parts) < 2:
            return "ERROR: rm requires a file path"

        file_path = self._normalize_path(parts[1], client_addr)

        if not self._file_exists(file_path):
            return f"ERROR: File not found: {file_path}"

        # Remove the file from virtual filesystem
        del self.virtual_files[file_path]

        return "ok"

    async def _handle_xmodem_command(
        self,
        command_line: str,
        cmd_key: str,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
        client_addr: str,
    ) -> str:
        """Handle XMODEM upload/download commands."""
        parts = command_line.split()

        if len(parts) < 2:
            return f"ERROR: {cmd_key} requires a filename"

        filename = parts[1]
        normalized_path = self._normalize_path(filename, client_addr)

        self.logger.info(f"Starting XMODEM {cmd_key} for file: {normalized_path}")

        # Create blocking I/O adapters for XMODEM protocol
        def getc(size: int, timeout: float = 1.0) -> Optional[bytes]:
            """Blocking read adapter for XMODEM protocol."""
            try:
                # Use asyncio.run_coroutine_threadsafe to run async code in blocking context
                loop = asyncio.get_event_loop()
                future = asyncio.ensure_future(
                    asyncio.wait_for(reader.read(size), timeout)
                )
                data = loop.run_until_complete(future)
                if len(data) == size:
                    return data
                else:
                    self.logger.debug(
                        f"getc: requested {size} bytes, got {len(data)} bytes"
                    )
                    return None
            except asyncio.TimeoutError:
                self.logger.debug(
                    f"getc: timeout after {timeout}s waiting for {size} bytes"
                )
                return None
            except Exception as e:
                self.logger.error(f"getc error: {e}")
                return None

        def putc(data: bytes, timeout: float = 1.0) -> Optional[int]:
            """Blocking write adapter for XMODEM protocol."""
            try:
                loop = asyncio.get_event_loop()
                writer.write(data)
                future = asyncio.ensure_future(
                    asyncio.wait_for(writer.drain(), timeout)
                )
                loop.run_until_complete(future)
                self.logger.debug(f"putc: sent {len(data)} bytes")
                return len(data)
            except asyncio.TimeoutError:
                self.logger.debug(
                    f"putc: timeout after {timeout}s sending {len(data)} bytes"
                )
                return None
            except Exception as e:
                self.logger.error(f"putc error: {e}")
                return None

        # Create XMODEM protocol instance
        self.logger.debug("Creating XMODEM protocol instance in 8K mode")
        xmodem = XMODEMProtocol(getc, putc, mode="xmodem8k")

        try:
            if cmd_key == "upload":
                return await self._handle_upload(xmodem, normalized_path, client_addr)
            elif cmd_key == "download":
                return await self._handle_download(xmodem, normalized_path, client_addr)
        except Exception as e:
            self.logger.error(f"XMODEM {cmd_key} error: {e}")
            return f"ERROR: {cmd_key} failed - {str(e)}"

        return ""

    async def _handle_upload(
        self, xmodem: XMODEMProtocol, filepath: str, client_addr: str
    ) -> str:
        """Handle file upload using XMODEM protocol."""
        self.logger.info(f"Starting XMODEM upload receive for: {filepath}")
        self.logger.debug(f"Upload initiated by client: {client_addr}")

        # Create in-memory stream to receive file data
        file_stream = io.BytesIO()

        # Start XMODEM receive operation (blocking)
        self.logger.debug("Beginning XMODEM receive operation (blocking)")
        result = xmodem.receive_file(file_stream, md5_hash="", retry=10)
        self.logger.debug(f"XMODEM receive completed with result: {result}")

        if result is None:
            self.logger.error(f"Upload failed for {filepath}")
            return "ERROR: Upload failed"
        elif result == -1:
            self.logger.info(f"Upload canceled by user for {filepath}")
            return "ERROR: Upload canceled"
        elif result == 0:
            self.logger.info(f"Upload canceled - MD5 match for {filepath}")
            return "Upload canceled - file already exists with same content"
        else:
            # Upload successful, add file to virtual filesystem
            file_data = file_stream.getvalue()
            file_stream.close()

            # Calculate MD5 for the uploaded file
            md5_hash = hashlib.md5(file_data).hexdigest()
            self.logger.debug(f"Calculated MD5 for uploaded file: {md5_hash}")

            # Add to virtual filesystem
            self._add_virtual_file(filepath, file_data, md5_hash)

            self.logger.info(
                f"Upload completed successfully: {filepath} ({result} bytes, MD5: {md5_hash})"
            )
            return ""  # Empty response for successful upload

    async def _handle_download(
        self, xmodem: XMODEMProtocol, filepath: str, client_addr: str
    ) -> str:
        """Handle file download using XMODEM protocol."""
        self.logger.info(f"Starting XMODEM download send for: {filepath}")
        self.logger.debug(f"Download requested by client: {client_addr}")

        # Check if file exists in virtual filesystem
        if filepath not in self.virtual_files:
            self.logger.error(f"Download failed: file not found - {filepath}")
            return f"ERROR: File not found: {filepath}"

        file_info = self.virtual_files[filepath]
        file_data = file_info.get("contents", "").encode("utf-8")
        md5_hash = hashlib.md5(file_data).hexdigest()

        self.logger.debug(f"File found: {len(file_data)} bytes, MD5: {md5_hash}")

        # Create stream from file data
        file_stream = io.BytesIO(file_data)

        # Start XMODEM send operation (blocking)
        self.logger.debug("Beginning XMODEM send operation (blocking)")
        result = xmodem.send_file(file_stream, md5_hash, retry=10)
        file_stream.close()
        self.logger.debug(f"XMODEM send completed with result: {result}")

        if result is None:
            self.logger.error(f"Download canceled for {filepath}")
            return "ERROR: Download canceled"
        elif result is False:
            self.logger.error(f"Download failed for {filepath}")
            return "ERROR: Download failed"
        else:
            self.logger.info(
                f"Download completed successfully: {filepath} ({len(file_data)} bytes, MD5: {md5_hash})"
            )
            return ""  # Empty response for successful download

    def _add_virtual_file(self, filepath: str, data: bytes, md5_hash: str):
        """Add a file to the virtual filesystem."""
        # Convert bytes to string for storage (assuming text files for now)
        try:
            content = data.decode("utf-8")
        except UnicodeDecodeError:
            # For binary files, store as base64 or handle differently
            import base64

            content = base64.b64encode(data).decode("ascii")
            # Mark as binary file
            filepath += ".b64"

        self.virtual_files[filepath] = {
            "path": filepath,
            "size": len(data),
            "contents": content,
            "md5": md5_hash,
        }

        self.logger.info(
            f"Added file to virtual filesystem: {filepath} ({len(data)} bytes)"
        )

    def _get_response(self, cmd_def: Dict[str, Any]) -> str:
        """Get the response for a command."""
        response = cmd_def.get("response", "ok")

        # Return the response directly from the JSON data
        return response

    async def _handle_client(
        self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter
    ):
        """Handle a client connection."""
        client_addr = writer.get_extra_info("peername")
        client_addr_str = f"{client_addr[0]}:{client_addr[1]}"
        self.logger.info(f"Client connected from {client_addr}")

        # Reject concurrent connections
        if self.active_connection is not None:
            self.logger.warning(f"Rejecting concurrent connection from {client_addr}")
            writer.write(b"ERROR: Server busy, only one connection allowed\n")
            await writer.drain()
            writer.close()
            await writer.wait_closed()
            return

        self.active_connection = writer

        # Initialize connection state (reset working directory)
        self._set_connection_cwd(client_addr_str, "/")

        try:
            while True:
                # Read command from client with 10-second timeout
                try:
                    data = await asyncio.wait_for(reader.readline(), timeout=10.0)
                except asyncio.TimeoutError:
                    self.logger.info(
                        f"Client {client_addr} timed out after 10 seconds of inactivity"
                    )
                    break

                if not data:
                    break

                command_line = data.decode("utf-8").strip()
                if not command_line:
                    continue

                self.logger.info(_format_multiline_log(command_line, "RECV"))

                # Parse and process command
                cmd_key, cmd_def = self._parse_command(command_line)

                if cmd_def is None or cmd_key is None:
                    # Unknown command
                    response = "ERROR: Unknown command"
                    self.logger.warning(f"Unknown command: {command_line}")
                else:
                    # Handle special commands
                    if cmd_key == "time":
                        response = self._handle_time_command(command_line, cmd_def)
                    elif cmd_key in ["ls", "pwd", "cd", "cat", "mv", "rm"]:
                        response = self._handle_filesystem_command(
                            command_line, cmd_key, client_addr_str
                        )
                    elif cmd_key in ["upload", "download"]:
                        # XMODEM file transfer commands - these are blocking operations
                        response = await self._handle_xmodem_command(
                            command_line, cmd_key, reader, writer, client_addr_str
                        )
                    else:
                        # Get response for known command
                        response = self._get_response(cmd_def)

                    # Add artificial delay (minimum 100ms, or command-specific time)
                    delay_ms = max(100, cmd_def.get("time_ms", 100))
                    await asyncio.sleep(delay_ms / 1000.0)

                # Send response
                writer.write(f"{response}\n".encode("utf-8"))

                # Send 'ok' if required
                if cmd_def and cmd_def.get("sends_ok", False):
                    writer.write(b"ok\n")

                await writer.drain()
                self.logger.info(_format_multiline_log(response, "SEND"))

        except asyncio.CancelledError:
            self.logger.info("Connection cancelled")
        except Exception as e:
            self.logger.error(f"Error handling client: {e}")
        finally:
            self.active_connection = None
            # Clean up connection state
            if client_addr_str in self.connection_cwd:
                del self.connection_cwd[client_addr_str]
            writer.close()
            await writer.wait_closed()
            self.logger.info(f"Client {client_addr} disconnected")

    async def start(self):
        """Start the mock CNC server."""
        server = await asyncio.start_server(self._handle_client, self.host, self.port)

        addr = server.sockets[0].getsockname()
        self.logger.info(f"Mock CNC Server started on {addr[0]}:{addr[1]}")

        async with server:
            await server.serve_forever()


def main():
    """Main CLI entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="Spindrift CNC Protocol Library")
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Mock server command
    server_parser = subparsers.add_parser("mock-server", help="Run mock CNC server")
    server_parser.add_argument(
        "--host", default="localhost", help="Host to bind to (default: localhost)"
    )
    server_parser.add_argument(
        "--port", type=int, default=2222, help="Port to bind to (default: 2222)"
    )
    server_parser.add_argument(
        "--verbose", "-v", action="store_true", help="Enable verbose logging"
    )

    args = parser.parse_args()

    if args.command == "mock-server":
        # Configure logging with colored format
        log_level = logging.DEBUG if args.verbose else logging.INFO
        setup_logging(level=log_level)

        # Start mock server
        server = MockCNCServer(host=args.host, port=args.port)
        try:
            asyncio.run(server.start())
        except KeyboardInterrupt:
            print("\nServer stopped by user")
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
