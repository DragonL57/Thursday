#!/usr/bin/env python3
"""
Reddit VPN Manager for Personal-Gem

This script sets up and manages a specialized VPN connection that routes only Reddit traffic 
through a secure tunnel, leaving other internet traffic untouched. This approach helps 
bypass Reddit connectivity issues while maintaining normal network access for everything else.

Requirements:
- sshuttle (lightweight VPN-like tool): pip install sshuttle
- An SSH server with internet access that can reach Reddit

Usage:
  python reddit_vpn.py check     # Check if Reddit needs VPN access
  python reddit_vpn.py start     # Start the Reddit VPN tunnel
  python reddit_vpn.py stop      # Stop the Reddit VPN tunnel
  python reddit_vpn.py status    # Check if Reddit VPN is running
  python reddit_vpn.py test      # Test Reddit tools with/without VPN
"""

import os
import sys
import socket
import subprocess
import time
import signal
import requests
import argparse
import json
import platform
from pathlib import Path
import threading
import ipaddress

# Add the parent directory to the path to import the tools module
parent_dir = str(Path(__file__).resolve().parent.parent)
sys.path.append(parent_dir)

try:
    import requests
    from dotenv import load_dotenv
except ImportError as e:
    print(f"Missing required package: {e}")
    print("Please run: pip install requests python-dotenv")
    sys.exit(1)

# ANSI color codes
COLORS = {
    'GREEN': '\033[92m',
    'YELLOW': '\033[93m',
    'RED': '\033[91m',
    'BLUE': '\033[94m',
    'CYAN': '\033[96m',
    'MAGENTA': '\033[95m',
    'ENDC': '\033[0m',
    'BOLD': '\033[1m',
}

# Reddit domains that need VPN access
REDDIT_DOMAINS = [
    'www.reddit.com',
    'reddit.com',
    'api.reddit.com',
    'oauth.reddit.com',
    'old.reddit.com',
    'i.redd.it',
    'v.redd.it',
    'preview.redd.it',
    'styles.redditmedia.com',
    'external-preview.redd.it'
]

# Configuration file path
CONFIG_FILE = os.path.join(parent_dir, 'config', 'reddit_vpn.json')
PID_FILE = os.path.join(parent_dir, 'config', 'reddit_vpn.pid')

# Default SSH configuration - will be overridden by user config
DEFAULT_CONFIG = {
    'ssh_host': '',           # SSH server address
    'ssh_port': 22,           # SSH port
    'ssh_user': '',           # SSH username
    'ssh_key': '',            # Path to SSH key
    'auto_start': False,      # Automatically start VPN when needed
    'connection_timeout': 10, # Connection timeout in seconds
    'last_checked': 0,        # Timestamp of last connectivity check
    'check_interval': 3600,   # How often to recheck connectivity (seconds)
}

def colored(text, color):
    """Add color to terminal output."""
    return f"{COLORS.get(color, '')}{text}{COLORS['ENDC']}"

def create_directory(path):
    """Create directory if it doesn't exist."""
    os.makedirs(path, exist_ok=True)

def load_config():
    """Load configuration from file or create with default values."""
    create_directory(os.path.dirname(CONFIG_FILE))
    
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r') as f:
                config = json.load(f)
                # Merge with defaults in case the config file is missing fields
                return {**DEFAULT_CONFIG, **config}
        except Exception as e:
            print(colored(f"Error loading configuration: {e}", "RED"))
    
    # If no config exists, create a new one with default values
    save_config(DEFAULT_CONFIG)
    return DEFAULT_CONFIG

def save_config(config):
    """Save configuration to file."""
    create_directory(os.path.dirname(CONFIG_FILE))
    
    try:
        with open(CONFIG_FILE, 'w') as f:
            json.dump(config, f, indent=2)
    except Exception as e:
        print(colored(f"Error saving configuration: {e}", "RED"))

