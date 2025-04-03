#!/usr/bin/env python3
"""
Thursday - Your AI Assistant Launcher
Run this script to start Thursday in either terminal or web mode.

Usage:
    python run.py          # Interactive mode (asks which interface to launch)
    python run.py web      # Launch web interface
    python run.py terminal # Launch terminal interface
    python run.py --help   # Show help message
"""

import os
import sys
import subprocess
import importlib.util
import platform

# ANSI color codes for prettier output
class Colors:
    BLUE = '\033[94m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'
    END = '\033[0m'

def check_dependencies():
    """Check if required dependencies are installed"""
    required_packages = [
        'flask', 'requests', 'rich', 'python-dotenv', 'colorama', 
        'prompt-toolkit', 'pydantic'
    ]
    
    missing = []
    for package in required_packages:
        spec = importlib.util.find_spec(package)
        if spec is None:
            missing.append(package)
    
    if missing:
        print(f"{Colors.RED}Missing dependencies: {', '.join(missing)}{Colors.END}")
        install = input(f"{Colors.YELLOW}Do you want to install them now? (y/n): {Colors.END}").strip().lower()
        
        if install == 'y':
            try:
                subprocess.check_call([sys.executable, "-m", "pip", "install"] + missing)
                print(f"{Colors.GREEN}Dependencies installed successfully!{Colors.END}")
            except subprocess.CalledProcessError:
                print(f"{Colors.RED}Failed to install dependencies. Please install them manually:{Colors.END}")
                print(f"pip install {' '.join(missing)}")
                return False
        else:
            print(f"{Colors.YELLOW}Please install missing dependencies and try again.{Colors.END}")
            return False
    
    return True

def run_terminal_interface():
    """Run the terminal interface"""
    print(f"{Colors.BLUE}Starting Thursday terminal interface...{Colors.END}")
    subprocess.run([sys.executable, "assistant.py"])

def run_web_interface():
    """Run the web interface"""
    print(f"{Colors.BLUE}Starting Thursday web interface...{Colors.END}")
    print(f"{Colors.GREEN}Open your browser and navigate to http://localhost:5000{Colors.END}")
    subprocess.run([sys.executable, "app.py"])

def print_header():
    """Print a nice header"""
    os_name = platform.system()
    header = r"""
  _______ _                        _             
 |__   __| |                      | |            
    | |  | |__  _   _ _ __ ___  __| | __ _ _   _ 
    | |  | '_ \| | | | '__/ __|/ _` |/ _` | | | |
    | |  | | | | |_| | |  \__ \ (_| | (_| | |_| |
    |_|  |_| |_|\__,_|_|  |___/\__,_|\__,_|\__, |
                                            __/ |
                                           |___/ 
    """
    print(f"{Colors.BLUE}{header}{Colors.END}")
    print(f"{Colors.BOLD}Thursday AI Assistant - Running on {os_name}{Colors.END}")
    print(f"{Colors.GREEN}{'=' * 60}{Colors.END}\n")

def interactive_mode():
    """Interactive mode to choose which interface to launch"""
    print_header()
    print(f"{Colors.BOLD}Choose interface to launch:{Colors.END}")
    print(f"  {Colors.GREEN}1.{Colors.END} Web Interface (with streaming tools and UI)")
    print(f"  {Colors.GREEN}2.{Colors.END} Terminal Interface (command line)\n")
    
    choice = input(f"{Colors.YELLOW}Enter your choice (1/2): {Colors.END}").strip()
    
    if choice == '1':
        run_web_interface()
    elif choice == '2':
        run_terminal_interface()
    else:
        print(f"{Colors.RED}Invalid choice. Please enter 1 or 2.{Colors.END}")
        return interactive_mode()

def main():
    """Main entry point"""
    if not check_dependencies():
        sys.exit(1)
    
    if len(sys.argv) > 1:
        arg = sys.argv[1].lower()
        
        if arg == 'web':
            run_web_interface()
        elif arg == 'terminal':
            run_terminal_interface()
        elif arg in ['--help', '-h', 'help']:
            print(__doc__)
        else:
            print(f"{Colors.RED}Unknown argument: {arg}{Colors.END}")
            print(f"Use '{Colors.YELLOW}python run.py --help{Colors.END}' for usage information.")
    else:
        interactive_mode()

if __name__ == "__main__":
    main()
