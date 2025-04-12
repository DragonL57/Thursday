"""
Functions for system-related operations with robust shell command execution capabilities.
"""

import datetime
import subprocess
import os
import shlex
import signal
import threading
import time
import uuid
import re
from typing import Dict, List, Optional, Tuple, Union, Any

from .formatting import tool_message_print, tool_report_print

# Store active background processes for management
_BACKGROUND_PROCESSES: Dict[str, Dict[str, Any]] = {}
# Store command history
_COMMAND_HISTORY: List[Dict[str, Any]] = []
# Maximum history size
_MAX_HISTORY_SIZE = 50

# Potentially dangerous commands that require extra confirmation
_DANGEROUS_COMMANDS = [
    r'\brm\s+-rf\b', r'\bdd\b.+\bof=', r'\bmkfs\b', r'\bformat\b',
    r'\bfdisk\b', r'\bmkpart\b', r'\bcrontab -r\b', r':(){', 
    r'\bchmod\s+-R\b.*777', r'\bsudo\s+rm\b', r'>\s*/dev/sd',
]

def _is_potentially_dangerous(cmd: str) -> Tuple[bool, str]:
    """
    Check if a command is potentially dangerous.
    
    Args:
        cmd: The command to check
        
    Returns:
        Tuple of (is_dangerous, reason)
    """
    cmd_lower = cmd.lower()
    
    # Check for dangerous patterns
    for pattern in _DANGEROUS_COMMANDS:
        if re.search(pattern, cmd):
            return True, f"Command matches dangerous pattern: {pattern}"
    
    # Check for recursive removals
    if re.search(r'\brm\b.*-r', cmd_lower) and not cmd_lower.endswith('-r'):
        return True, "Command appears to perform recursive deletion"
    
    # Check for commands that might affect many files
    if re.search(r'\bchmod\b.*777', cmd_lower) or re.search(r'\bchown\b.*-R', cmd_lower):
        return True, "Command changes permissions/ownership recursively"
        
    # Check for pipe to shell execution
    if '| sh' in cmd_lower or '| bash' in cmd_lower or '|sh' in cmd_lower:
        return True, "Command pipes output to a shell which can be dangerous"
        
    # Check for redirect to important files
    if re.search(r'>\s*/etc/[a-zA-Z0-9_]+', cmd_lower):
        return True, "Command overwrites system configuration files"
    
    return False, ""

