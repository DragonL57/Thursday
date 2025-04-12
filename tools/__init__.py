"""
Tools package for the Gem Assistant.

This package contains all the tools that the assistant can use.
The tools are organized into modules based on their functionality.
"""

# Import all formatting functions
from .formatting import tool_message_print, tool_report_print

# Import the new consolidated filesystem interface
from .filesys import FileSys

# Import all web functions
from .web import (
    read_website_content,
    web_search,
    get_youtube_transcript
)

# Import all system functions
from .system import (
    run_shell_command,
    get_current_datetime,
    get_command_output,
    kill_background_process,
    list_background_processes,
    get_command_history,
    get_system_info
)

# Import all Python tools
from .python_tools import (
    inspect_python_script,
    get_python_function_source_code
)

# Import thinking tools
from .thinking import think

# Import planning tools
from .plan import create_plan, update_plan, add_plan_step, get_plans, clear_plans, reset_plans

# Import Reddit tools
from .reddit import search_reddit_posts, get_reddit_post, get_subreddit_posts

# Import validation
from .validation import (
    validate_tool_call,
    KNOWN_TOOLS
)

# Define filesystem tools from the consolidated FileSys class
file_system_navigator = FileSys.navigator
file_reader = FileSys.reader
file_writer = FileSys.writer
file_manager = FileSys.manager
file_searcher = FileSys.searcher
file_archiver = FileSys.archiver
file_converter = FileSys.converter

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
    
    # Filesystem tools - organized by category
    # Navigation and info
    file_system_navigator.get_current_directory,
    file_system_navigator.list_directory,
    file_system_navigator.get_file_metadata,
    file_system_navigator.get_directory_size,
    
    # File content operations
    file_reader.read_text,
    file_reader.read_binary,
    file_reader.read_lines,
    file_reader.read_structured_file,
    file_writer.write_text,
    file_writer.write_multiple,
    file_writer.write_structured_file,
    
    # File management
    file_manager.copy,
    file_manager.move,
    file_manager.create_directory,
    file_manager.delete,
    
    # Search
    file_searcher.find_files,
    file_searcher.grep_in_files,
    
    # Archive operations
    file_archiver.create_zip,
    file_archiver.extract_archive,
    file_archiver.list_archive_contents,
    
    # File conversion
    file_converter.convert_to_json,
    file_converter.convert_from_json,
    
    # System tools
    run_shell_command,
    get_current_datetime,
    get_command_output,
    kill_background_process,
    list_background_processes,
    get_command_history,
    get_system_info,
    
    # Python tools
    inspect_python_script,
    get_python_function_source_code,
    
    # Thinking tools
    think,
    
    # Plan tools - checklist functionality
    create_plan,
    update_plan,
    add_plan_step,
    get_plans,
    clear_plans
]

# Now import and patch the find_tools function to use our TOOLS list
from .utils import find_tools as _find_tools_orig

# Create a new version of find_tools with the TOOLS list pre-injected
def find_tools(query: str) -> list[str]:
    """Find tools that match the provided query."""
    return _find_tools_orig(TOOLS, query)

# Add find_tools to TOOLS list after it's been created
TOOLS.append(find_tools)