def setup_config():
    """Interactive setup for VPN configuration."""
    config = load_config()
    
    print(colored("\n=== Reddit VPN Configuration ===", "BOLD"))
    print("This setup will configure a specialized VPN for Reddit access.")
    print("You'll need an SSH server with internet access that can reach Reddit.\n")
    
    config['ssh_host'] = input(f"SSH server address [{config['ssh_host']}]: ") or config['ssh_host']
    config['ssh_port'] = int(input(f"SSH server port [{config['ssh_port']}]: ") or config['ssh_port'])
    config['ssh_user'] = input(f"SSH username [{config['ssh_user']}]: ") or config['ssh_user']
    
    default_key = config['ssh_key'] or os.path.expanduser("~/.ssh/id_rsa")
    config['ssh_key'] = input(f"Path to SSH private key [{default_key}]: ") or default_key
    
    auto_default = "yes" if config['auto_start'] else "no"
    auto_resp = input(f"Automatically start VPN when needed? (yes/no) [{auto_default}]: ").lower() or auto_default
    config['auto_start'] = auto_resp.startswith('y')
    
    save_config(config)
    print(colored("\nConfiguration saved successfully!", "GREEN"))

def get_reddit_ips():
    """Get IP addresses for Reddit domains."""
    print(colored("Resolving Reddit IP addresses...", "BLUE"))
    ip_addresses = set()
    
    for domain in REDDIT_DOMAINS:
        try:
            print(f"Looking up {domain}...")
            ips = socket.gethostbyname_ex(domain)[2]
            for ip in ips:
                ip_addresses.add(ip)
            print(colored(f"  ✓ {domain} resolves to: {', '.join(ips)}", "GREEN"))
        except socket.gaierror as e:
            print(colored(f"  ✗ Failed to resolve {domain}: {e}", "RED"))
        except Exception as e:
            print(colored(f"  ✗ Error looking up {domain}: {e}", "RED"))
    
    # Convert IPs to CIDR notation for sshuttle
    cidr_ranges = []
    for ip in ip_addresses:
        cidr_ranges.append(f"{ip}/32")
    
    # Add CloudFlare IP ranges commonly used by Reddit
    cloudflare_ranges = [
        '104.16.0.0/12',
        '172.64.0.0/13',
        '131.0.72.0/22'
    ]
    cidr_ranges.extend(cloudflare_ranges)
    
    return cidr_ranges

def check_connectivity(timeout=10):
    """Check connectivity to Reddit services."""
    print(colored("\nChecking Reddit connectivity...", "BLUE"))
    all_accessible = True
    results = {}
    
    for domain in REDDIT_DOMAINS[:3]:  # Just check the main domains
        url = f"https://{domain}/"
        try:
            print(f"Testing connection to {url}...")
            start_time = time.time()
            response = requests.get(url, timeout=timeout)
            elapsed = time.time() - start_time
            
            if response.status_code < 400:
                print(colored(f"  ✓ Connection successful: {response.status_code}, {elapsed:.2f}s", "GREEN"))
                results[domain] = True
            else:
                print(colored(f"  ⚠ Received status {response.status_code}: {response.reason}, {elapsed:.2f}s", "YELLOW"))
                results[domain] = False
                all_accessible = False
        except requests.exceptions.RequestException as e:
            print(colored(f"  ✗ Connection failed: {e}", "RED"))
            results[domain] = False
            all_accessible = False
    
    # Test PRAW direct access
    try:
        from tools.reddit import _get_reddit_instance
        print("Testing Reddit API access through PRAW...")
        
        reddit = _get_reddit_instance(timeout=timeout)
        if reddit:
            # Try a simple API call
            subreddit = reddit.subreddit('announcements')
            name = subreddit.display_name
            print(colored(f"  ✓ PRAW connection successful (r/{name})", "GREEN"))
            results["praw_api"] = True
        else:
            print(colored(f"  ✗ PRAW initialization failed", "RED"))
            results["praw_api"] = False
            all_accessible = False
    except Exception as e:
        print(colored(f"  ✗ PRAW test failed: {e}", "RED"))
        results["praw_api"] = False
        all_accessible = False
    
    # Update last checked time
    config = load_config()
    config['last_checked'] = int(time.time())
    save_config(config)
    
    return all_accessible, results