def run_shell_command(
    command: str,
    blocking: bool,
    print_output: bool = False,
    timeout: int = 60,
    working_dir: str = None,
    env_vars: Dict[str, str] = None,
    sudo_password: str = None
) -> Union[str, Dict[str, Any]]:
    """
    Run a shell command with enhanced security and management features.

    Args:
        command: The shell command to execute.
        blocking: If True, waits for command to complete. If False, runs in background.
        print_output: If True, prints the output of the command for the user to see.
        timeout: Maximum execution time in seconds (for blocking commands only).
        working_dir: Directory where the command will be executed.
        env_vars: Additional environment variables for the command.
        sudo_password: Password for sudo commands (use with extreme caution).

    Returns: 
        If blocking=True: The output of the command as a string
        If blocking=False: Dictionary with process id and command information
    """
    # Generate a unique ID for this command execution
    process_id = str(uuid.uuid4())
    
    # Record timestamp
    timestamp = datetime.datetime.now().isoformat()
    
    # Initial tool announcement
    tool_message_print("run_shell_command", [
        ("command", command),
        ("blocking", str(blocking)),
        ("print_output", str(print_output)),
        ("timeout", str(timeout) if blocking else "N/A"),
        ("working_dir", working_dir or "current directory")
    ])
    
    # Safety check for dangerous commands
    is_dangerous, reason = _is_potentially_dangerous(command)
    if is_dangerous:
        safe_message = f"⚠️ WARNING: This command may be dangerous: {reason}"
        tool_report_print("Security Warning:", safe_message, is_error=True)
        # Still let it run but make sure warning is visible
    
    # Show execution output format
    tool_message_print("run_shell_command", [
        ("command", command),
        ("process_id", process_id),
        ("blocking", str(blocking)),
        ("print_output", str(print_output)),
    ], is_output=True)
    
    # Prepare environment
    process_env = os.environ.copy()
    if env_vars:
        process_env.update(env_vars)
    
    # Track in history
    history_entry = {
        "id": process_id,
        "command": command,
        "timestamp": timestamp,
        "blocking": blocking,
        "working_dir": working_dir
    }
    _add_to_history(history_entry)
    
    def _run_command():
        output = ""
        start_time = time.time()
        try:
            # Handle sudo password if provided
            stdin = None
            if sudo_password and 'sudo' in command:
                command_with_password = f"echo {shlex.quote(sudo_password)} | sudo -S {command.replace('sudo ', '', 1)}"
                process = subprocess.Popen(
                    command_with_password,
                    shell=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    cwd=working_dir,
                    env=process_env
                )
            else:
                process = subprocess.Popen(
                    command,
                    shell=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    cwd=working_dir,
                    env=process_env
                )
            
            # Store process info for background commands
            if not blocking:
                _BACKGROUND_PROCESSES[process_id] = {
                    'process': process,
                    'command': command,
                    'start_time': start_time,
                    'status': 'running'
                }
            
            # Handle timeout for blocking commands
            if blocking:
                try:
                    stdout, stderr = process.communicate(timeout=timeout)
                    exit_code = process.returncode
                except subprocess.TimeoutExpired:
                    if blocking:  # Only kill if we're supposed to be blocking
                        process.kill()
                        stdout, stderr = process.communicate()
                        exit_code = -1
                        tool_report_print("Error:", f"Command timed out after {timeout} seconds", is_error=True)
                        return f"Error: Command timed out after {timeout} seconds"
            else:
                # For background processes, we don't wait
                stdout, stderr = "", ""
                exit_code = None
                
                # Start output collection in a separate thread
                def collect_output():
                    nonlocal stdout, stderr, exit_code
                    stdout, stderr = process.communicate()
                    exit_code = process.returncode
                    _BACKGROUND_PROCESSES[process_id]['status'] = 'completed'
                    _BACKGROUND_PROCESSES[process_id]['exit_code'] = exit_code
                    _BACKGROUND_PROCESSES[process_id]['stdout'] = stdout
                    _BACKGROUND_PROCESSES[process_id]['stderr'] = stderr
                    _BACKGROUND_PROCESSES[process_id]['end_time'] = time.time()
                    
                output_thread = threading.Thread(target=collect_output)
                output_thread.daemon = True
                output_thread.start()
                
                # Return early for background processes
                return {
                    "process_id": process_id,
                    "message": f"Command running in background. Use get_command_output('{process_id}') to check results later."
                }
            
            # Process output for blocking commands
            if stderr and exit_code != 0:
                tool_report_print("Error:", stderr, is_error=True)
                output = f"Command failed with exit code {exit_code}:\n{stderr}\n{stdout}"
            else:
                if stderr and not stdout:
                    # Some commands write to stderr even on success
                    output = stderr
                else:
                    output = stdout
                
                execution_time = time.time() - start_time
                tool_report_print("Status:", f"Command completed in {execution_time:.2f}s with exit code {exit_code}")
                
            if print_output:
                print(output)
                
            return output.strip()
            
        except Exception as e:
            error_msg = f"Error running shell command: {str(e)}"
            tool_report_print("Error:", error_msg, is_error=True)
            return error_msg

    if blocking:
        result = _run_command()
        # Update history with completion status
        _update_history_entry(process_id, {'output_summary': result[:100] + '...' if len(result) > 100 else result})
        return result
    else:
        # For background commands, start in thread and return process ID
        thread = threading.Thread(target=_run_command)
        thread.daemon = True
        thread.start()
        return {
            "process_id": process_id,
            "message": f"Command started in background. Use get_command_output('{process_id}') to check results."
        }

def get_command_output(process_id: str) -> Dict[str, Any]:
    """
    Get the output of a background command.
    
    Args:
        process_id: The ID of the background process
        
    Returns:
        Dictionary with the command information and output
    """
    tool_message_print("get_command_output", [("process_id", process_id)])
    tool_message_print("get_command_output", [("process_id", process_id)], is_output=True)
    
    if process_id not in _BACKGROUND_PROCESSES:
        return {"error": f"No background process found with ID {process_id}"}
    
    process_info = _BACKGROUND_PROCESSES[process_id].copy()
    
    # Remove the actual process object as it's not serializable
    if 'process' in process_info:
        del process_info['process']
    
    # Calculate runtime
    if process_info.get('start_time'):
        if process_info.get('end_time'):
            runtime = process_info['end_time'] - process_info['start_time']
        else:
            runtime = time.time() - process_info['start_time']
        process_info['runtime_seconds'] = runtime
    
    # Format output for better readability
    if 'stdout' in process_info:
        if len(process_info['stdout']) > 2000:
            process_info['stdout'] = process_info['stdout'][:2000] + "...(output truncated)"
            
    return process_info

def kill_background_process(process_id: str) -> Dict[str, Any]:
    """
    Kill a background process.
    
    Args:
        process_id: The ID of the background process to kill
        
    Returns:
        Dictionary with the result of the kill operation
    """
    tool_message_print("kill_background_process", [("process_id", process_id)])
    tool_message_print("kill_background_process", [("process_id", process_id)], is_output=True)
    
    if process_id not in _BACKGROUND_PROCESSES:
        return {"error": f"No background process found with ID {process_id}"}
    
    process_info = _BACKGROUND_PROCESSES[process_id]
    process = process_info.get('process')
    
    if not process:
        return {"error": "Process object not available"}
    
    try:
        # Send SIGTERM first for graceful shutdown
        process.terminate()
        
        # Wait up to 3 seconds for graceful termination
        try:
            process.wait(timeout=3)
            result = {"status": "terminated", "process_id": process_id}
        except subprocess.TimeoutExpired:
            # If process doesn't terminate, force kill
            process.kill()
            process.wait()
            result = {"status": "killed", "process_id": process_id} 
            
        # Update process info
        process_info['status'] = 'terminated'
        process_info['end_time'] = time.time()
        
        return result
    except Exception as e:
        return {"error": f"Failed to kill process: {str(e)}"}

