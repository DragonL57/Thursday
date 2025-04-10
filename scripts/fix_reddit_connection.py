#!/usr/bin/env python3
"""
Diagnostic and fix script for Reddit connection issues in the personal-gem project.
This script attempts various methods to detect and fix connection problems with Reddit.
"""

import os
import sys
import time
import socket
import threading
import traceback
import argparse
import ipaddress
from concurrent.futures import ThreadPoolExecutor, as_completed

# Add the parent directory to the path to import the tools module
parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(parent_dir)

try:
    import requests
    from dotenv import load_dotenv
    import praw
except ImportError as e:
    print(f"Missing required package: {e}")
    print("Please run: pip install requests python-dotenv praw")
    sys.exit(1)

# ANSI color codes
COLORS = {
    'GREEN': '\033[92m',
    'YELLOW': '\033[93m',
    'RED': '\033[91m',
    'BLUE': '\033[94m',
    'CYAN': '\033[96m',
    'ENDC': '\033[0m',
    'BOLD': '\033[1m',
}

# Reddit domains to test
REDDIT_DOMAINS = [
    'www.reddit.com',
    'api.reddit.com',
    'oauth.reddit.com',
    'old.reddit.com',
    'i.redd.it'
]

def colored(text, color):
    """Add color to terminal output."""
    return f"{COLORS.get(color, '')}{text}{COLORS['ENDC']}"

def check_dns_resolution(domain):
    """Check if a domain can be resolved via DNS."""
    try:
        print(f"Resolving DNS for {domain}...")
        ip_addresses = socket.gethostbyname_ex(domain)[2]
        print(colored(f"  ✓ DNS resolves to: {', '.join(ip_addresses)}", "GREEN"))
        return True, ip_addresses
    except socket.gaierror as e:
        print(colored(f"  ✗ DNS resolution failed: {e}", "RED"))
        return False, []
    except Exception as e:
        print(colored(f"  ✗ Error during DNS lookup: {e}", "RED"))
        return False, []

def check_connection(url, timeout=5):
    """Check connection to a URL."""
    try:
        print(f"Testing connection to {url}...")
        start_time = time.time()
        response = requests.get(url, timeout=timeout)
        elapsed = time.time() - start_time
        
        if response.status_code == 200:
            print(colored(f"  ✓ Connection successful: HTTP {response.status_code}, {elapsed:.2f}s", "GREEN"))
            return True
        else:
            print(colored(f"  ⚠ Received HTTP {response.status_code}: {response.reason}, {elapsed:.2f}s", "YELLOW"))
            return response.status_code < 400
    except requests.exceptions.Timeout:
        print(colored(f"  ✗ Connection timed out after {timeout}s", "RED"))
        return False
    except requests.exceptions.ConnectionError as e:
        print(colored(f"  ✗ Connection error: {e}", "RED"))
        return False
    except Exception as e:
        print(colored(f"  ✗ Error: {e}", "RED"))
        return False

def check_praw_config():
    """Check if PRAW configuration is available and valid."""
    print(colored("\nChecking PRAW configuration...", "BOLD"))
    
    # Load environment variables
    load_dotenv()
    
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

def test_socket_connection(host, port=443, timeout=5):
    """Test direct socket connection to a host and port."""
    try:
        print(f"Testing direct socket connection to {host}:{port}...")
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        
        start_time = time.time()
        sock.connect((host, port))
        elapsed = time.time() - start_time
        
        sock.close()
        print(colored(f"  ✓ Socket connection successful in {elapsed:.2f}s", "GREEN"))
        return True
    except socket.timeout:
        print(colored(f"  ✗ Socket connection timed out after {timeout}s", "RED"))
        return False
    except socket.error as e:
        print(colored(f"  ✗ Socket error: {e}", "RED"))
        return False
    except Exception as e:
        print(colored(f"  ✗ Error: {e}", "RED"))
        return False

def create_hosts_entry(domain, ip_address):
    """Create a hosts file entry."""
    hosts_path = "/etc/hosts" if sys.platform != "win32" else r"C:\Windows\System32\drivers\etc\hosts"
    hosts_entry = f"{ip_address} {domain}"
    
    print(f"Creating hosts entry: {hosts_entry}")
    print(f"To add this entry, run:")
    if sys.platform != "win32":
        # Linux/macOS
        print(colored(f"  sudo echo '{hosts_entry}' >> {hosts_path}", "CYAN"))
    else:
        # Windows
        print(colored(f"  1. Run Notepad as administrator", "CYAN"))
        print(colored(f"  2. Open {hosts_path}", "CYAN"))
        print(colored(f"  3. Add this line at the end: {hosts_entry}", "CYAN"))
        print(colored(f"  4. Save the file", "CYAN"))

