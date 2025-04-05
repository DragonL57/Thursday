"""
Utility functions for Assistant module
"""

import re
import textwrap
import json
import functools
from typing import Callable, List, Dict, Any, Union

def cmd(names: List[str], description: str = ""):
    """
    Decorator to register a method as a command.
    
    Args:
        names: List of command names
        description: Description of the command
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            return func(*args, **kwargs)
        
        wrapper.__command__ = True
        wrapper.__command_names__ = names
        wrapper.__command_description__ = description
        
        return wrapper
    
    return decorator

def wrap_text(text: str, width: int) -> List[str]:
    """
    Custom text wrapper that preserves bullet points and indentation.
    
    Args:
        text: Text to wrap
        width: Maximum width in characters
        
    Returns:
        List of wrapped lines
    """
    lines = []
    for line in text.split('\n'):
        is_bullet = line.lstrip().startswith(('•', '-', '*', '1.', '2.', '3.', '4.', '5.', '6.', '7.', '8.', '9.'))
        indent = len(line) - len(line.lstrip())
        
        if is_bullet:
            available_width = width - indent - 2
        else:
            available_width = width
        
        if len(line) > width:
            words = line.split()
            current_line = []
            current_length = indent
            
            for word in words:
                if current_length + len(word) + 1 <= available_width:
                    current_line.append(word)
                    current_length += len(word) + 1
                else:
                    if current_line:
                        lines.append(' ' * indent + ' '.join(current_line))
                    current_line = [word]
                    current_length = indent + len(word)
            
            if current_line:
                lines.append(' ' * indent + ' '.join(current_line))
        else:
            lines.append(line)
    
    return lines

def format_markdown(text: str) -> str:
    """
    Format text for markdown display, with special handling for code blocks.
    
    Args:
        text: Markdown text to format
        
    Returns:
        Formatted markdown text
    """
    # Preserve code blocks
    code_blocks = []
    
    def replace_code_block(match):
        code_blocks.append(match.group(0))
        return f"CODE_BLOCK_{len(code_blocks) - 1}"
    
    # Extract and replace code blocks with placeholders
    pattern = r'```[\s\S]*?```'
    text_with_placeholders = re.sub(pattern, replace_code_block, text)
    
    # Apply other formatting rules here...
    
    # Restore code blocks
    for i, block in enumerate(code_blocks):
        text_with_placeholders = text_with_placeholders.replace(f"CODE_BLOCK_{i}", block)
    
    return text_with_placeholders

def parse_json_safely(text: str) -> Union[Dict[str, Any], List[Any], None]:
    """
    Safely parse JSON with error handling.
    
    Args:
        text: JSON text to parse
        
    Returns:
        Parsed JSON object or None if parsing fails
    """
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return None
