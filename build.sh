#!/usr/bin/env bash
# Exit on error
set -o errexit

# Ensure Python version
echo "Checking Python version..."
python --version

# Upgrade pip
echo "Upgrading pip..."
pip install --upgrade pip

# Install dependencies
echo "Installing dependencies..."
pip install -r requirements.txt

# Run database migrations if needed
# Uncomment if you're using Alembic for migrations
# echo "Running database migrations..."
# alembic upgrade head

echo "Build completed successfully!" 