"""
Functions for system-related operations.
"""

import datetime
import subprocess

from .formatting import tool_message_print, tool_report_print

def run_shell_command(command: str, blocking: bool, print_output: bool = False) -> str | None:
    """
    Run a shell command. Use with caution as this can be dangerous.
    Can be used for command line commands, running programs, opening files using other programs, etc.

    Args:
      command: The shell command to execute.
      blocking: If True, waits for command to complete. If False, runs in background (Default True).
      print_output: If True, prints the output of the command for the user to see(Default False).

    Returns: 
      If blocking=True: The output of the command as a string, or an error message.
      If blocking=False: None (command runs in background)
    """
    tool_message_print("run_shell_command", [("command", command), ("blocking", str(blocking)), ("print_output", str(print_output))])
    
    def _run_command():
        try:
            process = subprocess.Popen(
                command,
                shell=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            stdout, stderr = process.communicate()
            if stderr:
                tool_report_print("Error running command:", stderr, is_error=True)
                return f"Error running command: {stderr}"
            tool_report_print("Status:", "Command executed successfully")
            if print_output:
                print(stdout)
            return stdout.strip() 
        
        except Exception as e:
            tool_report_print("Error running shell command:", str(e), is_error=True)
            return f"Error running shell command: {e}"

    if blocking:
        return _run_command()
    else:
        import threading
        thread = threading.Thread(target=_run_command)
        thread.daemon = True  # Thread will exit when main program exits
        thread.start()
        return None

def get_current_datetime() -> str:
    """
    Get the current time and date.

    Returns: A string representing the current time and date.
    """
    tool_message_print("get_current_datetime")
    now = datetime.datetime.now()
    time_str = now.strftime("%Y-%m-%d %H:%M:%S")
    return time_str
