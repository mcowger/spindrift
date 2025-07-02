# Spindrift

CNC Protocol Implementation Library

## Description

A modular Python library for CNC protocol implementation, refactored from an existing implementation to be reusable across projects.

## Installation

```bash
poetry install
```

## Development

Run tests:
```bash
poetry run pytest
```

## Mock CNC Server

The Spindrift Mock CNC Server provides a comprehensive TCP server that emulates a Carvera CNC machine for development and testing. It supports hundreds of G-codes, M-codes, and console commands, includes a virtual filesystem with XMODEM file transfers, and provides realistic hardware behavior including connection limits and timeouts. The server is ideal for testing CNC applications without requiring physical hardware access.

```bash
# Basic startup (localhost:2222)
poetry run spindrift mock-server

# Custom host/port and verbose logging
poetry run spindrift mock-server --host 0.0.0.0 --port 3333 --verbose
```

📖 **[Complete Mock Server Documentation](README.mock_server.md)** - Comprehensive guide including all supported commands, virtual filesystem usage, XMODEM transfers, testing strategies, and troubleshooting.