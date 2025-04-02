import glob
import os, re
import datetime
import platform
import subprocess
import webbrowser
import shutil

import requests
from bs4 import BeautifulSoup
import psutil
import thefuzz.process
import json

from duckduckgo_search import DDGS
from dotenv import load_dotenv
import colorama
from colorama import Fore, Style
from pydantic import BaseModel, Field
import thefuzz

from rich.console import Console

import config as conf
from gem import seconds_to_hms, bytes_to_mb, format_size
from gem.inspection import inspect_script, get_func_source_code
from typing import Dict, List, Optional, Tuple

load_dotenv()

DEFAULT_USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36"

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

def duckduckgo_search_tool(query: str) -> list:
    """
    Searches DuckDuckGo for the given query and returns a list of results.

    Args:
        query: The search query.

    Returns:
        list: A list of search results.
    """
    tool_message_print("duckduckgo_search_tool", [("query", query)])
    try:
        ddgs = DDGS(timeout=conf.DUCKDUCKGO_TIMEOUT)
        results = ddgs.text(query, max_results=conf.MAX_DUCKDUCKGO_SEARCH_RESULTS)
        return results
    except Exception as e:
        tool_report_print("Error during DuckDuckGo search:", str(e), is_error=True)
        return f"Error during DuckDuckGo search: {e}"

def get_current_directory() -> str:
    """
    Get the current working directory.

    Returns:
        str: The absolute path of the current working directory as a string.
    """
    tool_message_print("get_current_directory", [])
    try:
        return os.getcwd()
    except Exception as e:
        tool_report_print("Error getting current directory:", str(e), is_error=True)
        return f"Error getting current directory: {e}"

def list_dir(path: str, recursive: bool, files_only: bool, dirs_only: bool) -> list:
    """
    Returns a list of contents of a directory. It can handle listing files, directories, or both,
    and can do so recursively or not.

    Args:
        path: The path to the directory.
        recursive: Whether to list contents recursively. If True, it will traverse subdirectories.
        files_only: Whether to list only files. If True, directories are ignored.
        dirs_only: Whether to list only directories. If True, files are ignored.

    Returns:
        list: A list of dictionaries containing information about each item in the directory.
            Each dictionary has the keys:
            - 'name': The name of the file or directory.
            - 'path': The full path to the file or directory.
            - 'is_dir': A boolean indicating if the item is a directory.
            - 'size': The size of the file in a human-readable format (GB or MB), or 'N/A' for directories.
            
            Note that it can have different behavior based on given arguments, for example if you only need files, set `files_only=True` and ignore `dirs_only` and `recursive` arguments, they won't have any effect.
    """
    tool_message_print("list_dir", [("path", path), ("recursive", str(recursive)), 
                                   ("files_only", str(files_only)), ("dirs_only", str(dirs_only))])
    items = []

    def add_item(item_path):
        item_info = {
            'name': os.path.basename(item_path),
            'path': item_path,
            'is_dir': os.path.isdir(item_path),
            'size': format_size(os.path.getsize(item_path)) if os.path.isfile(item_path) else 'N/A'
        }
        items.append(item_info)

    if recursive:
        for dirpath, dirnames, filenames in os.walk(path):
            if not files_only:
                for dirname in dirnames:
                    add_item(os.path.join(dirpath, dirname))
            if not dirs_only:
                for filename in filenames:
                    add_item(os.path.join(dirpath, filename))
    else:
        with os.scandir(path) as it:
            for entry in it:
                if files_only and entry.is_file():
                    add_item(entry.path)
                elif dirs_only and entry.is_dir():
                    add_item(entry.path)
                elif not files_only and not dirs_only:
                    add_item(entry.path)

    return items

    
