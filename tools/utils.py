"""
Miscellaneous utility functions.
"""

import thefuzz.process

from .formatting import tool_message_print, tool_report_print

def find_tools(query: str, tools=None) -> list[str]:
    """
    Allows the assistant to find tools that fuzzy matchs a given query. 
    Use this when you are not sure if a tool exists or not, it is a fuzzy search.

    Args:
        query: The search query.
        tools: List of tool functions to search within (injected by __init__.py)

    Returns:
        A list of tool names and doc that match the query.
    """
    tool_message_print("find_tools", [("query", query)])
    
    if tools is None:
        return []
    
    # Get tool names from the provided tools list
    tool_names = [tool.__name__ for tool in tools]
    best_matchs = thefuzz.process.extractBests(query, tool_names) # [(tool_name, score), ...]
    return [
        [match[0], next((tool.__doc__.strip() for tool in tools if tool.__name__ == match[0]), None)]
        for match in best_matchs
        if match[1] > 60 # only return tools with a score above 60
    ]
