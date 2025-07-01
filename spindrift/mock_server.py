"""
Mock CNC Server

A TCP server that simulates a CNC machine by responding to commands
with canned responses based on the commands.json configuration.
"""

import asyncio
import json
import logging
import re
import time
from pathlib import Path
from typing import Dict, Any, Optional, Tuple

from .logging_config import setup_logging


class MockCNCServer:
    """Mock CNC server that responds to commands with canned responses."""

    def __init__(self, host: str = "localhost", port: int = 2222):
        self.host = host
        self.port = port
        self.commands = self._load_commands()
        self.active_connection = None
        self.logger = logging.getLogger(__name__)

    def _load_commands(self) -> Dict[str, Any]:
        """Load command definitions from commands.json."""
        commands_file = Path(__file__).parent.parent / "artifacts" / "commands.json"
        with open(commands_file, "r") as f:
            return json.load(f)

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

                self.logger.info(f"Received command: {command_line}")

                # Parse and process command
                cmd_key, cmd_def = self._parse_command(command_line)

                if cmd_def is None or cmd_key is None:
                    # Unknown command
                    response = "ERROR: Unknown command"
                    self.logger.warning(f"Unknown command: {command_line}")
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
                self.logger.info(f"Sent response: {response}")

        except asyncio.CancelledError:
            self.logger.info("Connection cancelled")
        except Exception as e:
            self.logger.error(f"Error handling client: {e}")
        finally:
            self.active_connection = None
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