def get_drives() -> list[dict]:
    """
    Get a list of drives on the system.

    Returns:
        list[dict]: A list of dictionaries containing information about each drive.
                     Each dictionary has the following keys:
                     - 'OsType': The OS type (e.g., "Windows", "Linux", "MacOS").
                     - 'Drive': The drive letter (e.g., "C:") or mount point (e.g., "/").
                     - 'Type': The drive type (e.g., "Fixed", "Removable", "Network").
                     - 'FileSystem': The file system type (e.g., "NTFS", "ext4", "apfs"), or 'N/A'.
                     - 'FreeSpace': The amount of free space in human-readable format (GB or MB), or 'N/A'.
                     - 'TotalSize': The total size of the drive in human-readable format (GB or MB), or 'N/A'.
    """
    tool_message_print("get_drives")
    drives = []
    os_type = platform.system()

    if os_type == "Windows":
        from wmi import WMI
        c = WMI()
        for drive in c.Win32_LogicalDisk():
            drive_type_map = {
                0: "Unknown",
                1: "No Root Directory",
                2: "Removable",
                3: "Fixed",
                4: "Network",
                5: "Compact Disc",
                6: "RAM Disk"
            }
            drives.append({
                'OsType': "Windows",
                'Drive': drive.DeviceID,
                'Type': drive_type_map.get(drive.DriveType, "Unknown"),
                'FileSystem': drive.FileSystem if drive.FileSystem else 'N/A',
                'FreeSpace': format_size(drive.FreeSpace) if drive.FreeSpace else 'N/A',
                'TotalSize': format_size(drive.Size) if drive.Size else 'N/A'
            })
    elif os_type == "Linux" or os_type == "Darwin": 
        import shutil
        for partition in psutil.disk_partitions():
            try:
                disk_usage = shutil.disk_usage(partition.mountpoint)
                drives.append({
                    'OsType': os_type,
                    'Drive': partition.mountpoint,
                    'Type': partition.fstype,  # Filesystem type might serve as a decent "Type"
                    'FileSystem': partition.fstype if partition.fstype else 'N/A',
                    'FreeSpace': format_size(disk_usage.free),
                    'TotalSize': format_size(disk_usage.total)
                })
            except OSError:
                print(f"{Fore.YELLOW}Failed to get drive information for {partition.mountpoint}.  Skipping.{Style.RESET_ALL}")
                return []
    else:
        return []

    return drives


def get_directory_size(path: str) -> dict:
    """Get the size of the specified directory.

    Args:
      path: The path to the directory.

    Returns:
        dict: A dictionary containing the total size and the number of files in the directory.
        The dictionary has the following keys:
        - 'TotalSize': The total size of the directory in human-readable format (GB or MB).
        - 'FileCount': The number of files in the directory.
    """
    tool_message_print("get_directory_size", [("path", path)])
    total_size = 0
    file_count = 0

    for dirpath, _, filenames in os.walk(path):
        for f in filenames:
            fp = os.path.join(dirpath, f)
            if os.path.isfile(fp):
                total_size += os.path.getsize(fp)
                file_count += 1

    return {
        'TotalSize': format_size(total_size),
        'FileCount': file_count
    }


def get_multiple_directory_size(paths: list[str]) -> list[dict]:
    """Get the size of multiple directories.

    Args:
        paths: A list of paths to directories.

    Returns:
        list[dict]: A list of dictionaries containing the total size and the number of files in each directory.
        each item is the same as `get_directory_size`
    """
    tool_message_print("get_multiple_directory_size", [("paths", str(paths))])
    return [get_directory_size(path) for path in paths]


def read_file(filepath: str) -> str:
    """
    Read content from a single file, in utf-8 encoding only.

    Args:
      filepath: The path to the file.

    Returns:
        str: The content of the file as a string.
    """
    tool_message_print("read_file", [("filepath", filepath)])
    try:
        with open(filepath, 'r', encoding="utf-8") as f:
            return f.read()
    except Exception as e:
        tool_report_print("Error reading file:", str(e), is_error=True)
        return f"Error reading file: {e}"

def create_directory(paths: list[str]) -> bool:
    """
    Create single or multiple directories.

    Args:
      paths: A list of paths to the new directories.

    Returns:
        bool: True if directories were created successfully, False otherwise.
    """
    tool_message_print("create_directory", [("paths", str(paths))])
    try:
        success = True
        for path in paths:
            os.makedirs(path, exist_ok=True)
            tool_report_print("Created ✅:", path)
        return success
    except Exception as e:
        tool_report_print("Error creating directory:", str(e), is_error=True)
        return False

