"""
Formatting functions for tool output.
"""

import colorama
from colorama import Fore, Style

# Initialize colorama
colorama.init(autoreset=True)

def tool_message_print(msg: str, args: list[tuple[str, str]] = None, is_output: bool = False):
    """
    Print a message for a tool with optional arguments or output.
    
    Args:
        msg: The message to print.
        args: Optional list of (name, value) tuples.
        is_output: Whether this is an output message.
    """
    if is_output:
        prefix = f"{Fore.CYAN}  │ {Fore.GREEN}Output:{Style.RESET_ALL}"
    else:
        prefix = f"{Fore.CYAN}  ├ {Fore.YELLOW}Tool:{Style.RESET_ALL}"
    
    print(f"{prefix} {msg}")
    
    if args:
        for name, value in args:
            value_to_print = value if len(str(value)) < 100 else f"{str(value)[:100]}..."
            print(f"{Fore.CYAN}  │  {Fore.BLUE}{name}:{Style.RESET_ALL} {value_to_print}")

def tool_report_print(msg: str, value: str, is_error: bool = False):
    """
    Print when a tool needs to put out a message as a report

    Args:
        msg: The message to print.
        value: The value to print.
        is_error: Whether this is an error message. If True, value will be printed in red.
    """
    # Clear tool execution markers for real-time UI updates
    if msg.startswith("Running tool:"):
        # Signal that a tool execution has started
        print(f"{Fore.CYAN}🔧 Running tool: {Fore.YELLOW}{value}{Style.RESET_ALL}")
    elif msg == "Result:":
        # Signal that a tool execution has finished
        print(f"{Fore.CYAN}✅ Result: {Fore.GREEN if not is_error else Fore.RED}{value}{Style.RESET_ALL}")
    else:
        value_color = Fore.RED if is_error else Fore.YELLOW
        full_message = f"{Fore.CYAN}  ├─{Style.RESET_ALL} {msg} {value_color}{value}"
        print(full_message)
