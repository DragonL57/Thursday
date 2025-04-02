"""
Functions for web-related operations.
"""

import webbrowser
import requests
from bs4 import BeautifulSoup
from duckduckgo_search import DDGS

from .formatting import tool_message_print, tool_report_print
import config as conf

DEFAULT_USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36"

def duckduckgo_search_tool(query: str) -> list:
    """
    Searches DuckDuckGo for the given query and returns a list of results.

    Args:
        query: The search query.

    Returns:
        list: A list of search results.
    """
    tool_message_print("duckduckgo_search_tool", [("query", query)])
    try:
        ddgs = DDGS(timeout=conf.DUCKDUCKGO_TIMEOUT)
        results = ddgs.text(query, max_results=conf.MAX_DUCKDUCKGO_SEARCH_RESULTS)
        return results
    except Exception as e:
        tool_report_print("Error during DuckDuckGo search:", str(e), is_error=True)
        return f"Error during DuckDuckGo search: {e}"

def get_website_text_content(url: str) -> str:
    """
    Fetch and return the text content of a webpage/article in nicely formatted markdown for easy readability.
    It doesn't contain everything, just links and text contents

    Args:
      url: The URL of the webpage.

    Returns: The text content of the website in markdown format, or an error message.
    """
    tool_message_print("get_website_text_content", [("url", url)])
    try:
        base = "https://md.dhr.wtf/?url="
        response = requests.get(base+url, headers={'User-Agent': DEFAULT_USER_AGENT})
        response.raise_for_status()  # Raise HTTPError for bad responses (4xx or 5xx)
        soup = BeautifulSoup(response.content, 'lxml')
        text_content = soup.get_text(separator='\n', strip=True) 
        tool_report_print("Status:", "Webpage content fetched successfully")
        return text_content
    except requests.exceptions.RequestException as e:
        tool_report_print("Error fetching webpage content:", str(e), is_error=True)
        return f"Error fetching webpage content: {e}"
    except Exception as e:
        tool_report_print("Error processing webpage content:", str(e), is_error=True)
        return f"Error processing webpage content: {e}"

def open_url(url: str) -> bool:
    """
    Open a URL in the default web browser.

    Args:
      url: The URL to open.

    Returns: True if URL opened successfully, False otherwise.
    """
    tool_message_print("open_url", [("url", url)])
    try:
        webbrowser.open(url)
        tool_report_print("Status:", "URL opened successfully")
        return True
    except Exception as e:
        tool_report_print("Error opening URL:", str(e), is_error=True)
        return False