def get_file_metadata(filepath: str) -> dict:
    """
    Get metadata of a file.

    Args:
      filepath: The path to the file.

    Returns:
        dict: A dictionary containing file metadata:
              - 'creation_time': The timestamp of the file's creation.
              - 'modification_time': The timestamp of the file's last modification.
              - 'creation_time_readable': The creation time in ISO format.
              - 'modification_time_readable': The modification time in ISO format.
    """
    tool_message_print("get_file_metadata", [("filepath", filepath)])
    try:
        timestamp_creation = os.path.getctime(filepath)
        timestamp_modification = os.path.getmtime(filepath)
        return {
            'creation_time': timestamp_creation,
            'modification_time': timestamp_modification,
            'creation_time_readable': datetime.datetime.fromtimestamp(timestamp_creation).isoformat(),
            'modification_time_readable': datetime.datetime.fromtimestamp(timestamp_modification).isoformat()
        }
    except Exception as e:
        tool_report_print("Error getting file metadata:", str(e), is_error=True)
        return f"Error getting file metadata: {e}"


class FileData(BaseModel):
    file_path: str = Field(..., description="Path of the file, can be folder/folder2/filename.txt too")
    content: str = Field(..., description="Content of the file")

def write_files(files_data: list[FileData]) -> dict:
    """
    Write content to multiple files, supports nested directory file creation.
    
    Args:
      files_data: A list of FileData objects containing file paths and content.

    Returns:
      dict: A dictionary with file paths as keys and success status as values.
    """
    tool_message_print("write_files", [("count", str(len(files_data)))])
    results = {}
    
    for file_data in files_data:
        try:
            nested_dirs = os.path.dirname(file_data.file_path)
            if nested_dirs:
                os.makedirs(nested_dirs, exist_ok=True)

            with open(file_data.file_path, 'w', encoding="utf-8") as f:
                f.write(file_data.content)
            tool_report_print("Created ✅:", file_data.file_path)
            results[file_data.file_path] = True
        except Exception as e:
            tool_report_print("❌", file_data.file_path, is_error=True)
            tool_report_print("Error writing file:", str(e), is_error=True)
            results[file_data.file_path] = False

    success_count = sum(1 for success in results.values() if success)
    total_count = len(results)
    
    tool_report_print("Summary:", f"Wrote {success_count}/{total_count} files successfully")
    
    return results


def copy_file(src_filepath: str, dest_filepath: str) -> bool:
    """
    Copy a file from source to destination.

    Args:
      src_filepath: Path to the source file.
      dest_filepath: Path to the destination.

    Returns:
      bool: True if copy successful, False otherwise.
    """
    tool_message_print("copy_file", [("src_filepath", src_filepath), ("dest_filepath", dest_filepath)])
    try:
        shutil.copy2(src_filepath, dest_filepath) 
        tool_report_print("Status:", "File copied successfully")
        return True
    except Exception as e:
        tool_report_print("Error copying file:", str(e), is_error=True)
        return False

def move_file(src_filepath: str, dest_filepath: str) -> bool:
    """
    Move a file from source to destination.

    Args:
      src_filepath: Path to the source file.
      dest_filepath: Path to the destination.

    Returns:
      bool: True if move successful, False otherwise.
    """
    tool_message_print("move_file", [("src_filepath", src_filepath), ("dest_filepath", dest_filepath)])
    try:
        shutil.move(src_filepath, dest_filepath)
        tool_report_print("Status:", "File moved successfully")
        return True
    except Exception as e:
        tool_report_print("Error moving file:", str(e), is_error=True)
        return False
    
