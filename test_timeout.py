#!/usr/bin/env python3
"""
Test script to verify the 10-second timeout behavior of the mock CNC server.
"""

import socket
import time
import threading


def test_timeout_behavior():
    """Test that the server disconnects after 10 seconds of inactivity."""
    print("Testing 10-second timeout behavior...")
    
    try:
        # Connect to server
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.connect(('localhost', 2222))
        print("✓ Connected to server")
        
        # Send a command to establish connection
        sock.send(b"version\n")
        response = sock.recv(1024).decode('utf-8').strip()
        print(f"Initial response: {response}")
        
        # Wait for 12 seconds without sending anything
        print("Waiting 12 seconds without sending commands...")
        start_time = time.time()
        
        try:
            # Try to receive data - this should timeout/disconnect
            sock.settimeout(12.0)
            data = sock.recv(1024)
            if not data:
                elapsed = time.time() - start_time
                print(f"✓ Server disconnected after {elapsed:.1f} seconds")
            else:
                print(f"✗ Unexpected data received: {data}")
        except socket.timeout:
            print("✗ Socket timeout - server should have disconnected us")
        except ConnectionResetError:
            elapsed = time.time() - start_time
            print(f"✓ Server disconnected after {elapsed:.1f} seconds (connection reset)")
        
        sock.close()
        
    except ConnectionRefusedError:
        print("✗ Could not connect to server. Make sure it's running on port 2222")
    except Exception as e:
        print(f"✗ Test failed: {e}")


def test_activity_keeps_connection():
    """Test that sending commands within 10 seconds keeps the connection alive."""
    print("\nTesting that activity keeps connection alive...")
    
    try:
        # Connect to server
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.connect(('localhost', 2222))
        print("✓ Connected to server")
        
        # Send commands every 5 seconds for 25 seconds
        for i in range(5):
            sock.send(b"?\n")
            response = sock.recv(1024).decode('utf-8').strip()
            print(f"Command {i+1} response received (length: {len(response)})")
            
            if i < 4:  # Don't sleep after the last command
                time.sleep(5)
        
        print("✓ Connection stayed alive with regular activity")
        sock.close()
        
    except Exception as e:
        print(f"✗ Activity test failed: {e}")


if __name__ == "__main__":
    print("Mock CNC Server Timeout Test")
    print("============================")
    print("Make sure to start the server first with:")
    print("  poetry run spindrift mock-server")
    print()
    
    input("Press Enter when server is running...")
    
    test_timeout_behavior()
    test_activity_keeps_connection()
    
    print("\nTimeout tests completed!")
