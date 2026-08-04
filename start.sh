#!/bin/bash

# Define paths
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
FRONTEND_DIR="$ROOT_DIR/frontend"
BACKEND_DIR="$ROOT_DIR/agent"

# Cleanup function to kill all child processes when the script exits
cleanup() {
    echo -e "\nShutting down servers..."
    # Kill all children of this script
    pkill -P $$ 2>/dev/null
    exit 0
}

# Register the cleanup function for termination signals
trap cleanup SIGINT SIGTERM

# Start Frontend in the background
echo "Starting frontend server..."
cd "$FRONTEND_DIR"
npm run dev &
FRONTEND_PID=$!

# Prepare Backend
cd "$BACKEND_DIR"
if [ -d "$ROOT_DIR/.venv" ]; then
    source "$ROOT_DIR/.venv/bin/activate"
    echo "Using virtual environment at $ROOT_DIR/.venv"
fi

echo "================================================="
echo "Both servers are starting."
echo "Frontend PID: $FRONTEND_PID"
echo "Press Ctrl+C to stop both servers."
echo "================================================="

# Start Backend in a loop in the foreground so it auto-restarts
while true; do
    echo "Starting backend server (vibe-trading)..."
    vibe-trading
    echo "Backend server stopped (crash or restart requested). Restarting in 2 seconds..."
    sleep 2
done
