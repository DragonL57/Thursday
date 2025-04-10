#!/usr/bin/env python3
"""
Troubleshooting script for Reddit tools in the personal-gem project.
This script helps diagnose issues with the Reddit API connection.
"""

import os
import sys
import time
import importlib.util
import requests
import json

# Add parent directory to path
parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(parent_dir)

# ANSI color codes
COLORS = {
    'GREEN': '\033[92m',
    'YELLOW': '\033[93m',
    'RED': '\033[91m',
    'BLUE': '\033[94m',
    'ENDC': '\033[0m',
    'BOLD': '\033[1m',
}

def colored(text, color):
    """Add color to terminal output."""
    return f"{COLORS.get(color, '')}{text}{COLORS['ENDC']}"

def check_package(package_name):
    """Check if a package is installed and get its version."""
    try:
        spec = importlib.util.find_spec(package_name)
        if spec is None:
            return False, None
        
        # Try to get the version
        try:
            module = __import__(package_name)
            version = getattr(module, '__version__', 'Unknown')
            return True, version
        except (ImportError, AttributeError):
            return True, "Unknown version"
    except Exception as e:
        return False, str(e)

def check_reddit_connection():
    """Check direct connectivity to Reddit."""
    print(colored("\nTesting direct connection to Reddit...", "BOLD"))
    
    urls = [
        "https://www.reddit.com/",
        "https://api.reddit.com/",
        "https://oauth.reddit.com/"
    ]
    
    all_success = True
    
    for url in urls:
        try:
            print(f"Testing connection to {url}...")
            start_time = time.time()
            response = requests.get(url, timeout=10)
            elapsed = time.time() - start_time
            
            if response.status_code == 200:
                print(colored(f"✓ Connection successful! Response time: {elapsed:.2f}s", "GREEN"))
            else:
                print(colored(f"⚠ Received status code {response.status_code}. Response time: {elapsed:.2f}s", "YELLOW"))
                all_success = False
        except requests.exceptions.Timeout:
            print(colored(f"✗ Connection to {url} timed out after 10s", "RED"))
            all_success = False
        except requests.exceptions.ConnectionError as e:
            print(colored(f"✗ Connection error to {url}: {str(e)}", "RED"))
            all_success = False
        except Exception as e:
            print(colored(f"✗ Error connecting to {url}: {str(e)}", "RED"))
            all_success = False
    
    return all_success

def check_praw_config():
    """Check if PRAW configuration is available and valid."""
    print(colored("\nChecking PRAW configuration...", "BOLD"))
    
    # Load environment variables
    try:
        from dotenv import load_dotenv
        load_dotenv()
        print(colored("✓ Successfully loaded .env file", "GREEN"))
    except ImportError:
        print(colored("⚠ python-dotenv not installed, relying on system environment variables", "YELLOW"))
    except Exception as e:
        print(colored(f"⚠ Error loading .env: {str(e)}", "YELLOW"))
    
    # Check for required environment variables
    required_vars = ['REDDIT_CLIENT_ID', 'REDDIT_CLIENT_SECRET', 'REDDIT_USER_AGENT']
    missing_vars = []
    
    for var in required_vars:
        value = os.environ.get(var)
        if not value:
            print(colored(f"✗ Missing {var} environment variable", "RED"))
            missing_vars.append(var)
        else:
            masked_value = value[:4] + '*' * (len(value) - 4) if len(value) > 8 else '*' * len(value)
            print(colored(f"✓ Found {var}: {masked_value}", "GREEN"))
    
    return len(missing_vars) == 0

def test_praw_instance():
    """Test creating a PRAW instance and making a simple API call."""
    print(colored("\nTesting PRAW initialization...", "BOLD"))
    
    try:
        # Try to import praw
        import praw
        print(colored(f"✓ Successfully imported PRAW {praw.__version__}", "GREEN"))
        
        # Try to create a Reddit instance
        from tools.reddit import _get_reddit_instance
        
        print("Creating Reddit instance with timeout=60s...")
        reddit = _get_reddit_instance(timeout=60, max_retries=1)
        
        if reddit is None:
            print(colored("✗ Failed to initialize Reddit instance", "RED"))
            return False
        
        print(colored("✓ Successfully initialized Reddit instance", "GREEN"))
        
        # Try a simple API call
        try:
            print("Testing simple API call (accessing r/announcements)...")
            start_time = time.time()
            subreddit = reddit.subreddit('announcements')
            name = subreddit.display_name
            elapsed = time.time() - start_time
            
            print(colored(f"✓ API call successful! Retrieved r/{name} in {elapsed:.2f}s", "GREEN"))
            return True
        except Exception as e:
            print(colored(f"✗ API call failed: {str(e)}", "RED"))
            return False
    
    except ImportError as e:
        print(colored(f"✗ Failed to import PRAW: {str(e)}", "RED"))
        return False
    except Exception as e:
        print(colored(f"✗ Unexpected error: {str(e)}", "RED"))
        return False

def print_recommendations(network_ok, config_ok, praw_ok):
    """Print recommendations based on test results."""
    print(colored("\n=== RECOMMENDATIONS ===", "BOLD"))
    
    if network_ok and config_ok and praw_ok:
        print(colored("✓ All tests passed! Your Reddit tools should work correctly.", "GREEN"))
        print("If you're still experiencing issues, consider:")
        print("1. Checking for Reddit API rate limiting or downtime")
        print("2. Trying with a different Reddit API client ID")
        print("3. Increasing timeout values in the Reddit tools")
    else:
        if not network_ok:
            print(colored("1. Network connectivity issues detected:", "RED"))
            print("   - Check your internet connection")
            print("   - Verify that Reddit isn't blocked by your network/firewall")
            print("   - Try using a VPN or different network connection")
        
        if not config_ok:
            print(colored("2. Configuration issues detected:", "RED"))
            print("   - Make sure all required environment variables are set in your .env file:")
            print("     REDDIT_CLIENT_ID, REDDIT_CLIENT_SECRET, REDDIT_USER_AGENT")
            print("   - Create a new Reddit API application at https://www.reddit.com/prefs/apps")
            print("     and update your credentials")
        
        if not praw_ok:
            print(colored("3. PRAW initialization issues detected:", "RED"))
            print("   - Try reinstalling the praw package: pip install --upgrade praw")
            print("   - Check Reddit's status at https://reddit.statuspage.io/")
            print("   - Increase the timeout value in tools/reddit.py (DEFAULT_TIMEOUT)")

def main():
    """Run all tests and show recommendations."""
    print(colored("=== REDDIT TOOLS TROUBLESHOOTER ===", "BOLD"))
    print("This script will help diagnose issues with the Reddit tools.")
    
    # Check required packages
    print(colored("\nChecking required packages:", "BOLD"))
    packages = ['praw', 'requests', 'bs4']
    all_packages_ok = True
    
    for package in packages:
        installed, version = check_package(package)
        if installed:
            print(colored(f"✓ {package} is installed (version: {version})", "GREEN"))
        else:
            print(colored(f"✗ {package} is not installed: {version}", "RED"))
            all_packages_ok = False
    
    if not all_packages_ok:
        print(colored("\nMissing required packages. Please install them:", "RED"))
        print("pip install -r requirements.txt")
        return
    
    # Run the tests
    network_ok = check_reddit_connection()
    config_ok = check_praw_config()
    praw_ok = test_praw_instance()
    
    # Print recommendations
    print_recommendations(network_ok, config_ok, praw_ok)

if __name__ == "__main__":
    main()