def rename_file(filepath: str, new_filename: str) -> bool:
    """
    Rename a file.

    Args:
      filepath: Current path to the file.
      new_filename: The new filename (not path, just the name).

    Returns:
      bool: True if rename successful, False otherwise.
    """
    tool_message_print("rename_file", [("filepath", filepath), ("new_filename", new_filename)])
    directory = os.path.dirname(filepath)
    new_filepath = os.path.join(directory, new_filename)
    try:
        os.rename(filepath, new_filepath)
        tool_report_print("Status:", "File renamed successfully")
        return True
    except Exception as e:
        tool_report_print("Error renaming file:", str(e), is_error=True)
        return False

def rename_directory(path: str, new_dirname: str) -> bool:
    """
    Rename a directory.

    Args:
      path: Current path to the directory.
      new_dirname: The new directory name (not path, just the name).

    Returns:
      bool: True if rename successful, False otherwise.
    """
    tool_message_print("rename_directory", [("path", path), ("new_dirname", new_dirname)])
    parent_dir = os.path.dirname(path)
    new_path = os.path.join(parent_dir, new_dirname)
    try:
        os.rename(path, new_path)
        tool_report_print("Status:", "Directory renamed successfully")
        return True
    except Exception as e:
        tool_report_print("Error renaming directory:", str(e), is_error=True)
        return False
    

def evaluate_math_expression(expression: str) -> str:
    """
    Evaluate a mathematical expression.

    Args:
      expression: The mathematical expression to evaluate.

    Returns: The result of the expression as a string, or an error message.
    """
    tool_message_print("evaluate_math_expression", [("expression", expression)])
    try:
        result = eval(expression, {}, {})
        tool_report_print("Expression evaluated:", str(result))
        return str(result)
    except Exception as e:
        tool_report_print("Error evaluating math expression:", str(e), is_error=True)
        return f"Error evaluating math expression: {e}"

def get_current_datetime() -> str:
    """
    Get the current time and date.

    Returns: A string representing the current time and date.
    """
    tool_message_print("get_current_datetime")
    now = datetime.datetime.now()
    time_str = now.strftime("%Y-%m-%d %H:%M:%S")
    return time_str

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

def open_url(url: str) -> bool:
    """
    Open a URL in the default web browser.

    Args:
      url: The URL to open.

    Returns: True if URL opened successfully, False otherwise.
    """
    tool_message_print("open_url", [("url", url)])
    try:
        webbrowser.open(url)
        tool_report_print("Status:", "URL opened successfully")
        return True
    except Exception as e:
        tool_report_print("Error opening URL:", str(e), is_error=True)
        return False

def get_website_text_content(url: str) -> str:
    """
    Fetch and return the text content of a webpage/article in nicely formatted markdown for easy readability.
    It doesn't contain everything, just links and text contents

    Args:
      url: The URL of the webpage.

    Returns: The text content of the website in markdown format, or an error message.
    """
    tool_message_print("get_website_text_content", [("url", url)])
    try:
        base = "https://md.dhr.wtf/?url="
        response = requests.get(base+url, headers={'User-Agent': DEFAULT_USER_AGENT})
        response.raise_for_status()  # Raise HTTPError for bad responses (4xx or 5xx)
        soup = BeautifulSoup(response.content, 'lxml')
        text_content = soup.get_text(separator='\n', strip=True) 
        tool_report_print("Status:", "Webpage content fetched successfully")
        return text_content
    except requests.exceptions.RequestException as e:
        tool_report_print("Error fetching webpage content:", str(e), is_error=True)
        return f"Error fetching webpage content: {e}"
    except Exception as e:
        tool_report_print("Error processing webpage content:", str(e), is_error=True)
        return f"Error processing webpage content: {e}"