def is_vpn_running():
    """Check if the Reddit VPN is currently running."""
    if not os.path.exists(PID_FILE):
        return False
    
    try:
        with open(PID_FILE, 'r') as f:
            pid = int(f.read().strip())
        
        # Check if process is running
        os.kill(pid, 0)
        return True
    except (OSError, ValueError, ProcessLookupError):
        # Process not running
        return False

def start_vpn():
    """Start the Reddit VPN tunnel using sshuttle."""
    # Check if VPN is already running
    if is_vpn_running():
        print(colored("Reddit VPN is already running", "YELLOW"))
        return True
    
    config = load_config()
    
    # Check for required configuration
    if not config['ssh_host'] or not config['ssh_user']:
        print(colored("VPN configuration is incomplete. Please run 'setup' command first.", "RED"))
        return False
    
    # Get Reddit IP ranges
    reddit_cidrs = get_reddit_ips()
    
    if not reddit_cidrs:
        print(colored("Failed to resolve Reddit IP addresses", "RED"))
        return False
    
    # Build sshuttle command
    ssh_key_param = ['-e', f'ssh -i {config["ssh_key"]}'] if config['ssh_key'] else []
    ssh_dest = f"{config['ssh_user']}@{config['ssh_host']}"
    
    command = ['sshuttle', '-r', ssh_dest, '--daemon', '--pidfile', PID_FILE] + ssh_key_param
    command.extend(reddit_cidrs)
    
    print(colored("\nStarting Reddit VPN tunnel...", "BLUE"))
    print(f"Using SSH server: {ssh_dest}")
    print(f"Routing {len(reddit_cidrs)} network ranges through VPN")
    
    try:
        subprocess.run(command, check=True)
        time.sleep(1)  # Give it a moment to start
        
        if is_vpn_running():
            print(colored("✓ Reddit VPN started successfully!", "GREEN"))
            return True
        else:
            print(colored("✗ Failed to start Reddit VPN", "RED"))
            return False
    except subprocess.CalledProcessError as e:
        print(colored(f"✗ Error starting VPN: {e}", "RED"))
        print("\nIs sshuttle installed? If not, install it with: pip install sshuttle")
        return False
    except FileNotFoundError:
        print(colored("✗ sshuttle not found. Please install it with: pip install sshuttle", "RED"))
        return False

def stop_vpn():
    """Stop the Reddit VPN tunnel."""
    if not is_vpn_running():
        print(colored("Reddit VPN is not running", "YELLOW"))
        return True
    
    try:
        with open(PID_FILE, 'r') as f:
            pid = int(f.read().strip())
        
        print(colored("Stopping Reddit VPN...", "BLUE"))
        os.kill(pid, signal.SIGTERM)
        
        # Wait for the process to terminate
        for _ in range(5):
            try:
                os.kill(pid, 0)
                time.sleep(0.5)
            except OSError:
                break
        
        # Remove PID file
        if os.path.exists(PID_FILE):
            os.remove(PID_FILE)
        
        print(colored("✓ Reddit VPN stopped successfully", "GREEN"))
        return True
    except (OSError, ValueError, ProcessLookupError) as e:
        print(colored(f"Error stopping VPN: {e}", "RED"))
        
        # Clean up stale PID file
        if os.path.exists(PID_FILE):
            os.remove(PID_FILE)
        
        return False

