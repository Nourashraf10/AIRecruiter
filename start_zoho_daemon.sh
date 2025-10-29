#!/bin/bash

# Start Zoho Mail Monitor as a daemon
# This script will run the monitor in the background and restart it if it crashes

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PID_FILE="$SCRIPT_DIR/zoho_monitor.pid"
LOG_FILE="$SCRIPT_DIR/logs/zoho_monitor.log"
MONITOR_SCRIPT="$SCRIPT_DIR/zoho_mail_monitor.py"

# Create logs directory
mkdir -p "$SCRIPT_DIR/logs"

# Function to start the monitor
start_monitor() {
    if [ -f "$PID_FILE" ]; then
        PID=$(cat "$PID_FILE")
        if ps -p "$PID" > /dev/null 2>&1; then
            echo "❌ Zoho Mail Monitor is already running (PID: $PID)"
            return 1
        else
            rm -f "$PID_FILE"
        fi
    fi
    
    echo "🚀 Starting Zoho Mail Monitor daemon..."
    nohup python3 "$MONITOR_SCRIPT" > "$LOG_FILE" 2>&1 &
    PID=$!
    echo $PID > "$PID_FILE"
    echo "✅ Zoho Mail Monitor started (PID: $PID)"
    echo "📋 Logs: $LOG_FILE"
    return 0
}

# Function to stop the monitor
stop_monitor() {
    if [ -f "$PID_FILE" ]; then
        PID=$(cat "$PID_FILE")
        if ps -p "$PID" > /dev/null 2>&1; then
            echo "🛑 Stopping Zoho Mail Monitor (PID: $PID)..."
            kill "$PID"
            rm -f "$PID_FILE"
            echo "✅ Zoho Mail Monitor stopped"
        else
            echo "❌ Zoho Mail Monitor is not running"
            rm -f "$PID_FILE"
        fi
    else
        echo "❌ Zoho Mail Monitor is not running"
    fi
}

# Function to check status
status_monitor() {
    if [ -f "$PID_FILE" ]; then
        PID=$(cat "$PID_FILE")
        if ps -p "$PID" > /dev/null 2>&1; then
            echo "✅ Zoho Mail Monitor is running (PID: $PID)"
            echo "📋 Recent logs:"
            if [ -f "$LOG_FILE" ]; then
                tail -10 "$LOG_FILE"
            else
                echo "No log file found"
            fi
        else
            echo "❌ Zoho Mail Monitor is not running (stale PID file)"
            rm -f "$PID_FILE"
        fi
    else
        echo "❌ Zoho Mail Monitor is not running"
    fi
}

# Function to restart the monitor
restart_monitor() {
    echo "🔄 Restarting Zoho Mail Monitor..."
    stop_monitor
    sleep 2
    start_monitor
}

# Function to show logs
show_logs() {
    if [ -f "$LOG_FILE" ]; then
        echo "📋 Zoho Mail Monitor logs:"
        tail -f "$LOG_FILE"
    else
        echo "❌ No log file found"
    fi
}

# Main script logic
case "$1" in
    start)
        start_monitor
        ;;
    stop)
        stop_monitor
        ;;
    restart)
        restart_monitor
        ;;
    status)
        status_monitor
        ;;
    logs)
        show_logs
        ;;
    *)
        echo "🤖 Zoho Mail Monitor Daemon Manager"
        echo "===================================="
        echo ""
        echo "Usage: $0 [command]"
        echo ""
        echo "Commands:"
        echo "  start   - Start the monitor daemon"
        echo "  stop    - Stop the monitor daemon"
        echo "  restart - Restart the monitor daemon"
        echo "  status  - Show daemon status and recent logs"
        echo "  logs    - Show live logs"
        echo ""
        echo "Examples:"
        echo "  $0 start    # Start the daemon"
        echo "  $0 status   # Check if daemon is running"
        echo "  $0 logs     # View live logs"
        echo "  $0 stop     # Stop the daemon"
        ;;
esac
