#!/bin/bash

# Zoho Mail Monitor Dashboard
# Shows comprehensive status of the monitoring system

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PID_FILE="$SCRIPT_DIR/zoho_monitor.pid"
LOG_FILE="$SCRIPT_DIR/logs/zoho_monitor.log"
HEALTH_LOG="$SCRIPT_DIR/logs/health_check.log"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to get status with color
get_status() {
    if [ -f "$PID_FILE" ]; then
        PID=$(cat "$PID_FILE")
        if ps -p "$PID" > /dev/null 2>&1; then
            echo -e "${GREEN}✅ RUNNING${NC} (PID: $PID)"
            return 0
        else
            echo -e "${RED}❌ NOT RUNNING${NC} (stale PID: $PID)"
            return 1
        fi
    else
        echo -e "${RED}❌ NOT RUNNING${NC} (no PID file)"
        return 1
    fi
}

# Function to get recent activity
get_recent_activity() {
    if [ -f "$LOG_FILE" ]; then
        # Get last 5 log entries
        echo "📋 Recent Activity:"
        tail -5 "$LOG_FILE" | while read line; do
            echo "   $line"
        done
    else
        echo "❌ No log file found"
    fi
}

# Function to get health check status
get_health_status() {
    if [ -f "$HEALTH_LOG" ]; then
        echo "🏥 Health Check Status:"
        tail -3 "$HEALTH_LOG" | while read line; do
            if [[ $line == *"✅"* ]]; then
                echo -e "   ${GREEN}$line${NC}"
            elif [[ $line == *"❌"* ]] || [[ $line == *"🚨"* ]]; then
                echo -e "   ${RED}$line${NC}"
            elif [[ $line == *"⚠️"* ]]; then
                echo -e "   ${YELLOW}$line${NC}"
            else
                echo "   $line"
            fi
        done
    else
        echo "❌ No health check log found"
    fi
}

# Function to get system service status
get_service_status() {
    echo "🔧 System Services:"
    
    # Check LaunchAgent status
    if launchctl list | grep -q "com.bit68.zoho-mail-monitor"; then
        echo -e "   Zoho Monitor: ${GREEN}✅ LOADED${NC}"
    else
        echo -e "   Zoho Monitor: ${RED}❌ NOT LOADED${NC}"
    fi
    
    if launchctl list | grep -q "com.bit68.zoho-health-check"; then
        echo -e "   Health Check: ${GREEN}✅ LOADED${NC}"
    else
        echo -e "   Health Check: ${RED}❌ NOT LOADED${NC}"
    fi
}

# Function to show statistics
get_statistics() {
    echo "📊 Statistics:"
    
    if [ -f "$LOG_FILE" ]; then
        # Count processed emails
        PROCESSED_EMAILS=$(grep -c "Successfully processed email" "$LOG_FILE" 2>/dev/null || echo "0")
        echo "   Emails Processed: $PROCESSED_EMAILS"
        
        # Count errors
        ERRORS=$(grep -c -i "error\|exception\|failed" "$LOG_FILE" 2>/dev/null || echo "0")
        echo "   Errors: $ERRORS"
        
        # Last activity
        LAST_ACTIVITY=$(tail -1 "$LOG_FILE" | cut -d' ' -f1-2 2>/dev/null || echo "Unknown")
        echo "   Last Activity: $LAST_ACTIVITY"
    else
        echo "   No statistics available"
    fi
}

# Main dashboard
main() {
    clear
    echo -e "${BLUE}🤖 ZOHO MAIL MONITOR DASHBOARD${NC}"
    echo "=========================================="
    echo ""
    
    echo -e "${BLUE}📡 Monitor Status:${NC}"
    get_status
    echo ""
    
    get_recent_activity
    echo ""
    
    get_health_status
    echo ""
    
    get_service_status
    echo ""
    
    get_statistics
    echo ""
    
    echo -e "${BLUE}🔧 Quick Actions:${NC}"
    echo "   ./start_zoho_daemon.sh status  - Check daemon status"
    echo "   ./start_zoho_daemon.sh logs    - View live logs"
    echo "   ./start_zoho_daemon.sh restart - Restart daemon"
    echo "   ./monitor_health.sh            - Run health check"
    echo ""
    
    echo -e "${BLUE}📁 Log Files:${NC}"
    echo "   Monitor Logs: $LOG_FILE"
    echo "   Health Logs:  $HEALTH_LOG"
    echo ""
    
    echo "Press Ctrl+C to exit, or wait 30 seconds for auto-refresh..."
}

# Auto-refresh every 30 seconds
if [ "$1" = "--watch" ]; then
    while true; do
        main
        sleep 30
    done
else
    main
fi