def vpn_status():
    """Check and display the status of the Reddit VPN."""
    running = is_vpn_running()
    config = load_config()
    
    print(colored("\n=== Reddit VPN Status ===", "BOLD"))
    
    if running:
        print(colored("Status: ACTIVE", "GREEN"))
        try:
            with open(PID_FILE, 'r') as f:
                pid = f.read().strip()
            print(f"Process ID: {pid}")
        except Exception:
            print("Process ID: Unknown")
    else:
        print(colored("Status: INACTIVE", "YELLOW"))
    
    print(f"\nConfiguration:")
    print(f"  SSH Server: {config['ssh_user']}@{config['ssh_host']}:{config['ssh_port']}")
    print(f"  SSH Key: {config['ssh_key']}")
    print(f"  Auto-start: {'Enabled' if config['auto_start'] else 'Disabled'}")
    
    # Print last connectivity check
    if config['last_checked'] > 0:
        last_check_time = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(config['last_checked']))
        print(f"\nLast connectivity check: {last_check_time}")
        
        # Check if a new check is needed
        time_since_check = int(time.time()) - config['last_checked']
        if time_since_check > config['check_interval']:
            print(colored(f"Connectivity check is stale ({time_since_check//3600} hours old)", "YELLOW"))
            print(f"Run 'check' command to perform a new connectivity test")
    else:
        print("\nConnectivity never checked")
        print(f"Run 'check' command to test connectivity")

def test_reddit_tools():
    """Test the Reddit tools with and without VPN."""
    # Import the Reddit tools
    try:
        from tools.reddit import search_reddit_posts, get_reddit_post, get_subreddit_posts
    except ImportError:
        print(colored("Failed to import Reddit tools", "RED"))
        return False
    
    # Function to run a simple test
    def run_simple_test():
        print(colored("\nTesting Reddit tools...", "BOLD"))
        
        try:
            # Simple search
            print("Testing search_reddit_posts...")
            results = search_reddit_posts(query="python programming", limit=2)
            if isinstance(results, list) and results and "error" not in results[0]:
                print(colored("  ✓ search_reddit_posts successful", "GREEN"))
            else:
                print(colored("  ✗ search_reddit_posts failed", "RED"))
                if results and isinstance(results, list) and "error" in results[0]:
                    print(f"    Error: {results[0]['error']}")
            
            # Get a subreddit's posts
            print("Testing get_subreddit_posts...")
            results = get_subreddit_posts(subreddit="Python", limit=2)
            if isinstance(results, list) and results and "error" not in results[0]:
                print(colored("  ✓ get_subreddit_posts successful", "GREEN"))
            else:
                print(colored("  ✗ get_subreddit_posts failed", "RED"))
                if results and isinstance(results, list) and "error" in results[0]:
                    print(f"    Error: {results[0]['error']}")
            
            return True
        except Exception as e:
            print(colored(f"Error testing Reddit tools: {e}", "RED"))
            return False
    
    # Test without VPN
    vpn_was_running = is_vpn_running()
    
    if vpn_was_running:
        print(colored("Stopping VPN for initial test...", "BLUE"))
        stop_vpn()
    
    print(colored("\n=== Testing without VPN ===", "MAGENTA"))
    without_vpn_success = run_simple_test()
    
    # Test with VPN
    print(colored("\n=== Testing with VPN ===", "MAGENTA"))
    print(colored("Starting VPN...", "BLUE"))
    start_vpn()
    time.sleep(2)  # Give VPN a moment to establish
    
    with_vpn_success = run_simple_test()
    
    # Restore previous VPN state
    if not vpn_was_running:
        print(colored("Stopping VPN to restore previous state...", "BLUE"))
        stop_vpn()
    
    # Print summary
    print(colored("\n=== Test Summary ===", "BOLD"))
    print(f"Without VPN: {'✓ Working' if without_vpn_success else '✗ Not Working'}")
    print(f"With VPN:    {'✓ Working' if with_vpn_success else '✗ Not Working'}")
    
    if not without_vpn_success and with_vpn_success:
        print(colored("\nRecommendation: Use VPN for Reddit access", "GREEN"))
        print("Run 'reddit_vpn.py start' before using Reddit tools")
    elif without_vpn_success and with_vpn_success:
        print(colored("\nBoth methods work! VPN is optional.", "GREEN"))
    elif not without_vpn_success and not with_vpn_success:
        print(colored("\nNeither method works.", "RED"))
        print("Check your internet connection and Reddit API credentials.")
    else:  # without_vpn_success and not with_vpn_success
        print(colored("\nDirect connection works better than VPN!", "YELLOW"))
        print("No need to use the VPN.")
    
    return with_vpn_success or without_vpn_success

