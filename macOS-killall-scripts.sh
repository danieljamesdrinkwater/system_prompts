#!/bin/bash
# =============================================================================
# macOS Kill All Scripts
# Useful commands and scripts for terminating processes on macOS
# =============================================================================

# -----------------------------------------------------------------------------
# Basic killall commands - Kill processes by name
# -----------------------------------------------------------------------------

# Kill Finder (it will automatically restart)
killall Finder

# Kill Dock (it will automatically restart)
killall Dock

# Kill SystemUIServer (menu bar - restarts automatically)
killall SystemUIServer

# Kill all Safari instances
killall Safari

# Kill all Chrome instances
killall "Google Chrome"

# Kill all Firefox instances
killall firefox

# Kill all Terminal instances (careful - closes your terminal too!)
# killall Terminal

# Kill all Preview instances
killall Preview

# Kill all Mail instances
killall Mail

# Kill all Messages instances
killall Messages

# Kill all Slack instances
killall Slack

# Kill all Zoom instances
killall zoom.us

# Kill all Microsoft Teams instances
killall "Microsoft Teams"

# Kill all VS Code instances
killall "Electron"  # VS Code runs as Electron
# Or more specifically:
killall "Code Helper (Renderer)"

# Kill all Xcode instances
killall Xcode

# Kill all Activity Monitor instances
killall "Activity Monitor"

# -----------------------------------------------------------------------------
# Force kill (-9 SIGKILL) - Use when processes won't respond to normal kill
# -----------------------------------------------------------------------------

# Force kill a stubborn process
killall -9 Safari

# Force kill all instances of an app
killall -9 "Google Chrome"

# -----------------------------------------------------------------------------
# Kill by signal type
# -----------------------------------------------------------------------------

# Send SIGTERM (default, graceful shutdown)
killall -SIGTERM Safari

# Send SIGKILL (force kill, no cleanup)
killall -SIGKILL Safari

# Send SIGHUP (hang up, often used to reload config)
killall -SIGHUP nginx

# Send SIGSTOP (pause/freeze a process)
killall -SIGSTOP Safari

# Send SIGCONT (resume a paused process)
killall -SIGCONT Safari

# -----------------------------------------------------------------------------
# Kill processes by user
# -----------------------------------------------------------------------------

# Kill all processes owned by a specific user
killall -u username

# Kill all user processes (force)
killall -9 -u username

# -----------------------------------------------------------------------------
# Using pkill - Pattern-based process killing
# -----------------------------------------------------------------------------

# Kill processes matching a pattern
pkill -f "chrome"

# Kill processes matching a pattern (case insensitive)
pkill -if "chrome"

# Force kill by pattern
pkill -9 -f "node server.js"

# Kill all Node.js processes
pkill -f node

# Kill all Python processes
pkill -f python

# Kill all Ruby processes
pkill -f ruby

# Kill all Java processes
pkill -f java

# -----------------------------------------------------------------------------
# Using kill with PID - Kill specific process by ID
# -----------------------------------------------------------------------------

# Find PID first, then kill
# Find PID of a process
pgrep -f "process_name"

# Kill specific PID
kill 12345

# Force kill specific PID
kill -9 12345

# Kill multiple PIDs
kill 12345 67890 11111

# -----------------------------------------------------------------------------
# Kill all processes on a specific port
# -----------------------------------------------------------------------------

# Find and kill process on port 3000
lsof -ti:3000 | xargs kill -9

# Find and kill process on port 8080
lsof -ti:8080 | xargs kill -9

# Kill processes on multiple ports
lsof -ti:3000,8080,5000 | xargs kill -9

# Generic function to kill process on a port
kill_port() {
    local port=$1
    local pid
    pid=$(lsof -ti:"$port" 2>/dev/null)
    if [ -n "$pid" ]; then
        kill -9 "$pid"
        echo "Killed process $pid on port $port"
    else
        echo "No process found on port $port"
    fi
}

# -----------------------------------------------------------------------------
# Kill all background jobs
# -----------------------------------------------------------------------------

# Kill all background jobs in current shell
kill $(jobs -p) 2>/dev/null

# Kill all background jobs (force)
kill -9 $(jobs -p) 2>/dev/null

# -----------------------------------------------------------------------------
# Batch kill scripts
# -----------------------------------------------------------------------------

# Kill all common dev servers
kill_dev_servers() {
    echo "Killing development servers..."
    pkill -f "node" 2>/dev/null
    pkill -f "python.*manage.py" 2>/dev/null
    pkill -f "ruby.*rails" 2>/dev/null
    pkill -f "php.*artisan" 2>/dev/null
    pkill -f "webpack" 2>/dev/null
    pkill -f "vite" 2>/dev/null
    pkill -f "next" 2>/dev/null
    lsof -ti:3000,3001,4000,5000,5173,8000,8080 | xargs kill -9 2>/dev/null
    echo "Done."
}

# Kill all browsers
kill_all_browsers() {
    echo "Killing all browsers..."
    killall Safari 2>/dev/null
    killall "Google Chrome" 2>/dev/null
    killall firefox 2>/dev/null
    killall "Microsoft Edge" 2>/dev/null
    killall "Brave Browser" 2>/dev/null
    killall Opera 2>/dev/null
    killall Arc 2>/dev/null
    echo "Done."
}

# Kill all communication apps
kill_all_comms() {
    echo "Killing communication apps..."
    killall Slack 2>/dev/null
    killall "Microsoft Teams" 2>/dev/null
    killall Discord 2>/dev/null
    killall zoom.us 2>/dev/null
    killall Telegram 2>/dev/null
    killall WhatsApp 2>/dev/null
    killall Messages 2>/dev/null
    killall Mail 2>/dev/null
    echo "Done."
}

