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

## Mock Server

Run the mock CNC server for testing:

```bash
# Using poetry (recommended)
poetry run spindrift mock-server

# With custom host/port
poetry run spindrift mock-server --host 0.0.0.0 --port 3333

# Enable verbose logging
poetry run spindrift mock-server --verbose
```

The mock server runs on `localhost:2222` by default and simulates a CNC machine by responding to G-codes, M-codes, and console commands based on the configuration in `artifacts/commands.json`.