def check_requirements():
    """Check if all required tools are installed."""
    print(colored("Checking requirements...", "BLUE"))
    
    # Check for sshuttle
    try:
        subprocess.run(['sshuttle', '--version'], stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
        print(colored("✓ sshuttle is installed", "GREEN"))
    except FileNotFoundError:
        print(colored("✗ sshuttle is not installed", "RED"))
        print("Install it with: pip install sshuttle")
        return False
    
    # Check for SSH
    try:
        subprocess.run(['ssh', '-V'], stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
        print(colored("✓ SSH is installed", "GREEN"))
    except FileNotFoundError:
        print(colored("✗ SSH is not installed", "RED"))
        if platform.system() == "Windows":
            print("Install OpenSSH or Git Bash")
        else:
            print("Install OpenSSH client")
        return False
    
    return True

def auto_manage():
    """Automatically manage VPN based on Reddit connectivity."""
    config = load_config()
    
    # Skip if auto-start is disabled
    if not config['auto_start']:
        return
    
    # Check if we need to test connectivity
    current_time = int(time.time())
    time_since_check = current_time - config['last_checked']
    
    if time_since_check > config['check_interval']:
        print(colored("Checking Reddit connectivity for auto-management...", "BLUE"))
        accessible, results = check_connectivity(config['connection_timeout'])
        
        if not accessible:
            if not is_vpn_running():
                print(colored("Reddit appears inaccessible. Starting VPN...", "YELLOW"))
                start_vpn()
        else:
            if is_vpn_running():
                print(colored("Reddit is directly accessible. Stopping VPN...", "GREEN"))
                stop_vpn()

def main():
    parser = argparse.ArgumentParser(description='Reddit VPN Manager for Personal-Gem')
    subparsers = parser.add_subparsers(dest='command', help='Command to execute')
    
    # Setup command
    subparsers.add_parser('setup', help='Configure the Reddit VPN')
    
    # Check command
    subparsers.add_parser('check', help='Check Reddit connectivity')
    
    # Start command
    subparsers.add_parser('start', help='Start the Reddit VPN')
    
    # Stop command
    subparsers.add_parser('stop', help='Stop the Reddit VPN')
    
    # Status command
    subparsers.add_parser('status', help='Check VPN status')
    
    # Test command
    subparsers.add_parser('test', help='Test Reddit tools with and without VPN')
    
    # Auto command
    subparsers.add_parser('auto', help='Automatically manage VPN based on connectivity')
    
    args = parser.parse_args()
    
    print(colored("=== Reddit VPN Manager ===", "BOLD"))
    
    # Check for command
    if not args.command:
        parser.print_help()
        return
    
    # Setup command
    if args.command == 'setup':
        setup_config()
    
    # Check if requirements are met for other commands
    elif args.command in ['start', 'check', 'test', 'auto']:
        if not check_requirements():
            return
    
    # Execute the specified command
    if args.command == 'check':
        accessible, results = check_connectivity()
        
        print(colored("\n=== Connectivity Summary ===", "BOLD"))
        if accessible:
            print(colored("✓ Reddit is directly accessible", "GREEN"))
            print("VPN is not needed for Reddit access.")
        else:
            print(colored("✗ Reddit has connectivity issues", "RED"))
            print("Using a VPN is recommended for reliable Reddit access.")
            
            # Ask to start VPN if needed
            config = load_config()
            if config['auto_start']:
                if not is_vpn_running():
                    print("Auto-start is enabled. Starting VPN...")
                    start_vpn()
            else:
                if not is_vpn_running():
                    response = input("Start the Reddit VPN now? (y/n): ").lower()
                    if response.startswith('y'):
                        start_vpn()
    
    elif args.command == 'start':
        start_vpn()
    
    elif args.command == 'stop':
        stop_vpn()
    
    elif args.command == 'status':
        vpn_status()
    
    elif args.command == 'test':
        test_reddit_tools()
    
    elif args.command == 'auto':
        auto_manage()

if __name__ == "__main__":
    main()