# Kill all non-essential apps (keeps Finder, Dock, etc.)
kill_all_apps() {
    echo "Killing all non-essential applications..."
    osascript -e 'tell application "System Events" to set quitapps to name of every application process whose background only is false and name is not "Finder"'
    osascript -e 'tell application "System Events"
        set appList to name of every application process whose background only is false and name is not "Finder"
        repeat with appName in appList
            try
                tell application appName to quit
            end try
        end repeat
    end tell'
    echo "Done."
}

# Force quit all non-essential apps
force_kill_all_apps() {
    echo "Force quitting all non-essential applications..."
    osascript -e 'tell application "System Events"
        set appList to name of every application process whose background only is false and name is not "Finder" and name is not "Terminal" and name is not "iTerm2"
        repeat with appName in appList
            do shell script "killall -9 " & quoted form of appName
        end repeat
    end tell'
    echo "Done."
}

# -----------------------------------------------------------------------------
# Reset macOS UI components
# -----------------------------------------------------------------------------

reset_ui() {
    echo "Resetting macOS UI components..."
    killall Dock
    killall Finder
    killall SystemUIServer
    killall ControlCenter 2>/dev/null
    killall NotificationCenter 2>/dev/null
    echo "UI components will restart automatically."
}

# -----------------------------------------------------------------------------
# Kill accessibility-related processes
# -----------------------------------------------------------------------------

kill_accessibility() {
    echo "Killing accessibility-related processes..."

    # Kill VoiceOver
    killall "VoiceOver" 2>/dev/null
    killall "VoiceOverCacheDelete" 2>/dev/null

    # Kill Accessibility Inspector (Xcode tool)
    killall "Accessibility Inspector" 2>/dev/null

    # Kill assistive technology processes
    killall "AssistiveControl" 2>/dev/null
    killall "AXVisualSupportAgent" 2>/dev/null

    # Kill Zoom (accessibility zoom, not the video app)
    killall "ZoomAutoFix" 2>/dev/null

    # Kill Switch Control
    killall "SwitchBoard" 2>/dev/null

    # Kill dictation/speech processes
    killall "DictationIM" 2>/dev/null
    killall "SpeechSynthesisServer" 2>/dev/null
    killall "SpeechRecognitionCore" 2>/dev/null
    killall "com.apple.speech.speechsynthesisd" 2>/dev/null

    # Kill Hover Text
    killall "HoverTextService" 2>/dev/null

    # Kill accessibility-related agents
    killall "universalaccessd" 2>/dev/null
    killall "com.apple.accessibility.AXVisualSupportAgent" 2>/dev/null
    killall "universalAccessAuthWarn" 2>/dev/null

    echo "Accessibility processes killed. Some may restart if enabled in System Settings."
}

# Reset accessibility completely (requires re-enabling in System Settings)
reset_accessibility() {
    echo "Resetting accessibility services..."

    # Kill all accessibility-related daemons
    kill_accessibility

    # Reset TCC permissions for accessibility (requires sudo)
    # WARNING: This removes all accessibility permissions for all apps
    # sudo tccutil reset Accessibility

    # Restart accessibility framework
    killall "tccd" 2>/dev/null
    killall "universalaccessd" 2>/dev/null

    echo "Accessibility services reset. Re-enable features in System Settings > Accessibility."
}

# Kill screen reader and related assistive processes
kill_screen_readers() {
    echo "Killing screen reader processes..."
    killall "VoiceOver" 2>/dev/null
    killall "com.apple.VoiceOverUtility" 2>/dev/null
    killall "SpeechSynthesisServer" 2>/dev/null

    # Also kill third-party screen readers if present
    pkill -f "JAWS" 2>/dev/null
    pkill -f "NVDA" 2>/dev/null

    echo "Screen reader processes killed."
}

# -----------------------------------------------------------------------------
# Clear DNS cache (kills mDNSResponder)
# -----------------------------------------------------------------------------

flush_dns() {
    echo "Flushing DNS cache..."
    sudo dscacheutil -flushcache
    sudo killall -HUP mDNSResponder
    echo "DNS cache flushed."
}

# -----------------------------------------------------------------------------
# Kill hung Spotlight indexing
# -----------------------------------------------------------------------------

reset_spotlight() {
    echo "Resetting Spotlight..."
    sudo killall mds_stores 2>/dev/null
    sudo mdutil -E / 2>/dev/null
    echo "Spotlight will re-index."
}

# -----------------------------------------------------------------------------
# Interactive kill script - List and select processes to kill
# -----------------------------------------------------------------------------

interactive_kill() {
    echo "Top 20 processes by CPU usage:"
    echo "-------------------------------"
    ps aux --sort=-%cpu | head -21 | awk '{printf "%-8s %-6s %-5s %s\n", $1, $2, $3, $11}'
    echo ""
    read -rp "Enter PID to kill (or 'q' to quit): " pid
    if [ "$pid" != "q" ] && [ -n "$pid" ]; then
        kill -9 "$pid" 2>/dev/null && echo "Process $pid killed." || echo "Failed to kill process $pid."
    fi
}

# -----------------------------------------------------------------------------
# Usage
# -----------------------------------------------------------------------------
# Source this file to use the functions:
#   source macOS-killall-scripts.sh
#
# Then call any function:
#   kill_port 3000
#   kill_all_browsers
#   kill_dev_servers
#   kill_all_comms
#   kill_accessibility
#   reset_accessibility
#   kill_screen_readers
#   reset_ui
#   flush_dns
#   reset_spotlight
#   interactive_kill
#   kill_all_apps
#   force_kill_all_apps
# -----------------------------------------------------------------------------
