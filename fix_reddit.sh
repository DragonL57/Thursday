#!/bin/bash
# Simple wrapper to run the Reddit fix script with the correct Python interpreter

# Display script location for troubleshooting
echo "Running fix_reddit.sh from: $(pwd)/$(basename "$0")"

# Find the best available Python
if command -v python3 &> /dev/null; then
    PYTHON_CMD="python3"
elif command -v python &> /dev/null; then
    PYTHON_CMD="python"
else
    echo "Error: No Python interpreter found"
    exit 1
fi

# Check if required modules are installed
$PYTHON_CMD -c "import requests" 2>/dev/null || {
    echo "Installing required Python modules..."
    $PYTHON_CMD -m pip install requests
}

# Get the absolute path to the script directory
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
FIX_SCRIPT="${SCRIPT_DIR}/scripts/fix_reddit_hosts.py"

# Check if the fix script exists
if [ ! -f "$FIX_SCRIPT" ]; then
    echo "Error: Fix script not found at $FIX_SCRIPT"
    exit 1
fi

# Make the script executable
chmod +x "$FIX_SCRIPT"

# Backup hosts file before modification
HOSTS_FILE="/etc/hosts"
if [ "$EUID" -eq 0 ]; then  # Fixed missing space
    echo "Creating backup of hosts file..."
    cp "$HOSTS_FILE" "${HOSTS_FILE}.bak"
fi

# Run the script with sudo
if [ "$EUID" -ne 0 ]; then  # Fixed missing space
    echo "This script requires administrator privileges to modify the hosts file."
    sudo "$PYTHON_CMD" "$FIX_SCRIPT" "$@"
else
    "$PYTHON_CMD" "$FIX_SCRIPT" "$@"
fi

# Test Reddit API functionality
echo ""
echo "Testing Reddit API connection..."
$PYTHON_CMD -c "
import sys, os
sys.path.append('$SCRIPT_DIR')
try:
    from tools.reddit import _get_reddit_instance
    reddit = _get_reddit_instance(timeout=20)
    if reddit:
        subreddit = reddit.subreddit('announcements')
        print(f'\033[92m✓ Success: Connected to r/{subreddit.display_name}\033[0m')
        print('Reddit tools should work correctly now.')
    else:
        print('\033[91m✗ Failed to connect to Reddit API\033[0m')
        print('Try running the fix_reddit_hosts.py script directly.')
except Exception as e:
    print(f'\033[91m✗ Error: {e}\033[0m')
"