def find_working_reddit_api_ip(test_domain='api.reddit.com'):
    """
    Find a working IP address for Reddit API by testing CloudFlare IPs.
    """
    print(colored(f"\nLooking for working alternative IP addresses for {test_domain}...", "BOLD"))
    
    # First try resolving the domain naturally
    dns_ok, ip_addresses = check_dns_resolution(test_domain)
    if dns_ok:
        print("Testing IP addresses from DNS resolution...")
        for ip in ip_addresses:
            if test_socket_connection(ip):
                return ip
    
    # CloudFlare IP ranges that might work
    cloudflare_ranges = [
        '104.16.0.0/12',
        '172.64.0.0/13',
        '131.0.72.0/22'
    ]
    
    cf_ips_to_test = []
    for ip_range in cloudflare_ranges:
        network = ipaddress.ip_network(ip_range)
        # Take a small sample from each range
        sample_size = min(5, network.num_addresses)
        sample_ips = [str(ip) for ip in list(network.hosts())[:sample_size]]
        cf_ips_to_test.extend(sample_ips)
    
    print(f"Testing {len(cf_ips_to_test)} sample IPs from CloudFlare ranges...")
    
    with ThreadPoolExecutor(max_workers=10) as executor:
        # Submit all tests
        future_to_ip = {
            executor.submit(test_socket_connection, ip): ip 
            for ip in cf_ips_to_test
        }
        
        # Process results as they complete
        working_ips = []
        for future in as_completed(future_to_ip):
            ip = future_to_ip[future]
            try:
                if future.result():
                    working_ips.append(ip)
                    if len(working_ips) >= 3:  # Find a few working IPs
                        break
            except Exception as e:
                print(f"Error testing {ip}: {e}")
    
    if working_ips:
        print(colored(f"Found {len(working_ips)} working IP addresses!", "GREEN"))
        for ip in working_ips:
            create_hosts_entry(test_domain, ip)
        return working_ips[0]
    else:
        print(colored("Could not find working alternative IPs", "RED"))
        return None

def test_timeout_values():
    """Test with different timeout values."""
    print(colored("\nTesting with different timeout values...", "BOLD"))
    
    for timeout in [10, 20, 30, 45, 60]:
        print(f"Testing with {timeout} second timeout...")
        start_time = time.time()
        result = check_connection('https://api.reddit.com/', timeout)
        elapsed = time.time() - start_time
        
        if result:
            print(colored(f"  ✓ Connection successful with {timeout}s timeout (actual time: {elapsed:.2f}s)", "GREEN"))
            return timeout
        else:
            print(colored(f"  ✗ Connection failed with {timeout}s timeout", "RED"))
    
    return None

def test_praw_connection(timeout=45):
    """Test PRAW connection with given timeout."""
    print(colored(f"\nTesting PRAW connection with {timeout}s timeout...", "BOLD"))
    
    try:
        # Import from tools.reddit if possible
        try:
            from tools.reddit import _get_reddit_instance
            reddit = _get_reddit_instance(timeout=timeout, max_retries=1)
        except ImportError:
            # Fall back to local implementation
            config = {
                'client_id': os.environ.get('REDDIT_CLIENT_ID'),
                'client_secret': os.environ.get('REDDIT_CLIENT_SECRET'),
                'user_agent': os.environ.get('REDDIT_USER_AGENT'),
                'timeout': timeout
            }
            reddit = praw.Reddit(**config)
        
        if not reddit:
            print(colored("  ✗ Failed to initialize Reddit instance", "RED"))
            return False
        
        print(colored("  ✓ Successfully initialized Reddit instance", "GREEN"))
        
        # Try making an actual API call
        try:
            print("  Testing API call (accessing r/announcements)...")
            start_time = time.time()
            subreddit = reddit.subreddit('announcements')
            name = subreddit.display_name
            elapsed = time.time() - start_time
            
            print(colored(f"  ✓ API call successful! Retrieved r/{name} in {elapsed:.2f}s", "GREEN"))
            return True
        except Exception as e:
            print(colored(f"  ✗ API call failed: {str(e)}", "RED"))
            return False
    except Exception as e:
        print(colored(f"  ✗ Error initializing PRAW: {str(e)}", "RED"))
        traceback.print_exc()
        return False

def update_timeout_value(new_timeout):
    """Update the DEFAULT_TIMEOUT value in the reddit.py file."""
    reddit_tool_path = os.path.join(parent_dir, 'tools', 'reddit.py')
    
    if not os.path.exists(reddit_tool_path):
        print(colored(f"  ✗ File not found: {reddit_tool_path}", "RED"))
        return False
    
    try:
        # Read the current file
        with open(reddit_tool_path, 'r') as file:
            content = file.read()
        
        # Update the timeout value
        import re
        updated_content = re.sub(
            r'DEFAULT_TIMEOUT\s*=\s*\d+',
            f'DEFAULT_TIMEOUT = {new_timeout}',
            content
        )
        
        if content == updated_content:
            print(colored("  ⚠ DEFAULT_TIMEOUT value not found in file or already set to this value", "YELLOW"))
            return False
        
        # Write the updated file
        with open(reddit_tool_path, 'w') as file:
            file.write(updated_content)
        
        print(colored(f"  ✓ Updated DEFAULT_TIMEOUT to {new_timeout} in {reddit_tool_path}", "GREEN"))
        return True
    except Exception as e:
        print(colored(f"  ✗ Error updating timeout value: {str(e)}", "RED"))
        return False

