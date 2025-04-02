"""
Functions for web-related operations.
"""

import webbrowser
import requests
from bs4 import BeautifulSoup
from duckduckgo_search import DDGS
from duckduckgo_search.exceptions import DuckDuckGoSearchException, RatelimitException, TimeoutException

from .formatting import tool_message_print, tool_report_print
import config as conf
from urllib.parse import urlparse

DEFAULT_USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36"

def duckduckgo_search_tool(
    query: str, 
    max_results: int = 5, 
    region: str = "default", 
    time_filter: str = "all time", 
    safe_search: bool = True
):
    """
    Perform a search using DuckDuckGo and return the results.
    
    Args:
        query (str): The search query
        max_results (int): The maximum number of results to return
        region (str): The region for the search (default to "wt-wt")
        time_filter (str): Filter results by time ('day', 'week', 'month', 'year', or 'all time')
        safe_search (bool): Whether to enable safe search
    
    Returns:
        list: List of search results, each containing title, url, and snippet
    """
    tool_report_print("DuckDuckGo Search", f"query='{query}' | max={max_results} | region={region} | time={time_filter} | safe={safe_search}")
    
    # Convert region "default" to "wt-wt" (worldwide)
    if region == "default":
        region = "wt-wt"
    
    # Convert time filter string to expected format
    time_mapping = {
        "all time": None,
        "day": "d",
        "week": "w",
        "month": "m",
        "year": "y"
    }
    timelimit = time_mapping.get(time_filter.lower(), None)
    
    # Convert boolean safe_search to string format expected by the API
    safesearch = "moderate"
    if safe_search is True:
        safesearch = "on"
    elif safe_search is False:
        safesearch = "off"
    
    try:
        with DDGS() as ddgs:
            results = list(ddgs.text(
                keywords=query,
                region=region,
                safesearch=safesearch,
                timelimit=timelimit,
                max_results=max_results,
                backend="auto"  # Try all backends in random order
            ))
            
        tool_report_print("Search Complete", f"Found {len(results)} results")
        return results
    except TimeoutException as e:
        error_message = f"DuckDuckGo search timed out: {e}"
        tool_report_print("Search Error", error_message, is_error=True)
        return [{"title": "Search Timeout", "href": "", "body": f"Search for '{query}' timed out. Please try again later."}]
    except RatelimitException as e:
        error_message = f"DuckDuckGo search rate limited: {e}"
        tool_report_print("Search Error", error_message, is_error=True)
        return [{"title": "Rate Limit Reached", "href": "", "body": f"Search rate limit reached. Please try again later with a simpler query."}]
    except DuckDuckGoSearchException as e:
        error_message = f"DuckDuckGo search error: {e}"
        tool_report_print("Search Error", error_message, is_error=True)
        return [{"title": "Search Error", "href": "", "body": f"Error searching for '{query}'. Error: {str(e)}. Please try a different query."}]
    except Exception as e:
        error_message = f"Error during DuckDuckGo search: {e}"
        tool_report_print("Search Error", error_message, is_error=True)
        return [{"title": "Search Error", "href": "", "body": f"Failed to search for '{query}'. Error: {str(e)}. Please try again with a different query or use another approach."}]

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
