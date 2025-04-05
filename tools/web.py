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
    # Initial tool call announcement with output format
    tool_message_print("DuckDuckGo Search", [
        ("query", f"'{query}'"),
        ("max", str(max_results)),
        ("region", region),
        ("time", time_filter),
        ("safe", str(safe_search))
    ], is_output=True)
    
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
      extract_mode: Content extraction mode ('text' or 'markdown').
                   'text' extracts plain text, 'markdown' preserves some formatting.

    Returns: The text content of the website in the requested format, or an error message.
    """
    # Initial tool announcement
    tool_message_print("get_website_text_content", [
        ("url", url), 
        ("timeout", str(timeout)),
        ("extract_mode", extract_mode)
    ])
    
    # Show execution output
    tool_message_print("get_website_text_content", [
        ("url", url), 
        ("timeout", str(timeout)),
        ("extract_mode", extract_mode)
    ], is_output=True)
    
    # More sophisticated User-Agent rotation to avoid detection
    user_agents = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:124.0) Gecko/20100101 Firefox/124.0",
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36",
        "Mozilla/5.0 (iPhone; CPU iPhone OS 17_4_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1"
    ]
    
    # Choose a random user agent
    import random
    headers = {
        'User-Agent': random.choice(user_agents),
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.5',
        'Accept-Encoding': 'gzip, deflate, br',
        'DNT': '1',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1',
        'Sec-Fetch-Dest': 'document',
        'Sec-Fetch-Mode': 'navigate',
        'Sec-Fetch-Site': 'none',
        'Sec-Fetch-User': '?1',
        'Cache-Control': 'max-age=0',
    }
    
    def try_wayback_machine(target_url, original_error=None):
        """Try to get content from Internet Archive's Wayback Machine as a fallback"""
        try:
            tool_report_print("Direct access failed:", 
                             f"Trying to retrieve from Wayback Machine archive...",
                             is_error=True)
            
            # First, get the latest snapshot URL from the Wayback Machine API
            import json
            wayback_api_url = f"https://archive.org/wayback/available?url={target_url}"
            response = requests.get(wayback_api_url, timeout=timeout)
            data = response.json()
            
            # Check if we have a snapshot
            if data and 'archived_snapshots' in data and 'closest' in data['archived_snapshots']:
                archive_url = data['archived_snapshots']['closest']['url']
                
                # Get the content from the archive
                tool_report_print("Archive found:", f"Retrieving from {archive_url}")
                archive_response = requests.get(archive_url, headers=headers, timeout=timeout)
                archive_response.raise_for_status()
                
                # Note: Archive.org adds its own headers/footers, so we need to extract the main content
                archive_soup = BeautifulSoup(archive_response.content, 'lxml')
                
                # Look for the archived content frame - it's usually in an iframe with id="playback"
                # or the main content is in a specific div structure
                main_content = archive_soup.find(id="playback")
                if main_content and main_content.find('iframe'):
                    # Need to retrieve the iframe source
                    iframe_src = main_content.find('iframe').get('src')
                    if iframe_src:
                        if iframe_src.startswith('http'):
                            full_url = iframe_src
                        else:
                            full_url = f"https://web.archive.org{iframe_src}"
                            
                        iframe_response = requests.get(full_url, headers=headers, timeout=timeout)
                        iframe_response.raise_for_status()
                        return iframe_response.content, True
                else:
                    # Try to extract the main content directly
                    return archive_response.content, True
            
            return None, False
        except Exception as e:
            tool_report_print("Archive retrieval failed:", str(e), is_error=True)
            if original_error:
                return None, False
            else:
                return None, False
    
    try:
        # Parse the URL to check if it's valid
        parsed_url = urlparse(url)
        if not parsed_url.scheme or not parsed_url.netloc:
            raise ValueError(f"Invalid URL format: {url}")
            
        # Add protocol if missing
        if not parsed_url.scheme:
            url = "https://" + url
            tool_report_print("URL Update:", f"Added https:// to URL: {url}")
        
        content = None
        used_archive = False
        
        # Try direct access first
        try:
            # First attempt with normal request
            try:
                response = requests.get(url, headers=headers, timeout=timeout)
                response.raise_for_status()
            except requests.exceptions.HTTPError as e:
                # If we get a 403 Forbidden or 429 Too Many Requests, try with a different approach
                if e.response.status_code in [403, 429, 500, 502, 503, 504]:
                    # First, try with different headers
                    tool_report_print("Initial request failed:", f"Status code: {e.response.status_code}. Trying with different headers...", is_error=True)
                    
                    headers['User-Agent'] = random.choice([ua for ua in user_agents if ua != headers['User-Agent']])
                    headers['Referer'] = "https://www.google.com/"
                    
                    # Add a small delay to avoid rate limiting
                    import time
                    time.sleep(2)
                    
                    try:
                        response = requests.get(url, headers=headers, timeout=timeout)
                        response.raise_for_status()
                    except requests.exceptions.HTTPError as inner_e:
                        # If that also fails with 403/429, try Internet Archive
                        if inner_e.response.status_code in [403, 429, 451]:
                            archive_content, archive_success = try_wayback_machine(url, inner_e)
                            if archive_success and archive_content:
                                content = archive_content
                                used_archive = True
                            else:
                                raise inner_e
                        else:
                            raise inner_e
                else:
                    raise e
                    
            if not content:  # If we didn't get content from archive
                content = response.content
                
        except requests.exceptions.RequestException as direct_e:
            # For any request exception, try the archive
            archive_content, archive_success = try_wayback_machine(url, direct_e)
            if archive_success and archive_content:
                content = archive_content
                used_archive = True
            else:
                raise direct_e
        
        soup = BeautifulSoup(content, 'lxml')
        
        # If we used archive.org, try to clean up archive-specific elements
        if used_archive:
            # Remove any Wayback Machine toolbar or overlay
            for element in soup.select('.wb-header, #wm-ipp-base, #donato'):
                if element:
                    element.decompose()
            
            tool_report_print("Source:", "Content retrieved from Internet Archive's Wayback Machine")
                
        # Remove script, style, and other non-content elements
        for element in soup(['script', 'style', 'meta', 'noscript', 'header', 'footer', 'nav', 'aside', 'iframe', 'svg']):
            element.decompose()
            
        # Check if content seems too short, which might indicate an anti-scraping page
        body_text = soup.body.get_text(strip=True) if soup.body else ""
        if len(body_text) < 200 and "captcha" in body_text.lower():
            tool_report_print("Warning:", "Website may be showing a CAPTCHA page or anti-bot measures", is_error=True)
            return "Error: This website appears to be protected against automated access. It might be showing a CAPTCHA or using anti-bot measures."
            
        # Process based on extraction mode
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
                        if href:
                            # Handle relative URLs
                            if href.startswith('/'):
                                href = f"{parsed_url.scheme}://{parsed_url.netloc}{href}"
                            link_text = a.get_text(strip=True)
                            if link_text:
                                a.replace_with(f'[{link_text}]({href})')
                    result.append(elem.get_text(strip=True))
                else:
                    result.append(text)
                    
            content = '\n\n'.join(result)
        else:
            # Default text mode - with better formatting
            # Remove excessive whitespace and newlines
            for br in soup.find_all('br'):
                br.replace_with('\n')
                
            content = soup.get_text(separator='\n\n', strip=True)
            
            # Clean up the content: remove multiple newlines and spaces
            import re
            content = re.sub(r'\n{3,}', '\n\n', content)  # Replace 3+ newlines with 2
            content = re.sub(r' {2,}', ' ', content)      # Replace 2+ spaces with 1
        
        # Truncate if content is very long
        if len(content) > 50000:
            content = content[:50000] + "\n\n[Content truncated due to length...]"
            tool_report_print("Notice:", "Content was truncated because it exceeded 50,000 characters")
            
        tool_report_print("Status:", "Webpage content fetched successfully")
        return content
        
    except requests.exceptions.RequestException as e:
        error_message = f"Error fetching webpage content: {e}"
        tool_report_print("Error fetching webpage:", str(e), is_error=True)
        
        # Provide more helpful error messages based on status code
        if hasattr(e, 'response') and e.response is not None:
            status_code = e.response.status_code
            if status_code == 403:
                error_message += "\nThe website is blocking access. This could be due to bot protection or geographical restrictions."
            elif status_code == 404:
                error_message += "\nThe page does not exist. Please check the URL for typos."
            elif status_code == 429:
                error_message += "\nToo many requests sent to this website. Try again later."
            elif status_code >= 500:
                error_message += "\nThe server is experiencing issues. This is not a problem with your request. Try again later."
        
        # Check for common network issues and provide better explanations
        if "Timeout" in str(e):
            error_message += "\nThe website took too long to respond. It might be down or have connectivity issues."
        elif "SSLError" in str(e):
            error_message += "\nThere was a security issue when connecting to this website. It might have an invalid SSL certificate."
        elif "ConnectionError" in str(e):
            error_message += "\nCould not establish a connection to the website. It might be down or unreachable."
            
        return error_message
    except Exception as e:
        tool_report_print("Error processing webpage:", str(e), is_error=True)
        return f"Error processing webpage content: {e}"
