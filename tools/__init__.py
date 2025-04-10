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
    read_website_content,
    web_search,
    get_youtube_transcript
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

# Import thinking tools
from .thinking import think

# Import note-taking tools
from .notes import add_note, update_note, get_notes, clear_notes, reset_notes

# Import Reddit tools
from .reddit import search_reddit_posts, get_reddit_post, get_subreddit_posts

# Import validation
from .validation import (
    validate_tool_call,
    KNOWN_TOOLS
)

# Define tools available to the AI
TOOLS = [
    # Web tools
    web_search,
    read_website_content,
    get_youtube_transcript,
    
    # Reddit tools
    search_reddit_posts,
    get_reddit_post,
    get_subreddit_posts,
    
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
    
    # Thinking tools
    think,
    
    # Note-taking tools - use the actual functions instead of dictionaries
    add_note,
    update_note,
    get_notes,
    clear_notes
]

# Now import and patch the find_tools function to use our TOOLS list
from .utils import find_tools as _find_tools_orig

# Create a new version of find_tools with the TOOLS list pre-injected
def find_tools(query: str) -> list[str]:
    return _find_tools_orig(query, TOOLS)

# Add find_tools to TOOLS list after it's been created
TOOLS.append(find_tools)