def list_background_processes() -> List[Dict[str, Any]]:
    """
    List all background processes.
    
    Returns:
        List of dictionaries with information about each process
    """
    tool_message_print("list_background_processes", [])
    tool_message_print("list_background_processes", [], is_output=True)
    
    result = []
    for pid, info in _BACKGROUND_PROCESSES.items():
        # Create a copy without the process object
        process_info = info.copy()
        if 'process' in process_info:
            del process_info['process']
            
        # Add the process ID
        process_info['id'] = pid
        
        # Calculate runtime
        if process_info.get('start_time'):
            if process_info.get('end_time'):
                runtime = process_info['end_time'] - process_info['start_time']
            else:
                runtime = time.time() - process_info['start_time']
            process_info['runtime_seconds'] = round(runtime, 2)
            
        # Don't include full stdout/stderr in list
        if 'stdout' in process_info:
            stdout_length = len(process_info['stdout'])
            process_info['stdout'] = f"{process_info['stdout'][:50]}... ({stdout_length} chars)"
        if 'stderr' in process_info:
            stderr_length = len(process_info['stderr'])
            process_info['stderr'] = f"{process_info['stderr'][:50]}... ({stderr_length} chars)"
            
        result.append(process_info)
        
    return result

def _add_to_history(entry: Dict[str, Any]):
    """Add a command to the history."""
    _COMMAND_HISTORY.append(entry)
    # Trim history if it gets too long
    if len(_COMMAND_HISTORY) > _MAX_HISTORY_SIZE:
        _COMMAND_HISTORY.pop(0)

def _update_history_entry(command_id: str, updates: Dict[str, Any]):
    """Update a command in the history."""
    for entry in _COMMAND_HISTORY:
        if entry.get('id') == command_id:
            entry.update(updates)
            break

def get_command_history(limit: int = 10) -> List[Dict[str, Any]]:
    """
    Get the command execution history.
    
    Args:
        limit: Maximum number of history entries to return
        
    Returns:
        List of dictionaries with command history
    """
    tool_message_print("get_command_history", [("limit", str(limit))])
    tool_message_print("get_command_history", [("limit", str(limit))], is_output=True)
    
    # Return the most recent commands first
    return list(reversed(_COMMAND_HISTORY[-limit:]))

def get_current_datetime() -> str:
    """
    Get the current time and date.

    Returns: A string representing the current time and date.
    """
    # Initial tool announcement
    tool_message_print("get_current_datetime")
    
    # Show execution output format
    tool_message_print("get_current_datetime", is_output=True)
    now = datetime.datetime.now()
    time_str = now.strftime("%Y-%m-%d %H:%M:%S")
    return time_str

def get_system_info() -> Dict[str, Any]:
    """
    Get detailed system information.
    
    Returns:
        Dictionary with system information
    """
    tool_message_print("get_system_info", [])
    tool_message_print("get_system_info", [], is_output=True)
    
    system_info = {}
    
    # Basic OS info
    try:
        system_info['os'] = os.name
        system_info['hostname'] = os.uname().nodename
        system_info['kernel'] = os.uname().release
        system_info['architecture'] = os.uname().machine
    except Exception as e:
        system_info['os_error'] = str(e)
    
    # CPU info
    try:
        with open('/proc/cpuinfo', 'r') as f:
            cpu_info = f.readlines()
            
        cpu_model = next((line.split(':')[1].strip() for line in cpu_info if 'model name' in line), 'Unknown')
        cpu_cores = len([line for line in cpu_info if 'processor' in line])
        system_info['cpu_model'] = cpu_model
        system_info['cpu_cores'] = cpu_cores
    except Exception as e:
        system_info['cpu_error'] = str(e)
    
    # Memory info
    try:
        with open('/proc/meminfo', 'r') as f:
            mem_info = f.readlines()
            
        total_mem = next((line.split(':')[1].strip() for line in mem_info if 'MemTotal' in line), 'Unknown')
        free_mem = next((line.split(':')[1].strip() for line in mem_info if 'MemFree' in line), 'Unknown')
        system_info['total_memory'] = total_mem
        system_info['free_memory'] = free_mem
    except Exception as e:
        system_info['memory_error'] = str(e)
    
    # Disk info
    try:
        df_output = subprocess.check_output(['df', '-h']).decode('utf-8')
        system_info['disk_info'] = df_output
    except Exception as e:
        system_info['disk_error'] = str(e)
    
    # Network info
    try:
        ip_output = subprocess.check_output(['hostname', '-I']).decode('utf-8').strip()
        system_info['ip_addresses'] = ip_output
    except Exception as e:
        system_info['network_error'] = str(e)
    
    return system_info
