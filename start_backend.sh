#!/bin/bash
echo "🌊 Starting Aquifer Intelligence Platform..."

cd "$(dirname "$0")/backend"

# Install dependencies
echo "📦 Installing Python dependencies..."
pip install fastapi uvicorn pyjwt python-multipart --break-system-packages -q

# Start backend
echo "🚀 Starting FastAPI backend on http://localhost:8000"
echo "📖 API Docs: http://localhost:8000/docs"
python main.py
