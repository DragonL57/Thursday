"""
Assistant Package - AI assistant with streaming, tool execution and image handling

This package contains modules for working with the Pollinations AI API
with streaming capabilities, tool calling, and multi-modal interaction.
"""

from .core import Assistant
from .tool_handler import process_tool_calls, convert_to_pydantic_model
from .api_client import ApiClient

# Re-export main class and important functions for backward compatibility
__all__ = ['Assistant', 'process_tool_calls', 'convert_to_pydantic_model', 'ApiClient']