def find_files(pattern: str, directory: str = ".", recursive: bool = False, include_hidden: bool = False) -> list[str]:
    """
    Searches for files (using glob) matching a given pattern within a specified directory.

    Args:
        pattern: The glob pattern to match (e.g., "*.txt", "data_*.csv").
        directory: The directory to search in (defaults to the current directory).
        recursive: Whether to search recursively in subdirectories (default is False).
        include_hidden: Whether to include hidden files (default is False).

    Returns:
        A list of file paths that match the pattern.  Returns an empty list if no matches are found.
        Returns an appropriate error message if the directory does not exist or is not accessible.
    """
    tool_message_print("find_files", [("pattern", pattern), ("directory", directory), 
                                      ("recursive", str(recursive)), ("include_hidden", str(include_hidden))])
    try:
        if not os.path.isdir(directory):
            tool_report_print("Error:", f"Directory '{directory}' not found.", is_error=True)
            return f"Error: Directory '{directory}' not found."  # Clear error message

        full_pattern = os.path.join(directory, pattern)  # Combine directory and pattern
        matches = glob.glob(full_pattern, recursive=recursive, include_hidden=include_hidden)

        # Check if the list is empty and return a message.
        if not matches:
            tool_report_print("Status:", "No files found matching the criteria.")
            return "No files found matching the criteria."

        tool_report_print("Status:", f"Found {len(matches)} matching files")
        return matches  # Return the list of matching file paths

    except OSError as e:
        tool_report_print("Error:", str(e), is_error=True)
        return f"Error: {e}"  # Return the system error message

def find_tools(query: str) -> list[str]:
    """
    Allows the assistant to find tools that fuzzy matchs a given query. 
    Use this when you are not sure if a tool exists or not, it is a fuzzy search.

    Args:
        query: The search query.

    Returns:
        A list of tool names and doc that match the query.
    """
    tool_message_print("find_tools", [("query", query)])
    # TOOLS variable is defined later
    tools = [tool.__name__ for tool in TOOLS]
    best_matchs = thefuzz.process.extractBests(query, tools) # [(tool_name, score), ...]
    return [
        [match[0], next((tool.__doc__.strip() for tool in TOOLS if tool.__name__ == match[0]), None)]
        for match in best_matchs
        if match[1] > 60 # only return tools with a score above 60
    ]

def read_file_at_specific_line_range(file_path: str, start_line: int, end_line: int) -> str:
    """
    Read a range of lines from a file (inclusive).
    If end_line exceeds the file length, it reads up to the last line.
    can read single line by passing same start_line and end_line

    Args:
        file_path: The path to the file.
        start_line: The number of the first line to read (must be valid).
        end_line: The number of the last line to read.

    Returns:
        The content of the lines, or an error message if start_line is invalid
        or if start_line > end_line.
    """
    tool_message_print("read_file_at_specific_line_range", [("file_path", file_path), ("start_line", start_line), ("end_line", end_line)])
    try:
        with open(file_path, "r", encoding="utf-8") as file:
            lines = file.readlines()
        num_lines = len(lines)

        if start_line < 1 or start_line > num_lines:
            return f"Error: Start line ({start_line}) is out of range (File has {num_lines} lines)."

        if start_line > end_line:
             return f"Error: Start line ({start_line}) cannot be greater than end line ({end_line})."

       
        selected_lines = lines[start_line - 1:end_line]
        return "\n".join(selected_lines).strip() 
    except FileNotFoundError:
        return f"File not found: {file_path}"
    except Exception as e:
        tool_report_print("Error reading file:", str(e), is_error=True)
        return f"Error reading file: {e}"

# Python script inspection
def inspect_python_script(filepath: str) -> list[str]:
    """
    Parses a Python file and returns details about
    its imports, classes, and functions/methods.

    Args:
        filepath: The path to the Python script.

    Returns:
        A list of dict containg function details.
    """
    tool_message_print("inspect_python_script", [("filepath", filepath)])
    try:
        return inspect_script(filepath)
    except FileNotFoundError:
        tool_report_print("File not found:", filepath, is_error=True)
        return "File not found"
    except SyntaxError:
        tool_report_print("Syntax error in file:", filepath, is_error=True)
        return "Syntax error in file"
    except Exception as e:
        tool_report_print("Error getting function details:", str(e), is_error=True)
        return []
    
