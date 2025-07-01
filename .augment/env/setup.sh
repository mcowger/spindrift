#!/bin/bash
set -e

# Update system packages
sudo apt-get update

# Install Python 3.8+ and pip if not already installed
sudo apt-get install -y python3 python3-pip python3-venv

# Install Poetry
curl -sSL https://install.python-poetry.org | python3 -
echo 'export PATH="$HOME/.local/bin:$PATH"' >>$HOME/.profile
export PATH="$HOME/.local/bin:$PATH"

# Navigate to the workspace
cd /mnt/persist/workspace

# Install project dependencies using Poetry
poetry install

# Add Poetry virtual environment activation to profile
echo 'cd /mnt/persist/workspace && poetry shell' >>$HOME/.profile

echo "Setup completed successfully!"
