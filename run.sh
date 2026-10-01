#!/bin/bash

# Financial Reconciliation Tool - Quick Start Script

echo "======================================"
echo "Financial Reconciliation Tool"
echo "Quick Start Setup"
echo "======================================"
echo ""

# Check if Python is installed
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 is not installed. Please install Python 3.8+ first."
    exit 1
fi

echo "✅ Python 3 found: $(python3 --version)"
echo ""

# Create virtual environment if not exists
if [ ! -d "venv" ]; then
    echo "📦 Creating virtual environment..."
    python3 -m venv venv
    echo "✅ Virtual environment created"
else
    echo "✅ Virtual environment already exists"
fi

echo ""

# Activate virtual environment
echo "🔧 Activating virtual environment..."
source venv/bin/activate

echo ""

# Install requirements
echo "📥 Installing dependencies..."
pip install -q -r requirements.txt
echo "✅ Dependencies installed"

echo ""

# Generate sample data
echo "📊 Generating sample data..."
cd data
python3 generate_sample_data.py
cd ..

echo ""
echo "======================================"
echo "Setup Complete! ✅"
echo "======================================"
echo ""
echo "🚀 Starting the application..."
echo ""
echo "The server will run on: http://localhost:5000"
echo ""
echo "📝 Instructions:"
echo "1. Wait for Flask to start (you'll see 'Running on...')"
echo "2. Open http://localhost:5000 in your browser"
echo "3. Sample CSV files are in the 'data' folder"
echo "4. Upload the sample files and run reconciliation"
echo ""
echo "Press Ctrl+C to stop the server"
echo ""

# Start Flask app
cd backend
python3 app.py
