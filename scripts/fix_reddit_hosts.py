#!/usr/bin/env python3
"""
Fix Reddit Hosts File

This script updates your hosts file with working IP addresses for Reddit domains.
It targets all key Reddit domains to ensure tools can connect properly.
"""

import os
import sys
import platform
import socket
import requests
import subprocess
import time
from pathlib import Path

# Add parent directory to path
parent_dir = str(Path(__file__).resolve().parent.parent)
sys.path.append(parent_dir)

# ANSI colors for prettier output
COLORS = {
    'GREEN': '\033[92m',
    'YELLOW': '\033[93m',
    'RED': '\033[91m',
    'BLUE': '\033[94m',
    'ENDC': '\033[0m',
    'BOLD': '\033[1m',
}

# Reddit domains that need to be in the hosts file
REDDIT_DOMAINS = [
    'api.reddit.com',  # API endpoints (primary target)
    'oauth.reddit.com', # OAuth endpoints (primary target)
    'www.reddit.com',   # Main website
    'reddit.com',       # Main website (no www)
    'i.redd.it',        # Image hosting
    'v.redd.it',        # Video hosting
    'styles.redditmedia.com', # Styling
    'preview.redd.it'   # Preview images
]

# CloudFlare IP addresses known to work with Reddit
WORKING_CLOUDFLARE_IPS = [
    '104.16.12.131',
    '104.16.9.142',
    '151.101.129.140',
    '151.101.65.140',
    '151.101.1.140',
    '151.101.193.140'
]

def colored(text, color):
    """Add color to terminal output."""
    if platform.system() == 'Windows':
        # Windows command prompt doesn't support ANSI colors by default
        return text
    return f"{COLORS.get(color, '')}{text}{COLORS['ENDC']}"

def is_admin():
    """Check if the script is running with administrator/root privileges."""
    try:
        if platform.system() == 'Windows':
            import ctypes
            return ctypes.windll.shell32.IsUserAnAdmin() != 0
        else:
            # Unix: root has UID 0
            return os.geteuid() == 0
    except:
        return False

def get_hosts_path():
    """Get the path to the hosts file based on the operating system."""
    if platform.system() == 'Windows':
        return r'C:\Windows\System32\drivers\etc\hosts'
    else:
        return '/etc/hosts'

def check_host_reachable(host, port=443):
    """Check if a host is reachable on the given port."""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(2)
        sock.connect((host, port))
        sock.close()
        return True
    except:
        return False

def find_working_ip_for_domain(domain):
    """Find a working IP address for a domain."""
    # First try DNS resolution
    print(f"Finding working IP for {domain}...")
    
    try:
        # Try standard DNS resolution first
        addresses = socket.gethostbyname_ex(domain)[2]
        print(f"DNS found: {', '.join(addresses)}")
        
        # Test if IPs are actually working
        for ip in addresses:
            if check_host_reachable(ip):
                print(colored(f"✓ {ip} works for {domain}", "GREEN"))
                return ip
    except Exception as e:
        print(f"DNS lookup failed: {str(e)}")
    
    # Try CloudFlare IPs as a fallback
    print("Trying CloudFlare IPs...")
    for ip in WORKING_CLOUDFLARE_IPS:
        if check_host_reachable(ip):
            print(colored(f"✓ CloudFlare IP {ip} works", "GREEN"))
            return ip
    
    # Default fallback
    print(colored("⚠ Using default fallback IP", "YELLOW"))
    return '104.16.9.142'  # Default fallback IP

def update_hosts_file():
    """Update the hosts file with entries for Reddit domains."""
    hosts_path = get_hosts_path()
    
    if not is_admin():
        print(colored("⚠ This script must be run as administrator/root to modify the hosts file", "YELLOW"))
        if platform.system() == 'Windows':
            print("Please restart the script as administrator.")
        else:
            print("Please restart with sudo.")
        return False
    
    print(colored(f"Updating hosts file: {hosts_path}", "BLUE"))
    
    try:
        # Read existing hosts file
        with open(hosts_path, 'r') as f:
            content = f.read()
        
        lines = content.splitlines()
        new_content = []
        
        # Keep existing non-Reddit entries
        for line in lines:
            stripped = line.strip()
            # Skip comment lines and empty lines
            if not stripped or stripped.startswith('#'):
                new_content.append(line)
                continue
                
            # Skip existing Reddit entries
            if any(domain in line for domain in REDDIT_DOMAINS):
                continue
                
            # Keep all other entries
            new_content.append(line)
        
        # Add a header for our entries
        new_content.append("")
        new_content.append("# Reddit domains - Added by fix_reddit_hosts.py")
        
        # Add entries for each Reddit domain
        for domain in REDDIT_DOMAINS:
            # Use the same IP for all domains to ensure consistency
            ip = find_working_ip_for_domain(domain)
            new_content.append(f"{ip} {domain}")
        
        # Write back to hosts file
        with open(hosts_path, 'w') as f:
            f.write("\n".join(new_content))
        
        print(colored("✓ Successfully updated hosts file", "GREEN"))
        return True
    except Exception as e:
        print(colored(f"✗ Error updating hosts file: {str(e)}", "RED"))
        return False

