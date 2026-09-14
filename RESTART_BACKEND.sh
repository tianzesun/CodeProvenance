#!/bin/bash
# Script to restart the backend server with the updated code

echo "Stopping old backend server..."
pkill -f "uvicorn src.backend.api.server:app"

echo "Waiting for process to stop..."
sleep 2

echo "Starting backend server with updated code..."
cd /home/tsun/Documents/CodeProvenance
source venv/bin/activate

# Start backend server
uvicorn src.backend.api.server:app --host 127.0.0.1 --port 8000 --log-level warning &

echo "Backend server restarted! PID: $!"
echo ""
echo "To test the fix:"
echo "1. Go to http://localhost:3000/upload"
echo "2. Upload 2 files"
echo "3. Click 'Analyze'"
echo "4. Should now complete without getting stuck at 92%"
echo ""
echo "To view logs:"
echo "  tail -f /path/to/logs (or check the terminal where uvicorn is running)"