def generate_recommendations(dns_results, connection_results, working_timeout):
    """Generate recommendations based on test results."""
    print(colored("\n=== RECOMMENDATIONS ===", "BOLD"))
    
    all_ok = True
    recommendations = []
    
    # Check DNS issues
    dns_issues = [domain for domain, (status, _) in dns_results.items() if not status]
    if dns_issues:
        all_ok = False
        recommendations.append(f"1. DNS resolution issues detected for: {', '.join(dns_issues)}")
        recommendations.append(f"   - Consider using a different DNS server (e.g., 8.8.8.8 or 1.1.1.1)")
        recommendations.append(f"   - Or add manual hosts entries as shown above")
    
    # Check connection issues
    conn_issues = [url for url, status in connection_results.items() if not status]
    if conn_issues:
        all_ok = False
        recommendations.append(f"2. Connection issues detected for: {', '.join(conn_issues)}")
        recommendations.append(f"   - Your network might be blocking these domains")
        recommendations.append(f"   - Try using a VPN or different network connection")
        recommendations.append(f"   - Or update your hosts file with working IPs as shown above")
    
    # Timeout recommendations
    if working_timeout:
        if working_timeout > 30:
            recommendations.append(f"3. Connection successful but slow ({working_timeout}s timeout required)")
            recommendations.append(f"   - We've updated the DEFAULT_TIMEOUT value in reddit.py")
            recommendations.append(f"   - Your connection to Reddit is working but slow; consider a better network")
    else:
        all_ok = False
        recommendations.append(f"3. Could not establish connection with any timeout value")
        recommendations.append(f"   - Try using a VPN or different network connection")
        recommendations.append(f"   - Check if your firewall is blocking outbound connections")
    
    if all_ok:
        print(colored("All tests passed! Your connection to Reddit should work correctly.", "GREEN"))
    else:
        for recommendation in recommendations:
            print(colored(recommendation, "YELLOW"))

def main():
    parser = argparse.ArgumentParser(description='Fix Reddit connection issues')
    parser.add_argument('--update-timeout', type=int, help='Update the DEFAULT_TIMEOUT value')
    parser.add_argument('--find-ip', action='store_true', help='Find working alternative IPs')
    parser.add_argument('--test-praw', action='store_true', help='Test PRAW connection directly')
    parser.add_argument('--all', action='store_true', help='Run all tests')
    
    args = parser.parse_args()
    
    run_all = args.all or (not any([args.update_timeout, args.find_ip, args.test_praw]))
    
    print(colored("=== REDDIT CONNECTION FIXER ===", "BOLD"))
    print("This script diagnoses and attempts to fix Reddit connection issues.\n")
    
    # Check PRAW configuration
    praw_config_ok = check_praw_config()
    if not praw_config_ok:
        print(colored("\nPlease fix PRAW configuration issues before continuing.", "RED"))
        return
    
    # Test DNS resolution for Reddit domains
    print(colored("\nChecking DNS resolution for Reddit domains...", "BOLD"))
    dns_results = {}
    for domain in REDDIT_DOMAINS:
        dns_results[domain] = check_dns_resolution(domain)
    
    # Test connections to Reddit URLs
    print(colored("\nTesting connections to Reddit URLs...", "BOLD"))
    connection_results = {}
    for domain in REDDIT_DOMAINS:
        connection_results[f"https://{domain}/"] = check_connection(f"https://{domain}/")
    
    # Find the best timeout value
    working_timeout = None
    if run_all or args.update_timeout:
        working_timeout = test_timeout_values()
        if working_timeout and (run_all or args.update_timeout):
            if args.update_timeout:
                working_timeout = args.update_timeout
            update_timeout_value(working_timeout)
    
    # Find alternative IPs if needed
    if (run_all and any(not status for url, status in connection_results.items())) or args.find_ip:
        working_ip = find_working_reddit_api_ip()
    
    # Test PRAW connection
    if run_all or args.test_praw:
        test_praw_connection(timeout=working_timeout or 45)
    
    # Generate recommendations
    if run_all:
        generate_recommendations(dns_results, connection_results, working_timeout)
    
    print(colored("\nTests completed. If issues persist, try running with --all flag.", "BOLD"))

if __name__ == "__main__":
    main()