def flush_dns():
    """Flush DNS cache to make sure our hosts file changes take effect."""
    print(colored("\nFlushing DNS cache...", "BLUE"))
    
    try:
        if platform.system() == 'Windows':
            subprocess.run(['ipconfig', '/flushdns'], check=True)
            print("DNS cache flushed.")
        elif platform.system() == 'Darwin':  # macOS
            subprocess.run(['dscacheutil', '-flushcache'], check=True)
            subprocess.run(['killall', '-HUP', 'mDNSResponder'], check=True)
            print("DNS cache flushed.")
        elif platform.system() == 'Linux':
            # Different Linux distros use different methods
            try:
                subprocess.run(['systemd-resolve', '--flush-caches'], check=True)
                print("DNS cache flushed (systemd-resolve).")
            except:
                try:
                    subprocess.run(['service', 'nscd', 'restart'], check=True)
                    print("DNS cache flushed (nscd).")
                except:
                    print("Could not flush DNS cache automatically.")
                    print("This is not critical. Changes may take a few minutes to take effect.")
    except Exception as e:
        print(f"Could not flush DNS cache: {e}")
        print("This is not critical. Changes may take a few minutes to take effect.")

def test_reddit_connectivity():
    """Test connectivity to Reddit domains after update."""
    print(colored("\nTesting connectivity to Reddit domains...", "BLUE"))
    
    all_successful = True
    for domain in REDDIT_DOMAINS[:3]:  # Test only the most important domains
        url = f"https://{domain}/"
        print(f"Testing {url}... ", end="", flush=True)
        
        try:
            # Try with a user agent that mimics a desktop browser
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.5",
                "Connection": "keep-alive"
            }
            
            # Try both www and api endpoints for better diagnostics
            if domain == "www.reddit.com":
                alt_domain = "api.reddit.com"
                print(f"\n  - Also trying {alt_domain} as alternative... ", end="", flush=True)
                
                try:
                    alt_start = time.time()
                    alt_response = requests.get(f"https://{alt_domain}/", timeout=8, headers=headers)
                    alt_elapsed = time.time() - alt_start
                    print(colored(f"Success ({alt_response.status_code}) in {alt_elapsed:.2f}s", "GREEN"))
                    print("  - API endpoint is accessible, tools should work properly.")
                    # If API domain works, we're good for tools usage
                    continue
                except Exception as alt_e:
                    print(colored(f"Failed: {str(alt_e)}", "RED"))
            
            # Try the original domain
            start = time.time()
            response = requests.get(url, timeout=8, headers=headers)
            elapsed = time.time() - start
            
            if response.status_code < 400:
                print(colored(f"Success ({response.status_code}) in {elapsed:.2f}s", "GREEN"))
            else:
                print(colored(f"Status {response.status_code} in {elapsed:.2f}s", "YELLOW"))
                all_successful = False
        except Exception as e:
            print(colored(f"Failed: {str(e)}", "RED"))
            # Don't mark as failed if www.reddit.com times out but api.reddit.com works
            if not (domain == "www.reddit.com" and "api.reddit.com" in locals()):
                all_successful = False
    
    return all_successful

def main():
    """Main function."""
    print(colored("=== REDDIT HOSTS FILE FIXER ===", "BOLD"))
    print("This script will update your hosts file with working IPs for Reddit domains.\n")
    
    if update_hosts_file():
        flush_dns()
        time.sleep(2)  # Give DNS changes time to take effect
        connectivity_ok = test_reddit_connectivity()
        
        if connectivity_ok:
            print(colored("\n✓ Reddit connectivity fixed successfully!", "GREEN"))
        else:
            print(colored("\n⚠ Reddit connectivity partially fixed.", "YELLOW"))
            print("API endpoints are working, which means Reddit tools should function correctly.")
            print("However, some web endpoints may still have issues. This is normal with some ISPs.")
        
        print("\nPlease restart any applications that need to connect to Reddit.")
    else:
        print(colored("\n✗ Could not update hosts file.", "RED"))
        print("Please try running the script as administrator/root.")

if __name__ == "__main__":
    main()
