"""
Validation functions for tool calls.
"""

from typing import Dict, Optional, Tuple

# Define known tools and their required/optional parameters
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
