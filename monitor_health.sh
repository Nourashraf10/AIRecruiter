#!/bin/bash

# Health Check and Auto-Recovery Script for Zoho Mail Monitor
# This script runs every 5 minutes to ensure the monitor is always running

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PID_FILE="$SCRIPT_DIR/zoho_monitor.pid"
LOG_FILE="$SCRIPT_DIR/logs/zoho_monitor.log"
HEALTH_LOG="$SCRIPT_DIR/logs/health_check.log"
DAEMON_SCRIPT="$SCRIPT_DIR/start_zoho_daemon.sh"

# Create logs directory
mkdir -p "$SCRIPT_DIR/logs"

# Function to log with timestamp
log_message() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') - $1" >> "$HEALTH_LOG"
}

# Function to check if monitor is running
check_monitor() {
    if [ -f "$PID_FILE" ]; then
        PID=$(cat "$PID_FILE")
        if ps -p "$PID" > /dev/null 2>&1; then
            return 0  # Running
        else
            log_message "❌ Monitor process not found (stale PID: $PID)"
            rm -f "$PID_FILE"
            return 1  # Not running
        fi
    else
        log_message "❌ No PID file found"
        return 1  # Not running
    fi
}

# Function to check if monitor is processing emails
check_monitor_activity() {
    if [ -f "$LOG_FILE" ]; then
        # Check if there are recent log entries (within last 10 minutes)
        RECENT_LOGS=$(find "$LOG_FILE" -mmin -10 2>/dev/null)
        if [ -n "$RECENT_LOGS" ]; then
            # Check if there are any error messages in the last 10 minutes
            RECENT_ERRORS=$(tail -50 "$LOG_FILE" | grep -i "error\|exception\|failed" | wc -l)
            if [ "$RECENT_ERRORS" -gt 0 ]; then
                log_message "⚠️ Monitor has recent errors: $RECENT_ERRORS"
                return 1
            fi
            return 0  # Healthy
        else
            log_message "⚠️ No recent log activity"
            return 1
        fi
    else
        log_message "❌ No log file found"
        return 1
    fi
}

# Function to restart monitor
restart_monitor() {
    log_message "🔄 Restarting Zoho Mail Monitor..."
    "$DAEMON_SCRIPT" restart
    if [ $? -eq 0 ]; then
        log_message "✅ Monitor restarted successfully"
        return 0
    else
        log_message "❌ Failed to restart monitor"
        return 1
    fi
}

# Function to send notification (you can customize this)
send_notification() {
    local message="$1"
    log_message "📢 NOTIFICATION: $message"
    
    # You can add email notifications, Slack webhooks, etc. here
    # For now, just log the notification
}

# Main health check
main() {
    log_message "🔍 Starting health check..."
    
    # Check if monitor is running
    if ! check_monitor; then
        log_message "🚨 Monitor is not running, attempting restart..."
        if restart_monitor; then
            send_notification "Zoho Mail Monitor was down and has been restarted"
        else
            send_notification "CRITICAL: Zoho Mail Monitor is down and failed to restart"
        fi
        return
    fi
    
    # Check monitor activity
    if ! check_monitor_activity; then
        log_message "🚨 Monitor appears unhealthy, attempting restart..."
        if restart_monitor; then
            send_notification "Zoho Mail Monitor was unhealthy and has been restarted"
        else
            send_notification "CRITICAL: Zoho Mail Monitor is unhealthy and failed to restart"
        fi
        return
    fi
    
    log_message "✅ Monitor is healthy and running"
}

# Run the health check
main