def get_python_function_source_code(filepath: str, function_name: str) -> str:
    """
    Get the source code of a specific function within a Python file.

    Args:
        filepath: The path to the Python file.
        function_name: The name of the function to get the source code for.

    Returns:
        str: The source code of the function as a string, or an error message.
    """
    tool_message_print("get_python_function_source_code", [("filepath", filepath), ("function_name", function_name)])
    try:
        source_code = get_func_source_code(filepath, function_name)
        if source_code:
            return source_code
        else:
            return f"Error: Function '{function_name}' not found in '{filepath}'."
    except Exception as e:
        tool_report_print("Error getting function source code:", str(e), is_error=True)
        return f"Error getting function source code: {e}"


# Define known tools and their required/optional parameters
# Based on the ACTUAL functions listed in the TOOLS variable below
KNOWN_TOOLS = {
    "duckduckgo_search_tool": {"required": ["query"], "optional": []},
    "list_dir": {"required": ["path", "recursive", "files_only", "dirs_only"], "optional": []},
    "get_drives": {"required": [], "optional": []},
    "get_directory_size": {"required": ["path"], "optional": []},
    "get_multiple_directory_size": {"required": ["paths"], "optional": []},
    "read_file": {"required": ["filepath"], "optional": []},
    "create_directory": {"required": ["paths"], "optional": []},
    "get_file_metadata": {"required": ["filepath"], "optional": []},
    "write_files": {"required": ["files_data"], "optional": []},
    "read_file_at_specific_line_range": {"required": ["file_path", "start_line", "end_line"], "optional": []},
    "copy_file": {"required": ["src_filepath", "dest_filepath"], "optional": []},
    "move_file": {"required": ["src_filepath", "dest_filepath"], "optional": []},
    "rename_file": {"required": ["filepath", "new_filename"], "optional": []},
    "rename_directory": {"required": ["path", "new_dirname"], "optional": []},
    "find_files": {"required": ["pattern"], "optional": ["directory", "recursive", "include_hidden"]},
    "get_website_text_content": {"required": ["url"], "optional": []},
    "open_url": {"required": ["url"], "optional": []},
    "run_shell_command": {"required": ["command", "blocking"], "optional": ["print_output"]},
    "get_current_datetime": {"required": [], "optional": []},
    "evaluate_math_expression": {"required": ["expression"], "optional": []},
    "get_current_directory": {"required": [], "optional": []},
    "find_tools": {"required": ["query"], "optional": []},
    "inspect_python_script": {"required": ["filepath"], "optional": []},
    "get_python_function_source_code": {"required": ["filepath", "function_name"], "optional": []},
}

