"""
Functions for Python code inspection and manipulation.
"""

from gem.inspection import inspect_script, get_func_source_code
from .formatting import tool_message_print, tool_report_print

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
