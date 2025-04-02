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

def duckduckgo_search_tool(
    query: str, 
    max_results: int = None, 
    region: str = None,
    time_filter: str = None,
    safe_search: bool = True
) -> list:
    """
    Searches DuckDuckGo for the given query and returns a list of results.

    Args:
        query: The search query.
        max_results: Maximum number of results to return (defaults to config value).
        region: Region code for localized results (e.g., 'us-en', 'uk-en', 'de-de').
        time_filter: Time filter for results ('d' for day, 'w' for week, 'm' for month, 'y' for year).
        safe_search: Whether to enable safe search filtering.

    Returns:
        list: A list of search results.
    """
    tool_message_print("duckduckgo_search_tool", [
        ("query", query), 
        ("max_results", str(max_results) if max_results else "default"),
        ("region", region if region else "default"),
        ("time_filter", time_filter if time_filter else "all time"),
        ("safe_search", str(safe_search))
    ])
    try:
        ddgs = DDGS(timeout=conf.DUCKDUCKGO_TIMEOUT)
        results = ddgs.text(
            query, 
            max_results=max_results or conf.MAX_DUCKDUCKGO_SEARCH_RESULTS,
            region=region,
            safesearch=safe_search,
            timelimit=time_filter
        )
        return list(results)  # Convert generator to list
    except Exception as e:
        tool_report_print("Error during DuckDuckGo search:", str(e), is_error=True)
        return f"Error during DuckDuckGo search: {e}"

def get_website_text_content(
    url: str, 
    timeout: int = 30, 
    extract_mode: str = "text"
) -> str:
    """
    Fetch and return the text content of a webpage/article.

    Args:
      url: The URL of the webpage.
      timeout: Request timeout in seconds.
      extract_mode: Content extraction mode ('text', 'markdown', 'article').
                   'text' extracts plain text, 'markdown' preserves some formatting,
                   'article' attempts to extract main article content.

    Returns: The text content of the website in the requested format, or an error message.
    """
    tool_message_print("get_website_text_content", [
        ("url", url), 
        ("timeout", str(timeout)),
        ("extract_mode", extract_mode)
    ])
    
    try:
        if extract_mode == "article":
            # Use readability-style extraction through the md.dhr.wtf service
            base = "https://md.dhr.wtf/?url="
            response = requests.get(base+url, headers={'User-Agent': DEFAULT_USER_AGENT}, timeout=timeout)
        else:
            # Direct request for other extraction modes
            response = requests.get(url, headers={'User-Agent': DEFAULT_USER_AGENT}, timeout=timeout)
            
        response.raise_for_status()
        
        soup = BeautifulSoup(response.content, 'lxml')
        
        # Remove script and style elements
        for script_or_style in soup(['script', 'style', 'meta', 'noscript']):
            script_or_style.decompose()
        
        if extract_mode == "markdown":
            # A simple markdown conversion that preserves links and headers
            result = []
            for elem in soup.find_all(['p', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'li']):
                text = elem.get_text(strip=True)
                if not text:
                    continue
                    
                # Handle headings
                if elem.name.startswith('h') and len(elem.name) == 2:
                    level = int(elem.name[1])
                    result.append('#' * level + ' ' + text)
                # Handle links
                elif elem.find('a'):
                    for a in elem.find_all('a'):
                        href = a.get('href', '')
                        if href and href.startswith(('http', '/')):
                            link_text = a.get_text(strip=True)
                            if link_text:
                                a.replace_with(f'[{link_text}]({href})')
                    result.append(elem.get_text(strip=True))
                else:
                    result.append(text)
                    
            content = '\n\n'.join(result)
        else:
            # Default text mode
            content = soup.get_text(separator='\n\n', strip=True)
        
        tool_report_print("Status:", "Webpage content fetched successfully")
        return content
    except requests.exceptions.RequestException as e:
        tool_report_print("Error fetching webpage content:", str(e), is_error=True)
        return f"Error fetching webpage content: {e}"
    except Exception as e:
        tool_report_print("Error processing webpage content:", str(e), is_error=True)
        return f"Error processing webpage content: {e}"
