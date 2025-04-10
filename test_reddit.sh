#!/bin/bash
# Simple script to test Reddit connection with history expansion disabled

set +H  # Disable history expansion
python3 -c 'from tools.reddit import _get_reddit_instance; reddit = _get_reddit_instance(); print("Success!" if reddit else "Failed")'
set -H  # Re-enable history expansion