def validate_tool_call(tool_name: str, arguments: Dict) -> Tuple[bool, Optional[str]]:
    """
    Validates the tool name and arguments for a tool call.

    Args:
        tool_name: The name of the tool/function being called.
        arguments: The dictionary of arguments provided for the call.

    Returns:
        A tuple containing:
        - bool: True if the call is valid, False otherwise.
        - Optional[str]: An error message if validation fails, None otherwise.
    """
    if tool_name not in KNOWN_TOOLS:
        return False, f"Unknown tool name: '{tool_name}'"

    tool_schema = KNOWN_TOOLS[tool_name]
    required_params = set(tool_schema["required"])
    optional_params = set(tool_schema["optional"])
    all_allowed_params = required_params.union(optional_params)

    provided_params = set(arguments.keys())

    # Check for unknown parameters
    unknown_params = provided_params - all_allowed_params
    if unknown_params:
        # Allow 'suggest' within 'follow_up' for ask_followup_question
        # This check becomes slightly less direct without XML structure,
        # but we assume 'follow_up' contains a list if it's the special case.
        if not (tool_name == "ask_followup_question" and "follow_up" in arguments and isinstance(arguments.get("follow_up"), list)):
             # More general check for unknown params if not the ask_followup exception
             first_unknown = list(unknown_params)[0] # Get one example
             # Note: This simple check might need refinement if complex nested args are allowed
             # outside of the 'ask_followup_question' special case.
             # We need to be careful not to flag valid nested structures as unknown.
             # For now, we only check top-level keys.
             # A more robust solution might involve recursive schema validation if needed.
             pass # Relaxing this check slightly due to lack of XML structure info
             # Let's reconsider strictness here. The schema only defines top-level params.
             # If the LLM sends extra top-level keys, it's likely an error.
             # return False, f"Unknown parameter '{first_unknown}' provided for tool '{tool_name}'"


    # Check for missing required parameters
    missing_required = required_params - provided_params
    if missing_required:
        return False, f"Missing required parameters for tool '{tool_name}': {', '.join(sorted(list(missing_required)))}"

    # Check for empty required parameters
    for req_param in required_params:
        if req_param in arguments and (arguments[req_param] is None or arguments[req_param] == ""):
             # Special exceptions: allow empty text for browser_action type
             if tool_name == "browser_action" and arguments.get("action") == "type" and req_param == "text":
                 continue
             # Add other exceptions if needed
             return False, f"Required parameter '{req_param}' for tool '{tool_name}' cannot be empty"

    # Specific validation for browser_action based on action type
    if tool_name == "browser_action":
        action_value = arguments.get("action")
        has_url = "url" in arguments and arguments["url"]
        has_coord = "coordinate" in arguments and arguments["coordinate"]
        has_text = "text" in arguments # Allow empty string for typing

        if action_value == 'launch':
            if not has_url:
                return False, "Action 'launch' requires a non-empty 'url' parameter."
            if has_coord or has_text:
                 return False, "Action 'launch' should only have the 'url' parameter."
        elif action_value == 'click':
            if not has_coord:
                return False, "Action 'click' requires a non-empty 'coordinate' parameter."
            if has_url or has_text:
                 return False, "Action 'click' should only have the 'coordinate' parameter."
        elif action_value == 'type':
             # Note: Checking for key existence ('has_text') is enough here, as empty string is allowed.
             if "text" not in arguments:
                 return False, "Action 'type' requires a 'text' parameter."
             if has_url or has_coord:
                  return False, "Action 'type' should only have the 'text' parameter."
        elif action_value in ['scroll_down', 'scroll_up', 'close']:
             if has_url or has_coord or has_text:
                  return False, f"Action '{action_value}' should not have 'url', 'coordinate', or 'text' parameters."
        elif action_value:
            # Only fail if action_value is present but not recognized
             return False, f"Unknown 'action' value for browser_action: '{action_value}'"
        else:
             # Fail if action itself is missing (it's required)
             return False, f"Missing required parameter 'action' for tool '{tool_name}'"


    # Special check for ask_followup_question structure
    if tool_name == "ask_followup_question":
         follow_up_arg = arguments.get("follow_up")
         if not isinstance(follow_up_arg, list) or not follow_up_arg:
             return False, "Parameter 'follow_up' must be a non-empty list of suggestions."
         # Assuming suggestions are directly strings or simple objects in the list
         for suggestion in follow_up_arg:
             # Crude check for emptiness - might need refinement based on actual structure
             if not suggestion:
                 return False, "Suggestions within 'follow_up' cannot be empty."


    return True, None

# ... (rest of the file)
    """
    Returns the source code of a specific function.

    Args:
        filepath: The path to the Python script.
        function_name: The name of the function.

    Returns:
        The source code of the function.
    """
    tool_message_print("get_python_function_source_code", [("filepath", filepath), ("function_name", function_name)])
    try:
        return get_func_source_code(filepath, function_name)
    except FileNotFoundError:
        tool_report_print("File not found:", filepath, is_error=True)
        return "File not found"
    except SyntaxError:
        tool_report_print("Syntax error in file:", filepath, is_error=True)
        return "Syntax error in file"
    except Exception as e:
        tool_report_print("Error getting function source code:", str(e), is_error=True)
        return ""

TOOLS = [
    duckduckgo_search_tool,
    list_dir,
    get_drives,
    get_directory_size,
    get_multiple_directory_size,
    read_file,
    create_directory,
    get_file_metadata,
    write_files,
    read_file_at_specific_line_range,
    copy_file,
    move_file,
    rename_file,
    rename_directory,
    find_files,
    get_website_text_content,
    open_url,
    run_shell_command,
    get_current_datetime,
    evaluate_math_expression,
    get_current_directory,
    find_tools,
    inspect_python_script,
    get_python_function_source_code
]