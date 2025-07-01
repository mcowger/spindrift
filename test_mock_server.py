#!/usr/bin/env python3
"""
Simple test script to verify the mock CNC server works correctly.
"""

import socket
import time
import threading
from spindrift.mock_server import MockCNCServer
import asyncio


def test_server_connection():
    """Test basic server connection and commands."""
    print("Testing mock CNC server...")

    # Test commands to send
    test_commands = [
        "version",
        "?",
        "$G",
        "$#",
        "G0 X10 Y5 F100",
        "M3 S5000",
        "M5",
        "help",
        "mem",
        "ls",
        "pwd",
        "unknown_command",
    ]

    try:
        # Connect to server
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.connect(("localhost", 2222))
        print("✓ Connected to server")

        for cmd in test_commands:
            print(f"\nSending: {cmd}")

            # Send command
            sock.send(f"{cmd}\n".encode("utf-8"))

            # Receive response
            response = sock.recv(4096).decode("utf-8").strip()
            print(f"Response: {response}")

            # Small delay between commands
            time.sleep(0.1)

        sock.close()
        print("\n✓ All tests completed successfully")

    except ConnectionRefusedError:
        print("✗ Could not connect to server. Make sure it's running on port 2222")
    except Exception as e:
        print(f"✗ Test failed: {e}")


def test_concurrent_connections():
    """Test that concurrent connections are rejected."""
    print("\nTesting concurrent connection rejection...")

    try:
        # First connection
        sock1 = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock1.connect(("localhost", 2222))
        print("✓ First connection established")

        # Second connection (should be rejected)
        sock2 = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock2.connect(("localhost", 2222))

        # Try to read response from second connection
        response = sock2.recv(1024).decode("utf-8")
        if "ERROR: Server busy" in response:
            print("✓ Second connection properly rejected")
        else:
            print(f"✗ Unexpected response: {response}")

        sock1.close()
        sock2.close()

    except Exception as e:
        print(f"✗ Concurrent connection test failed: {e}")


if __name__ == "__main__":
    print("Mock CNC Server Test")
    print("===================")
    print("Make sure to start the server first with:")
    print("  python -m spindrift.mock_server mock-server")
    print("or:")
    print("  poetry run spindrift mock-server")
    print()

    input("Press Enter when server is running...")

    test_server_connection()
    test_concurrent_connections()

    print("\nTest completed!")
