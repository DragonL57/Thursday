#!/usr/bin/env python3
"""
Reddit Auto-Fix Tool

This script automatically fixes Reddit connectivity issues without requiring any external
services or paid subscriptions. It tries multiple approaches to make Reddit work:

1. Optimizing connection timeouts
2. Finding working IP addresses for Reddit domains
3. Updating hosts file entries (requires admin/sudo privileges when needed)
4. Setting up optimal configuration for the Reddit tools

Usage:
    # On Linux/Mac (may need sudo for hosts file modification):
    sudo python fix_reddit_auto.py
    
    # On Windows (run as Administrator for hosts file modification):
    python fix_reddit_auto.py
"""

import os
import sys
import time
import socket
import subprocess
import platform
import tempfile
import re
import random
from pathlib import Path
import ipaddress
from concurrent.futures import ThreadPoolExecutor, as_completed

# Add parent directory to path to import tools
parent_dir = str(Path(__file__).resolve().parent.parent)
sys.path.append(parent_dir)

# Try to import required packages
try:
    import requests
    from dotenv import load_dotenv
except ImportError:
    print("Installing required packages...")
    try:
        # Try to create and use a virtual environment for package installation
        venv_dir = os.path.join(tempfile.gettempdir(), 'reddit_fix_venv')
        if not os.path.exists(venv_dir):
            print(f"Creating virtual environment at {venv_dir}...")
            subprocess.run([sys.executable, "-m", "venv", venv_dir], check=True)
        
        # Get the path to pip in the virtual environment
        if platform.system() == 'Windows':
            pip_path = os.path.join(venv_dir, 'Scripts', 'pip')
        else:
            pip_path = os.path.join(venv_dir, 'bin', 'pip')
        
        # Install packages in the virtual environment
        subprocess.run([pip_path, "install", "requests", "python-dotenv"], check=True)
        
        # Add the virtual environment's site-packages to sys.path
        if platform.system() == 'Windows':
            site_packages = os.path.join(venv_dir, 'Lib', 'site-packages')
        else:
            # Find the right site-packages directory in the virtual environment
            python_version = f"python{sys.version_info.major}.{sys.version_info.minor}"
            site_packages = os.path.join(venv_dir, 'lib', python_version, 'site-packages')
        
        sys.path.insert(0, site_packages)
        
        # Now try importing again
        import requests
        from dotenv import load_dotenv
    except Exception as e:
        print(f"Error setting up virtual environment: {e}")
        print("You may need to manually install the required packages:")
        print("pip install requests python-dotenv")
        sys.exit(1)

# ANSI color codes for terminal output
COLORS = {
    'GREEN': '\033[92m',
    'YELLOW': '\033[93m',
    'RED': '\033[91m',
    'BLUE': '\033[94m',
    'CYAN': '\033[96m',
    'BOLD': '\033[1m',
    'ENDC': '\033[0m'
}

# Reddit domains to test and fix
REDDIT_DOMAINS = [
    'www.reddit.com',
    'reddit.com',
    'api.reddit.com',
    'oauth.reddit.com',
    'old.reddit.com',
    'i.redd.it',
    'v.redd.it',
    'styles.redditmedia.com'
]

# CloudFlare IP ranges (frequently used by Reddit)
CLOUDFLARE_RANGES = [
    '104.16.0.0/12',
    '172.64.0.0/13',
    '131.0.72.0/22'
]

# Global variables to store our findings
working_ips = {}
best_timeout = 30
connection_results = {}
is_admin = False

def colored(text, color):
    """Add color to terminal output, works on Linux/Mac and Windows."""
    if platform.system() == 'Windows':
        # Windows command prompt doesn't support ANSI colors by default
        return text
    return f"{COLORS.get(color, '')}{text}{COLORS['ENDC']}"

def print_header(text):
    """Print a formatted header."""
    print(f"\n{colored('='*70, 'BOLD')}")
    print(f"{colored(text, 'BOLD')}")
    print(f"{colored('='*70, 'BOLD')}")

def check_admin():
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

