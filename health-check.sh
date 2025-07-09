#!/bin/bash

# Timeclock Server Health Check Script
# Description: Checks server health and restarts if unresponsive
# Author: Generated for timeclock deployment
# Usage: Run via cron every 5 minutes

# Configuration
SERVICE_NAME="timeclock"  # Your systemd service name
HEALTH_URL="https://localhost:8443/health"  # Replace with your actual URL
LOG_FILE="./healthcheck.log"  # Log file in same directory as script
MAX_LOG_SIZE=10485760  # 10MB in bytes
TIMEOUT=10  # seconds to wait for response
MAX_RETRIES=2  # number of retry attempts

# Function to log messages with timestamp
log_message() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') - $1" >> "$LOG_FILE"
}

# Function to rotate log if it gets too large
rotate_log() {
    if [ -f "$LOG_FILE" ] && [ $(stat -f%z "$LOG_FILE" 2>/dev/null || stat -c%s "$LOG_FILE" 2>/dev/null) -gt $MAX_LOG_SIZE ]; then
        mv "$LOG_FILE" "${LOG_FILE}.old"
        log_message "Log rotated due to size limit"
    fi
}

# Function to check if service is running
is_service_running() {
    systemctl is-active --quiet "$SERVICE_NAME"
    return $?
}

# Function to ping health endpoint
check_health_endpoint() {
    local attempt=1
    
    while [ $attempt -le $MAX_RETRIES ]; do
        log_message "Health check attempt $attempt/$MAX_RETRIES"
        
        # Use curl to check health endpoint
        if curl -k -f -s --max-time $TIMEOUT "$HEALTH_URL" > /dev/null 2>&1; then
            log_message "Health check PASSED - Server responding normally"
            return 0
        fi
        
        log_message "Health check attempt $attempt FAILED"
        attempt=$((attempt + 1))
        
        # Wait 5 seconds between retries
        if [ $attempt -le $MAX_RETRIES ]; then
            sleep 5
        fi
    done
    
    log_message "Health check FAILED after $MAX_RETRIES attempts"
    return 1
}

# Function to restart the service
restart_service() {
    log_message "RESTARTING SERVICE: $SERVICE_NAME"
    
    # Stop the service first
    systemctl stop "$SERVICE_NAME"
    sleep 3
    
    # Start the service
    systemctl start "$SERVICE_NAME"
    
    if [ $? -eq 0 ]; then
        log_message "Service restart SUCCESSFUL"
        
        # Wait a moment for service to fully start
        sleep 10
        
        # Verify it's actually working
        if check_health_endpoint; then
            log_message "Service restart VERIFIED - Health endpoint responding"
            
            # Send notification (optional - requires mail setup)
            # echo "Timeclock server was restarted on $(hostname) at $(date)" | mail -s "Timeclock Server Restarted" admin@yourcompany.com
            
            return 0
        else
            log_message "Service restart FAILED - Health endpoint still not responding"
            return 1
        fi
    else
        log_message "Service restart FAILED - systemctl reported error"
        return 1
    fi
}

# Function to send alert (customize as needed)
send_alert() {
    local message="$1"
    log_message "ALERT: $message"
    
    # Option 1: Log to system log
    logger -t "timeclock-healthcheck" "$message"
    
    # Option 2: Send email (uncomment if you have mail configured)
    # echo "$message" | mail -s "Timeclock Server Alert" admin@yourcompany.com
    
    # Option 3: Write to a special alert file
    echo "$(date): $message" >> "/var/log/timeclock-alerts.log"
}

# Main execution
main() {
    # Rotate log if needed
    rotate_log
    
    log_message "=== Starting health check ==="
    
    # First check if the systemd service is running
    if ! is_service_running; then
        log_message "ERROR: Service $SERVICE_NAME is not running according to systemd"
        send_alert "Timeclock service $SERVICE_NAME is not running - attempting restart"
        
        # Try to start the service
        systemctl start "$SERVICE_NAME"
        sleep 10
        
        if is_service_running; then
            log_message "Successfully started service via systemd"
        else
            send_alert "CRITICAL: Failed to start service $SERVICE_NAME via systemd"
            exit 1
        fi
    fi
    
    # Check health endpoint
    if check_health_endpoint; then
        log_message "Health check completed successfully"
        exit 0
    else
        log_message "Health endpoint is not responding - service may be hung"
        send_alert "Timeclock server health endpoint not responding - restarting service"
        
        # Restart the service
        if restart_service; then
            log_message "Service successfully restarted and verified"
            send_alert "Timeclock server successfully restarted and is now responding"
            exit 0
        else
            send_alert "CRITICAL: Failed to restart timeclock server - manual intervention required"
            exit 1
        fi
    fi
}

# Create log file if it doesn't exist
touch "$LOG_FILE"

# Run main function
main
