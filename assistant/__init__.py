"""
Assistant Package - AI assistant with streaming, tool execution and image handling

This package contains modules for working with the Pollinations AI API
with streaming capabilities, tool calling, and multi-modal interaction.
"""

from .core import Assistant

# Re-export main class for backward compatibility
__all__ = ['Assistant']
