#!/bin/bash

# Memory Site Runner
echo "📸 Starting Private Memory Site"
echo "================================"

# Check Python version
python_version=$(python3 --version 2>&1 | grep -Po '(?<=Python )\d+\.\d+')
if (( $(echo "$python_version < 3.7" | bc -l) )); then
    echo "❌ Python 3.7+ required. Found Python $python_version"
    exit 1
fi

echo "✅ Python $python_version found"

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo "📦 Creating virtual environment..."
    python3 -m venv venv
fi

# Activate virtual environment
source venv/bin/activate

# Install requirements
echo "📦 Installing requirements..."
pip install -r requirements.txt

# Initialize database if it doesn't exist
if [ ! -f "memories.db" ]; then
    echo "🗄️ Initializing database..."
    python init_db.py
fi

# Start the application
echo "🚀 Starting server..."
echo "🌐 Access your memory site at: http://localhost:5000"
echo "================================"

# Set Flask environment variables
export FLASK_APP=app.py
export FLASK_ENV=development
export FLASK_DEBUG=1

# Run the app
python app.py
