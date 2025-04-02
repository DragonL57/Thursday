"""
Tools package for the Gem Assistant.

This package contains all the tools that the assistant can use.
The tools are organized into modules based on their functionality.
"""

# Import all formatting functions
from .formatting import tool_message_print, tool_report_print

# Import all filesystem functions
from .filesystem import (
    get_current_directory,
    list_dir,
    get_drives,
    get_directory_size,
    get_multiple_directory_size,
    read_file,
    create_directory,
    get_file_metadata,
    write_files,
    copy_file,
    move_file,
    rename_file,
    rename_directory,
    find_files,
    read_file_at_specific_line_range
)

# Import all web functions
from .web import (
    duckduckgo_search_tool,
    get_website_text_content
)

# Import all system functions
from .system import (
    run_shell_command,
    get_current_datetime
)

# Import all Python tools
from .python_tools import (
    inspect_python_script,
    get_python_function_source_code
)

# Import utility functions but not the ones that depend on TOOLS
from .utils import (
    evaluate_math_expression
)

# Import validation
from .validation import (
    validate_tool_call,
    KNOWN_TOOLS
)

# First define the tools list
TOOLS = [
    # Web tools
    duckduckgo_search_tool,
    get_website_text_content,
    
    # Filesystem tools
    get_current_directory,
    list_dir,
    get_drives,
    get_directory_size,
    get_multiple_directory_size,
    read_file,
    create_directory,
    get_file_metadata,
    write_files,
    copy_file,
    move_file,
    rename_file,
    rename_directory,
    find_files,
    read_file_at_specific_line_range,
    
    # System tools
    run_shell_command,
    get_current_datetime,
    
    # Python tools
    inspect_python_script,
    get_python_function_source_code,
    
    # Utility tools
    evaluate_math_expression
]

# Now import and patch the find_tools function to use our TOOLS list
from .utils import find_tools as _find_tools_orig

# Create a new version of find_tools with the TOOLS list pre-injected
def find_tools(query: str) -> list[str]:
    return _find_tools_orig(query, TOOLS)

# Add find_tools to TOOLS list after it's been created
TOOLS.append(find_tools)
