#!/bin/bash
# Quick Start Script for Camera AI-VMD Manager

set -e

echo "=================================="
echo "Camera AI-VMD Manager Quick Start"
echo "=================================="
echo ""

# Check Python version
if ! command -v python3 &> /dev/null; then
    echo "Error: Python 3 is not installed"
    echo "Please install Python 3.8 or higher"
    exit 1
fi

PYTHON_VERSION=$(python3 --version | awk '{print $2}')
echo "✓ Python version: $PYTHON_VERSION"

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo ""
    echo "Creating virtual environment..."
    python3 -m venv venv
    echo "✓ Virtual environment created"
fi

# Activate virtual environment
echo ""
echo "Activating virtual environment..."
source venv/bin/activate
echo "✓ Virtual environment activated"

# Install dependencies
echo ""
echo "Installing dependencies..."
pip install -q --upgrade pip
pip install -q -r requirements.txt
echo "✓ Dependencies installed"

# Check for cameras.json
if [ ! -f "cameras.json" ]; then
    echo ""
    echo "⚠ Warning: cameras.json not found"
    echo "Please create cameras.json with your camera configuration"
    echo "See README.md for format details"
    echo ""
fi

# Start the application
echo ""
echo "=================================="
echo "Starting Camera AI-VMD Manager..."
echo "=================================="
echo ""
echo "Access the web interface at: http://localhost:5000"
echo "Press Ctrl+C to stop the server"
echo ""

python3 app.py