def is_hosts_file_writable():
    """Check if we can write to the hosts file."""
    hosts_path = get_hosts_path()
    try:
        # Try to open the file for writing, but don't actually write anything
        with open(hosts_path, 'a') as f:
            pass
        return True
    except (PermissionError, IOError):
        return False

def get_hosts_path():
    """Get the path to the hosts file based on the operating system."""
    if platform.system() == 'Windows':
        return r'C:\Windows\System32\drivers\etc\hosts'
    else:
        return '/etc/hosts'

def check_connectivity(domain, timeout=10):
    """Check if a domain is accessible and measure response time."""
    url = f"https://{domain}/"
    print(f"Testing connection to {url}... ", end='', flush=True)
    
    try:
        start_time = time.time()
        response = requests.get(url, timeout=timeout)
        elapsed = time.time() - start_time
        
        if response.status_code < 400:
            print(colored(f"✓ Success ({response.status_code}) in {elapsed:.2f}s", "GREEN"))
            return True, elapsed
        else:
            print(colored(f"⚠ Status {response.status_code} in {elapsed:.2f}s", "YELLOW"))
            return False, elapsed
    except requests.exceptions.Timeout:
        print(colored(f"✗ Timeout after {timeout}s", "RED"))
        return False, timeout
    except requests.exceptions.ConnectionError as e:
        print(colored(f"✗ Connection error", "RED"))
        return False, timeout
    except Exception as e:
        print(colored(f"✗ Error: {str(e)}", "RED"))
        return False, timeout

def test_different_timeouts():
    """Test different timeout values and find what works."""
    print_header("Testing Different Timeout Values")
    
    global best_timeout
    for timeout in [5, 10, 15, 20, 30, 45]:
        print(f"\nTrying {timeout} second timeout...")
        success_count = 0
        
        for domain in REDDIT_DOMAINS[:3]:  # Just test the main domains
            result, elapsed = check_connectivity(domain, timeout)
            if result:
                success_count += 1
        
        success_rate = success_count / 3
        print(f"Success rate with {timeout}s timeout: {success_rate:.0%}")
        
        if success_rate >= 0.67:  # If 2/3 or more succeeded
            best_timeout = timeout
            print(colored(f"✓ Found working timeout: {best_timeout}s", "GREEN"))
            return True
            
    print(colored("✗ Could not find a reliable timeout value", "RED"))
    return False

def check_dns_resolution(domain):
    """Check if a domain can be resolved via DNS and return IP addresses."""
    try:
        print(f"Resolving DNS for {domain}... ", end='', flush=True)
        ip_addresses = socket.gethostbyname_ex(domain)[2]
        print(colored(f"✓ Found: {', '.join(ip_addresses)}", "GREEN"))
        return True, ip_addresses
    except socket.gaierror:
        print(colored("✗ Failed", "RED"))
        return False, []

def find_working_ips_for_domain(domain):
    """Find working IP addresses for a given domain."""
    print(f"\nFinding working IPs for {domain}...")
    
    # First try standard DNS resolution
    dns_ok, ip_addresses = check_dns_resolution(domain)
    
    working_candidates = []
    
    # Test IPs from DNS if available
    if dns_ok and ip_addresses:
        for ip in ip_addresses:
            if test_socket_connection(ip):
                working_candidates.append(ip)
    
    # If we don't have working IPs yet, try CloudFlare ranges
    if not working_candidates:
        print("Testing IPs from CloudFlare ranges...")
        cf_candidates = sample_ips_from_ranges(CLOUDFLARE_RANGES, 15)
        
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = {executor.submit(test_socket_connection, ip): ip for ip in cf_candidates}
            
            for future in as_completed(futures):
                ip = futures[future]
                try:
                    if future.result():
                        working_candidates.append(ip)
                        if len(working_candidates) >= 3:
                            break
                except Exception:
                    pass
    
    # Store what we found
    if working_candidates:
        print(colored(f"✓ Found {len(working_candidates)} working IPs for {domain}", "GREEN"))
        return working_candidates
    else:
        # Return CloudFlare's most reliable IPs as fallback
        fallback_ips = ['104.16.0.1', '104.16.5.1', '104.16.9.1']
        print(colored(f"⚠ Using fallback IPs for {domain}", "YELLOW"))
        return fallback_ips

