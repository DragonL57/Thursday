"""
Formatting functions for tool output.
"""

import colorama
from colorama import Fore, Style

# Initialize colorama
colorama.init(autoreset=True)

def tool_message_print(msg: str, args: list[tuple[str, str]] = None):
    """
    Prints a tool message with the given message and arguments.

    Args:
        msg: The message to print.
        args: A list of tuples containing the argument name and value. Optional.
    """
    full_msasage = f"{Fore.CYAN}[TOOL]{Style.RESET_ALL} {Fore.WHITE}{msg}"
    if args:
        for arg in args:
            full_msasage += f" [{Fore.YELLOW}{arg[0]}{Fore.WHITE}={arg[1]}]"
    print(full_msasage)

def tool_report_print(msg: str, value: str, is_error: bool = False):
    """
    Print when a tool needs to put out a message as a report

    Args:
        msg: The message to print.
        value: The value to print.
        is_error: Whether this is an error message. If True, value will be printed in red.
    """
    value_color = Fore.RED if is_error else Fore.YELLOW
    full_msasage = f"{Fore.CYAN}  ├─{Style.RESET_ALL} {msg} {value_color}{value}"
    print(full_msasage)
