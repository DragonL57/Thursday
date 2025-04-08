"""
Functions for step-by-step thinking and reasoning.
"""

from .formatting import tool_message_print, tool_report_print

def think(thought: str) -> str:
    """
    A tool for the assistant to think step-by-step, work through complex problems,
    or make strategic decisions. This creates a dedicated space for structured thinking
    and improves performance on complex tasks, especially when:
    
    1. Analyzing outputs from previous tool calls
    2. Following detailed policies or guidelines
    3. Making sequential decisions where each step builds on previous ones
    4. Breaking down complex problems into manageable steps
    
    Args:
        thought: The thinking process, analysis, or reasoning steps.
        
    Returns:
        The detailed thinking process that was provided.
    """
    tool_message_print("think", [("thought", thought)])
    
    # Log the thinking process for visibility
    tool_report_print("Thinking process:", thought)
    
    # Return the actual thought content instead of a generic confirmation message
    return thought