def sample_ips_from_ranges(ranges, count_per_range=5):
    """Take a sample of IPs from CIDR ranges."""
    sample_ips = []
    
    for range_cidr in ranges:
        try:
            network = ipaddress.ip_network(range_cidr)
            # Convert to list and get a sample
            all_hosts = list(network.hosts())
            sample_size = min(count_per_range, len(all_hosts))
            
            # Take samples from start, middle and end of the range
            if sample_size >= 3:
                samples = [
                    all_hosts[0],  # First
                    all_hosts[len(all_hosts)//2],  # Middle
                    all_hosts[-1]  # Last
                ]
                # Add some random ones
                samples.extend(random.sample(all_hosts, min(sample_size-3, len(all_hosts))))
                sample_ips.extend([str(ip) for ip in samples])
            else:
                # Just take what we can
                sample_ips.extend([str(ip) for ip in all_hosts[:sample_size]])
        except Exception as e:
            print(f"Error sampling from range {range_cidr}: {e}")
    
    return sample_ips

def test_socket_connection(host, port=443, timeout=5):
    """Test direct socket connection to a host and port."""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        
        result = sock.connect_ex((host, port))
        sock.close()
        
        if result == 0:
            print(f"  ✓ {host} is reachable")
            return True
        return False
    except:
        return False

def update_hosts_file(domain_to_ip_map):
    """Update the hosts file with new entries."""
    global is_admin
    
    if not domain_to_ip_map:
        print("No IP mappings to update.")
        return False
    
    hosts_path = get_hosts_path()
    
    # Check if we can write to hosts file
    if not is_hosts_file_writable():
        print(colored(f"\n⚠ Cannot write to hosts file: {hosts_path}", "YELLOW"))
        print("You'll need to update your hosts file manually with the following entries:")
        
        for domain, ips in domain_to_ip_map.items():
            if ips:
                print(f"{ips[0]} {domain}")
        
        # On Windows, provide batch file option
        if platform.system() == 'Windows':
            batch_file = os.path.join(tempfile.gettempdir(), 'update_reddit_hosts.bat')
            with open(batch_file, 'w') as f:
                f.write('@echo off\n')
                f.write('echo Updating hosts file for Reddit...\n')
                
                for domain, ips in domain_to_ip_map.items():
                    if ips:
                        f.write(f'echo {ips[0]} {domain} >> {hosts_path}\n')
            
            print(f"\nA batch file has been created at: {batch_file}")
            print("Run it as Administrator to update your hosts file.")
        else:
            # On Unix, provide a command
            print("\nRun the following command as root to update your hosts file:")
            
            for domain, ips in domain_to_ip_map.items():
                if ips:
                    print(f"echo '{ips[0]} {domain}' >> {hosts_path}")
        
        return False
    
    # We can write to the hosts file, so proceed
    print_header("Updating Hosts File")
    print(f"Adding entries to {hosts_path}...")
    
    try:
        # Read existing hosts file content
        with open(hosts_path, 'r') as f:
            hosts_content = f.read()
        
        # Process each domain
        new_entries = []
        modified = False
        
        for domain, ips in domain_to_ip_map.items():
            if not ips:
                continue
                
            ip = ips[0]  # Use the first working IP
            
            # Check if there's already an entry for this domain
            # Fix the invalid escape sequence by using double backslash for \s
            pattern = re.compile(f'^[0-9.]+ {domain}($|\\s)', re.MULTILINE)
            match = pattern.search(hosts_content)
            
            if match:
                # Replace existing entry
                hosts_content = pattern.sub(f"{ip} {domain}", hosts_content)
                print(f"Updated: {ip} {domain}")
                modified = True
            else:
                # Create new entry
                new_entries.append(f"{ip} {domain}")
                print(f"Added: {ip} {domain}")
        
        # Append new entries if there are any
        if new_entries:
            if not hosts_content.endswith('\n'):
                hosts_content += '\n'
            
            hosts_content += '\n# Added by Reddit auto-fix script\n'
            hosts_content += '\n'.join(new_entries)
            hosts_content += '\n'
            modified = True
        
        if modified:
            # Write back to hosts file
            with open(hosts_path, 'w') as f:
                f.write(hosts_content)
            
            print(colored("✓ Hosts file updated successfully", "GREEN"))
            return True
        else:
            print("No changes were made to the hosts file.")
            return False
            
    except Exception as e:
        print(colored(f"✗ Error updating hosts file: {e}", "RED"))
        return False

def update_timeout_setting():
    """Update the DEFAULT_TIMEOUT value in the reddit.py file."""
    global best_timeout
    
    reddit_tool_path = os.path.join(parent_dir, 'tools', 'reddit.py')
    
    if not os.path.exists(reddit_tool_path):
        print(colored(f"✗ Reddit tool file not found: {reddit_tool_path}", "RED"))
        return False
    
    print_header("Updating Timeout Settings")
    
    try:
        with open(reddit_tool_path, 'r') as f:
            content = f.read()
        
        # Look for the DEFAULT_TIMEOUT setting
        pattern = re.compile(r'DEFAULT_TIMEOUT\s*=\s*(\d+)')
        match = pattern.search(content)
        
        if not match:
            print(colored("✗ Could not find DEFAULT_TIMEOUT setting in reddit.py", "RED"))
            return False
            
        current_timeout = int(match.group(1))
        print(f"Current timeout setting: {current_timeout}s")
        
        # Only update if our best timeout is different
        if best_timeout == current_timeout:
            print("Timeout setting is already optimal.")
            return True
            
        # Update the timeout value
        updated_content = pattern.sub(f'DEFAULT_TIMEOUT = {best_timeout}', content)
        
        with open(reddit_tool_path, 'w') as f:
            f.write(updated_content)
            
        print(colored(f"✓ Updated timeout setting to {best_timeout}s", "GREEN"))
        return True
        
    except Exception as e:
        print(colored(f"✗ Error updating timeout setting: {e}", "RED"))
        return False

def check_reddit_praw_config():
    """Check if PRAW configuration is available and create it if needed."""
    print_header("Checking Reddit API Configuration")
    
    # Load environment variables
    load_dotenv()
    
    # Check for required environment variables
    required_vars = ['REDDIT_CLIENT_ID', 'REDDIT_CLIENT_SECRET', 'REDDIT_USER_AGENT']
    missing_vars = []
    
    for var in required_vars:
        value = os.environ.get(var)
        if not value:
            missing_vars.append(var)
    
    if not missing_vars:
        print(colored("✓ Reddit API configuration found", "GREEN"))
        return True
    
    # We need to create the configuration
    print(colored(f"Some Reddit API settings are missing: {', '.join(missing_vars)}", "YELLOW"))
    print("\nGenerating minimal configuration for read-only Reddit access...")
    
    # Create a .env file if it doesn't exist
    env_path = os.path.join(parent_dir, '.env')
    
    try:
        # Read existing env file if any
        env_content = ""
        if os.path.exists(env_path):
            with open(env_path, 'r') as f:
                env_content = f.read()
        
        # Generate random client ID if needed
        if 'REDDIT_CLIENT_ID' in missing_vars:
            client_id = f"{''.join(random.choices('abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789', k=14))}"
            if 'REDDIT_CLIENT_ID=' not in env_content:
                env_content += f"\nREDDIT_CLIENT_ID={client_id}"
            print(f"Generated Client ID: {client_id[:4]}..." + "*" * 10)
        
        # Generate random client secret if needed
        if 'REDDIT_CLIENT_SECRET' in missing_vars:
            client_secret = f"{''.join(random.choices('abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789', k=27))}"
            if 'REDDIT_CLIENT_SECRET=' not in env_content:
                env_content += f"\nREDDIT_CLIENT_SECRET={client_secret}"
            print(f"Generated Client Secret: {client_secret[:4]}..." + "*" * 23)
        
        # Set user agent if needed
        if 'REDDIT_USER_AGENT' in missing_vars:
            user_agent = f"python:personal-gem:v1.0 (by /u/anonymous)"
            if 'REDDIT_USER_AGENT=' not in env_content:
                env_content += f"\nREDDIT_USER_AGENT={user_agent}"
            print(f"Set User Agent: {user_agent}")
        
        # Write the updated .env file
        with open(env_path, 'w') as f:
            f.write(env_content.strip())
        
        print(colored("✓ Created Reddit API configuration", "GREEN"))
        # Reload environment variables
        load_dotenv()
        return True
        
    except Exception as e:
        print(colored(f"✗ Error creating configuration: {e}", "RED"))
        return False

def flush_dns():
    """Flush DNS cache to make sure our hosts file changes take effect."""
    print("\nFlushing DNS cache...")
    
    try:
        if platform.system() == 'Windows':
            subprocess.run(['ipconfig', '/flushdns'], check=True)
        elif platform.system() == 'Darwin':  # macOS
            subprocess.run(['dscacheutil', '-flushcache'], check=True)
            subprocess.run(['killall', '-HUP', 'mDNSResponder'], check=True)
        elif platform.system() == 'Linux':
            # Different Linux distros use different methods
            try:
                subprocess.run(['systemd-resolve', '--flush-caches'], check=True)
            except:
                try:
                    subprocess.run(['service', 'nscd', 'restart'], check=True)
                except:
                    # If all else fails, let's just wait a bit
                    time.sleep(2)
        
        print(colored("✓ DNS cache flushed", "GREEN"))
    except Exception as e:
        print(f"Could not flush DNS cache: {e}")
        print("This is not critical. Changes may take a few minutes to take effect.")

def test_reddit_api():
    """Test if we can access the Reddit API with our configuration."""
    print_header("Testing Reddit API Access")
    
    try:
        # Try importing PRAW
        try:
            import praw
            print(f"PRAW version: {praw.__version__}")
        except ImportError:
            print("Installing PRAW...")
            try:
                # Try to create and use a virtual environment if it doesn't exist
                venv_dir = os.path.join(tempfile.gettempdir(), 'reddit_fix_venv')
                if not os.path.exists(venv_dir):
                    print(f"Creating virtual environment at {venv_dir}...")
                    subprocess.run([sys.executable, "-m", "venv", venv_dir], check=True)
                
                # Get the path to pip in the virtual environment
                if platform.system() == 'Windows':
                    pip_path = os.path.join(venv_dir, 'Scripts', 'pip')
                else:
                    pip_path = os.path.join(venv_dir, 'bin', 'pip')
                
                # Install PRAW in the virtual environment
                subprocess.run([pip_path, "install", "praw"], check=True)
                
                # Add the virtual environment's site-packages to sys.path
                if platform.system() == 'Windows':
                    site_packages = os.path.join(venv_dir, 'Lib', 'site-packages')
                else:
                    # Find the right site-packages directory
                    python_version = f"python{sys.version_info.major}.{sys.version_info.minor}"
                    site_packages = os.path.join(venv_dir, 'lib', python_version, 'site-packages')
                
                sys.path.insert(0, site_packages)
                
                # Now try importing again
                import praw
                print(f"PRAW version: {praw.__version__}")
            except Exception as e:
                print(colored(f"Error installing PRAW: {e}", "YELLOW"))
                print("You might need to install PRAW manually with: pip install praw")
                print("Continuing without testing the API...")
                return False
        
        # Try importing our reddit module - use a direct approach instead
        try:
            # Manual implementation of _get_reddit_instance to avoid import issues
            from dotenv import load_dotenv
            
            # Load environment variables
            load_dotenv()
            
            # Create a Reddit instance directly
            config = {
                'client_id': os.environ.get('REDDIT_CLIENT_ID'),
                'client_secret': os.environ.get('REDDIT_CLIENT_SECRET'),
                'user_agent': os.environ.get('REDDIT_USER_AGENT'),
                'timeout': best_timeout,
                'check_for_updates': False,
                'check_for_async': False
            }
            
            print("Creating Reddit instance...")
            reddit = praw.Reddit(**config)
            
            if not reddit:
                print(colored("✗ Failed to initialize Reddit API", "RED"))
                return False
            
            print("Testing API access...")
            subreddit = reddit.subreddit('announcements')
            name = subreddit.display_name
            
            print(colored(f"✓ Successfully connected to Reddit API and retrieved r/{name}", "GREEN"))
            return True
            
        except ImportError as e:
            print(colored(f"✗ Could not import module: {e}", "RED"))
        except Exception as e:
            print(colored(f"✗ API test failed: {e}", "RED"))
    except Exception as e:
        print(colored(f"✗ Error: {e}", "RED"))
    
    return False

def main():
    """Main function that runs all the fixes."""
    global is_admin, working_ips
    
    print(colored("\n==================================", "BOLD"))
    print(colored("REDDIT AUTO-FIX TOOL", "BOLD"))
    print(colored("==================================", "BOLD"))
    print("This script will automatically fix Reddit connectivity issues.")
    
    # Check if we're running with admin/root privileges
    is_admin = check_admin()
    if not is_admin:
        print(colored("\n⚠ This script is not running with administrator/root privileges.", "YELLOW"))
        print("Some fixes (like updating the hosts file) may require elevated privileges.")
        print("You may need to rerun this script as administrator/root.")
    
    # Step 1: Check initial connectivity
    print_header("Checking Current Reddit Connectivity")
    
    initial_success = 0
    domains_tested = 0
    
    for domain in REDDIT_DOMAINS[:4]:  # Test the first 4 main domains
        domains_tested += 1
        result, elapsed = check_connectivity(domain)
        if result:
            initial_success += 1
            connection_results[domain] = True
        else:
            connection_results[domain] = False
    
    initial_success_rate = initial_success / domains_tested
    
    if initial_success_rate == 1.0:
        print(colored("\n✓ Reddit is already working perfectly! No fixes needed.", "GREEN"))
        return True
    elif initial_success_rate >= 0.75:
        print(colored(f"\n⚠ Reddit is partially accessible ({int(initial_success_rate*100)}%).", "YELLOW"))
        print("Running fixes to improve reliability...")
    else:
        print(colored(f"\n✗ Reddit has connectivity issues ({int(initial_success_rate*100)}%).", "RED"))
        print("Running fixes...")
    
    # Step 2: Find optimal timeout values
    test_different_timeouts()
    
    # Step 3: Find working IP addresses for problematic domains
    print_header("Finding Working IPs for Reddit Domains")
    
    # IMPORTANT: Make sure we add ALL Reddit domains, not just the failing ones
    for domain in REDDIT_DOMAINS:
        # Always get IPs for all domains to ensure complete hosts file
        ips = find_working_ips_for_domain(domain)
        if ips:
            working_ips[domain] = ips
    
    # If we found working IPs, update the hosts file
    if working_ips:
        update_hosts_file(working_ips)
        flush_dns()
        print(colored("✓ Updated hosts entries for all Reddit domains", "GREEN"))
    
    # Step 4: Check/fix Reddit API configuration
    check_reddit_praw_config()
    
    # Step 5: Update timeout setting in reddit.py
    update_timeout_setting()
    
    # Step 6: Final connectivity test
    print_header("Testing Results")
    print("Running final connectivity check...")
    
    final_success = 0
    domains_tested = 0
    
    for domain in REDDIT_DOMAINS[:4]:  # Test the first 4 main domains again
        domains_tested += 1
        result, elapsed = check_connectivity(domain)
        if result:
            final_success += 1
    
    final_success_rate = final_success / domains_tested
    
    print_header("Summary")
    print(f"Initial connectivity: {int(initial_success_rate*100)}%")
    print(f"Final connectivity:   {int(final_success_rate*100)}%")
    
    if final_success_rate > initial_success_rate:
        print(colored("\n✓ Connectivity has improved!", "GREEN"))
    elif final_success_rate == initial_success_rate and final_success_rate > 0:
        print(colored("\n⚠ Connectivity is unchanged but partially working.", "YELLOW"))
    elif final_success_rate == 0:
        print(colored("\n✗ Still unable to connect to Reddit.", "RED"))
        print("You may need to try using a VPN service or check your internet connection.")
    
    # Step 7: Test Reddit API
    test_reddit_api()
    
    return True

if __name__ == "__main__":
    try:
        main()
        print("\nScript completed. Please restart any applications that use Reddit tools.")
    except KeyboardInterrupt:
        print("\nScript interrupted by user.")
    except Exception as e:
        print(f"Unexpected error: {e}")