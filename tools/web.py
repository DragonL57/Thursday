"""
Functions for web-related operations.
"""
import re  
import random
import time
import io
import json
import requests
import asyncio
import aiohttp
from bs4 import BeautifulSoup
from duckduckgo_search import DDGS
from duckduckgo_search.exceptions import DuckDuckGoSearchException, RatelimitException, TimeoutException
from typing import List, Dict, Union, Optional, Tuple, Any
from urllib.parse import urlparse, urljoin
import hashlib
import os
from datetime import datetime, timedelta
from pathlib import Path

from .formatting import tool_message_print, tool_report_print

# Add Selenium imports
try:
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.common.exceptions import TimeoutException as SeleniumTimeoutException
    from selenium.webdriver.chrome.service import Service
    from selenium.webdriver.common.action_chains import ActionChains
    from selenium.webdriver.common.keys import Keys
    SELENIUM_AVAILABLE = True
except ImportError:
    SELENIUM_AVAILABLE = False

# Try to import Scrapy for advanced scraping capabilities
try:
    import scrapy
    from scrapy import Selector
    SCRAPY_AVAILABLE = True
except ImportError:
    SCRAPY_AVAILABLE = False

# Try to import undetected_chromedriver for enhanced anti-bot capabilities
try:
    import undetected_chromedriver as uc
    UNDETECTED_CHROME_AVAILABLE = True
except ImportError:
    UNDETECTED_CHROME_AVAILABLE = False

# Add support for requests_html for JavaScript rendering without full browser
try:
    from requests_html import HTMLSession
    REQUESTS_HTML_AVAILABLE = True
except ImportError:
    REQUESTS_HTML_AVAILABLE = False

# Try to import fake_useragent for better user agent rotation
try:
    from fake_useragent import UserAgent
    UA_GENERATOR_AVAILABLE = True
except ImportError:
    UA_GENERATOR_AVAILABLE = False

# Check if chardet is available for better encoding detection
try:
    import chardet
    CHARDET_AVAILABLE = True
except ImportError:
    CHARDET_AVAILABLE = False

# Default fallback user agents if fake_useragent is not available
DEFAULT_USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36"
FALLBACK_USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15", 
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_4_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Edge/133.0.2623.0 Safari/537.36",
    "Mozilla/5.0 (iPad; CPU OS 17_4_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1"
]

# Dictionary to track websites that are likely to need JavaScript rendering
JS_REQUIRED_SITES = {}

# Let's remember which sites need headless browser vs standard requests
SITE_CAPABILITIES = {}

# Create a simple cache for web responses to avoid redundant requests
CACHE_DIR = Path.home() / ".cache" / "web_scraper"
CACHE_EXPIRY = 24  # hours

# Ensure cache directory exists
CACHE_DIR.mkdir(parents=True, exist_ok=True)

# Common website parsers for popular sites
SITE_SPECIFIC_PARSERS = {
    "youtube.com": "parse_youtube",
    "twitter.com": "parse_twitter",
    "x.com": "parse_twitter",
    "reddit.com": "parse_reddit",
    "github.com": "parse_github",
    "medium.com": "parse_medium",
    "news.ycombinator.com": "parse_hacker_news"
}

def web_search(
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

def fetch_webpage(
    url: str, 
    timeout: int = 10, 
    extract_mode: str = "text",
    extract_links: bool = True,
    bypass_bot_protection: bool = False,
    use_cache: bool = True,
    cache_expiry_hours: int = 24,
    smart_retry: bool = True,
    render_js: bool = True
) -> Dict[str, Any]:
    """
    Enhanced web content extractor with multiple levels of fallbacks, caching, and anti-bot protection.

    Args:
        url: The URL of the webpage.
        timeout: Request timeout in seconds.
        extract_mode: Content extraction mode ('text', 'markdown', or 'html').
            'text' extracts plain text, 'markdown' preserves some formatting, 'html' returns cleaned HTML.
        extract_links: Whether to extract and include links from the page.
        bypass_bot_protection: Try extra measures to bypass anti-bot protections.
        use_cache: Whether to use cached responses when available.
        cache_expiry_hours: How long to keep cached responses valid.
        smart_retry: Use adaptive retry strategies for difficult sites.
        render_js: Whether to attempt JavaScript rendering for dynamic content.

    Returns: 
        A dictionary containing the extracted content and metadata:
        {
            'content': str,           # The main content text/html
            'title': str,             # Page title if available
            'links': Dict,            # Categorized links if extract_links=True
            'success': bool,          # Whether extraction was successful
            'source': str,            # Source of extraction (direct/archive/fallback)
            'error': str,             # Error message if any
            'timestamp': str          # When the content was fetched
        }
    """
    # Initial tool announcement
    tool_message_print("fetch_webpage", [
        ("url", url), 
        ("timeout", str(timeout)),
        ("extract_mode", extract_mode),
        ("extract_links", str(extract_links)),
        ("bypass_bot_protection", str(bypass_bot_protection))
    ])
    
    # Result template
    result = {
        'content': "",
        'title': "",
        'links': {},
        'success': False,
        'source': "direct",
        'error': "",
        'timestamp': datetime.now().isoformat()
    }
    
    # Check if URL looks valid
    if not url.startswith(('http://', 'https://')):
        result['error'] = f"Invalid URL: {url}. URLs must start with http:// or https://."
        result['success'] = False
        tool_report_print("Error:", result['error'], is_error=True)
        return result
    
    # Clean URL (remove tracking parameters)
    try:
        parsed_url = urlparse(url)
        clean_url = f"{parsed_url.scheme}://{parsed_url.netloc}{parsed_url.path}"
        if parsed_url.query:
            # Keep essential query params, remove common tracking ones
            query_params = parsed_url.query.split("&")
            clean_params = []
            for param in query_params:
                if not param.startswith(('utm_', 'fbclid', 'gclid', 'msclkid')):
                    clean_params.append(param)
            if clean_params:
                clean_url += '?' + '&'.join(clean_params)
        url = clean_url
    except Exception as e:
        tool_report_print("Warning:", f"Error cleaning URL: {str(e)}")
    
    # Check cache if enabled
    if use_cache:
        cached_result = _get_cached_page(url)
        if cached_result:
            # Check if cache is still valid
            cache_time = datetime.fromisoformat(cached_result.get('timestamp', '2000-01-01'))
            if cache_time > datetime.now() - timedelta(hours=cache_expiry_hours):
                tool_report_print("Cache:", "Retrieved content from cache")
                return cached_result
            else:
                tool_report_print("Cache:", "Cache expired, fetching fresh content")
    
    # Determine the best method to fetch the content based on site capabilities
    domain = urlparse(url).netloc
    
    # Check if this domain has been marked as requiring JavaScript
    js_required = JS_REQUIRED_SITES.get(domain, False)
    if '.js' in url.lower() or 'javascript:' in url.lower():
        # Direct JavaScript file, don't try to render
        js_required = False
        render_js = False
    
    # Check if this is a known PDF or other document
    is_document = _is_document_url(url)
    if is_document:
        # Don't use JavaScript rendering for documents
        js_required = False
        render_js = False
    
    # Try different methods in sequence based on site capabilities
    methods_to_try = _determine_fetch_methods(
        url=url,
        js_required=js_required,
        bypass_bot_protection=bypass_bot_protection,
        render_js=render_js,
        is_document=is_document
    )
    
    for method_name, method_func, method_params in methods_to_try:
        try:
            tool_report_print("Trying:", f"Method: {method_name}")
            method_result = method_func(url=url, timeout=timeout, **method_params)
            
            if method_result['success']:
                result.update(method_result)
                
                # Update site capability information for future requests
                if domain not in SITE_CAPABILITIES:
                    SITE_CAPABILITIES[domain] = {'preferred_method': method_name}
                
                # Process the content according to extract_mode
                if extract_mode == 'text':
                    result['content'] = _extract_readable_text(result['content'])
                elif extract_mode == 'markdown':
                    result['content'] = _convert_to_markdown(result['content'])
                # 'html' mode keeps the HTML content as is
                
                # Extract links if requested
                if extract_links:
                    result['links'] = _extract_links(result['content'], url)
                
                # Cache the successful result if caching is enabled
                if use_cache:
                    _cache_page(url, result)
                
                return result
                
        except Exception as e:
            tool_report_print("Method failed:", f"{method_name}: {str(e)}", is_error=True)
            continue
    
    # If we've tried all methods and none worked, try using the Internet Archive
    try:
        tool_report_print("Trying:", "Internet Archive Wayback Machine")
        archive_result = _get_from_wayback(url, timeout)
        if archive_result['success']:
            result.update(archive_result)
            result['source'] = "archive"
            
            # Process content according to extract_mode
            if extract_mode == 'text':
                result['content'] = _extract_readable_text(result['content'])
            elif extract_mode == 'markdown':
                result['content'] = _convert_to_markdown(result['content'])
                
            # Extract links if requested
            if extract_links:
                result['links'] = _extract_links(result['content'], url)
                
            # Cache the archive result if caching is enabled
            if use_cache:
                _cache_page(url, result)
                
            return result
    except Exception as e:
        tool_report_print("Archive failed:", str(e), is_error=True)
    
    # If all methods failed
    result['error'] = "All fetch methods failed for this URL"
    result['success'] = False
    tool_report_print("Error:", "Could not retrieve content by any available method", is_error=True)
    return result

def _determine_fetch_methods(url, js_required, bypass_bot_protection, render_js, is_document):
    """
    Determine the sequence of fetch methods to try based on URL analysis and available tools.
    Returns a list of tuples: (method_name, method_function, method_params)
    """
    methods = []
    domain = urlparse(url).netloc
    
    # If this is a document (PDF, etc.), prioritize direct download
    if is_document:
        methods.append(("direct_download", _fetch_document, {}))
    
    # Get the preferred method for this domain if known
    preferred_method = SITE_CAPABILITIES.get(domain, {}).get('preferred_method', None)
    
    # If JavaScript is required or we should render it
    if js_required or render_js:
        # Use undetected_chromedriver for high bot protection sites if available
        if bypass_bot_protection and UNDETECTED_CHROME_AVAILABLE:
            methods.append(("undetected_chrome", _fetch_with_undetected_chrome, {"stealth": True}))
        
        # Add Selenium method if available
        if SELENIUM_AVAILABLE:
            methods.append(("selenium", _fetch_with_selenium, {"headless": not bypass_bot_protection}))
            
        # Add requests-html renderer for lighter JS rendering
        if REQUESTS_HTML_AVAILABLE:
            methods.append(("requests_html", _fetch_with_requests_html, {}))
    
    # Always add standard requests method as it's the fastest
    methods.append(("requests", _fetch_with_requests, {"retry": True}))
    
    # Add a specialized anti-bot method if needed
    if bypass_bot_protection:
        methods.append(("anti_bot", _fetch_with_anti_bot_measures, {}))
    
    # If we have a known preferred method for this domain, prioritize it
    if preferred_method:
        methods.sort(key=lambda m: 0 if m[0] == preferred_method else 1)
        
    return methods

def _fetch_with_requests(url, timeout, retry=True):
    """Fetch content using the standard requests library"""
    result = {
        'content': "",
        'title': "",
        'success': False,
        'source': "direct",
        'error': "",
        'timestamp': datetime.now().isoformat()
    }
    
    # Get a good user agent
    headers = _get_request_headers()
    
    try:
        # Make the request
        response = requests.get(url, headers=headers, timeout=timeout)
        response.raise_for_status()
        
        # Check if the response is binary content
        content_type = response.headers.get('Content-Type', '').lower()
        if _is_binary_content(content_type):
            result['content'] = f"Binary content detected: {content_type}"
            result['success'] = False
            result['error'] = "Content is binary and cannot be displayed as text"
            return result
        
        # Detect and decode content with proper encoding
        content = _decode_content(response.content)
        
        # Parse content
        soup = BeautifulSoup(content, 'lxml')
        
        # Get title
        title_tag = soup.find('title')
        if title_tag:
            result['title'] = title_tag.get_text(strip=True)
        
        # Check if it's likely a bot protection page
        if _is_bot_protection_page(content):
            result['error'] = "Bot protection detected"
            result['success'] = False
            return result
            
        # Store the HTML content
        result['content'] = str(soup)
        result['success'] = True
        
        return result
        
    except requests.exceptions.HTTPError as e:
        if retry and hasattr(e, 'response') and e.response.status_code in [403, 429, 503]:
            # Try again with different headers
            tool_report_print("Retrying:", f"Got {e.response.status_code}, trying with different headers")
            time.sleep(2)  # Small delay
            
            # Different headers
            headers = _get_request_headers(advanced=True)
            
            try:
                response = requests.get(url, headers=headers, timeout=timeout)
                response.raise_for_status()
                
                # Process content as above
                content = _decode_content(response.content)
                soup = BeautifulSoup(content, 'lxml')
                
                if title_tag := soup.find('title'):
                    result['title'] = title_tag.get_text(strip=True)
                
                if _is_bot_protection_page(content):
                    result['error'] = "Bot protection detected"
                    result['success'] = False
                else:
                    result['content'] = str(soup)
                    result['success'] = True
                
                return result
                
            except Exception as retry_error:
                result['error'] = f"Retry failed: {str(retry_error)}"
                result['success'] = False
                return result
        else:
            result['error'] = str(e)
            result['success'] = False
            return result
            
    except Exception as e:
        result['error'] = str(e)
        result['success'] = False
        return result

def _fetch_with_selenium(url, timeout, headless=True):
    """Fetch content using Selenium WebDriver with Chrome"""
    if not SELENIUM_AVAILABLE:
        return {'success': False, 'error': "Selenium not available"}
    
    result = {
        'content': "",
        'title': "",
        'success': False,
        'source': "direct",
        'error': "",
        'timestamp': datetime.now().isoformat()
    }
    
    driver = None
    try:
        # Set up Chrome options
        chrome_options = Options()
        if headless:
            chrome_options.add_argument("--headless=new")
        
        # Add common options to make browser more stable
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--disable-features=VizDisplayCompositor")
        chrome_options.add_argument("--disable-extensions")
        chrome_options.add_argument("--disable-in-process-stack-traces")
        
        # Add stealth options to avoid detection
        chrome_options.add_argument("--disable-blink-features=AutomationControlled")
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        chrome_options.add_experimental_option('useAutomationExtension', False)
        
        # Set a realistic user agent
        user_agent = _get_user_agent()
        chrome_options.add_argument(f"--user-agent={user_agent}")
        
        # Initialize driver
        driver = webdriver.Chrome(options=chrome_options)
        driver.set_page_load_timeout(timeout)
        
        # Add window size to mimic a real browser
        driver.set_window_size(1366, 768)
        
        # Navigate to URL
        driver.get(url)
        
        # Wait for page to load
        WebDriverWait(driver, timeout).until(
            EC.presence_of_element_located((By.TAG_NAME, "body"))
        )
        
        # Additional waiting for dynamic content
        time.sleep(2)
        
        # Execute any needed interactions if bot protection is detected
        if "captcha" in driver.page_source.lower() or "cloudflare" in driver.page_source.lower():
            _try_bypass_protection(driver)
            
            # Wait again after bypass attempt
            time.sleep(3)
        
        # Get the title
        result['title'] = driver.title
        
        # Get the content
        result['content'] = driver.page_source
        result['success'] = True
        
        return result
        
    except Exception as e:
        result['error'] = f"Selenium error: {str(e)}"
        result['success'] = False
        return result
        
    finally:
        # Make sure to quit the driver
        if driver:
            driver.quit()

def _fetch_with_undetected_chrome(url, timeout, stealth=True):
    """Fetch content using undetected_chromedriver to bypass strong anti-bot measures"""
    if not UNDETECTED_CHROME_AVAILABLE:
        return {'success': False, 'error': "undetected_chromedriver not available"}
    
    result = {
        'content': "",
        'title': "",
        'success': False,
        'source': "direct",
        'error': "",
        'timestamp': datetime.now().isoformat()
    }
    
    driver = None
    try:
        # Configure undetected Chrome
        options = uc.ChromeOptions()
        
        # Add minimal arguments to avoid detection
        options.add_argument("--disable-extensions")
        
        # Create the driver
        driver = uc.Chrome(options=options, headless=False)  # Headless often doesn't work with undetected_chromedriver
        driver.set_page_load_timeout(timeout)
        
        # Navigate to URL
        driver.get(url)
        
        # Wait for page to load
        time.sleep(5)  # Undetected Chrome sometimes needs more time
        
        # Get the title
        result['title'] = driver.title
        
        # Get the content
        result['content'] = driver.page_source
        result['success'] = True
        
        return result
        
    except Exception as e:
        result['error'] = f"Undetected Chrome error: {str(e)}"
        result['success'] = False
        return result
        
    finally:
        # Make sure to quit the driver
        if driver:
            driver.quit()

def _fetch_with_requests_html(url, timeout):
    """Fetch content using requests-html for lightweight JavaScript rendering"""
    if not REQUESTS_HTML_AVAILABLE:
        return {'success': False, 'error': "requests-html not available"}
    
    result = {
        'content': "",
        'title': "",
        'success': False,
        'source': "direct",
        'error': "",
        'timestamp': datetime.now().isoformat()
    }
    
    try:
        # Create session
        session = HTMLSession()
        
        # Set headers
        session.headers.update(_get_request_headers())
        
        # Make request
        response = session.get(url, timeout=timeout)
        
        # Render JavaScript
        response.html.render(timeout=timeout)
        
        # Get the title
        title_elem = response.html.find('title', first=True)
        if title_elem:
            result['title'] = title_elem.text
        
        # Get the content
        result['content'] = response.html.html
        result['success'] = True
        
        return result
        
    except Exception as e:
        result['error'] = f"requests-html error: {str(e)}"
        result['success'] = False
        return result

def _fetch_with_anti_bot_measures(url, timeout):
    """Fetch content with specialized anti-bot measures"""
    result = {
        'content': "",
        'title': "",
        'success': False,
        'source': "direct",
        'error': "",
        'timestamp': datetime.now().isoformat()
    }
    
    try:
        # Create a session to maintain cookies
        session = requests.Session()
        
        # Set very realistic headers
        headers = _get_request_headers(advanced=True)
        session.headers.update(headers)
        
        # First make a request to the domain root to get cookies
        parsed_url = urlparse(url)
        domain_url = f"{parsed_url.scheme}://{parsed_url.netloc}"
        
        # GET request to domain root
        session.get(domain_url, timeout=timeout/2)
        
        # Small delay to seem more human
        time.sleep(1.5)
        
        # Now make the actual request
        response = session.get(url, timeout=timeout)
        response.raise_for_status()
        
        # Decode content
        content = _decode_content(response.content)
        
        # Parse content
        soup = BeautifulSoup(content, 'lxml')
        
        # Get title
        title_tag = soup.find('title')
        if title_tag:
            result['title'] = title_tag.get_text(strip=True)
        
        # Check if it's still a bot protection page
        if _is_bot_protection_page(content):
            result['error'] = "Still detected as bot despite countermeasures"
            result['success'] = False
            return result
        
        # Store content
        result['content'] = str(soup)
        result['success'] = True
        
        return result
        
    except Exception as e:
        result['error'] = f"Anti-bot method error: {str(e)}"
        result['success'] = False
        return result

def _fetch_document(url, timeout):
    """Fetch document content (PDF, DOC, etc.) and extract text"""
    result = {
        'content': "",
        'title': "",
        'success': False,
        'source': "direct",
        'error': "",
        'timestamp': datetime.now().isoformat()
    }
    
    try:
        # Get document file
        headers = _get_request_headers()
        response = requests.get(url, headers=headers, timeout=timeout, stream=True)
        response.raise_for_status()
        
        # Check content type
        content_type = response.headers.get('Content-Type', '').lower()
        
        # Get filename from URL or headers
        filename = None
        if 'Content-Disposition' in response.headers:
            disposition = response.headers['Content-Disposition']
            filename_match = re.search(r'filename="?([^";]+)"?', disposition)
            if filename_match:
                filename = filename_match.group(1)
        
        if not filename:
            # Try to get from URL
            path = urlparse(url).path
            if path:
                filename = path.split('/')[-1]
        
        # Extract text based on document type
        if 'application/pdf' in content_type or url.lower().endswith('.pdf'):
            text = _extract_pdf_text(response.content)
            result['content'] = text
            result['title'] = filename or "PDF Document"
            result['success'] = True
            
        elif any(url.lower().endswith(ext) for ext in ['.doc', '.docx']):
            result['content'] = f"Document file detected: {filename or url}"
            result['title'] = filename or "Word Document"
            result['success'] = False
            result['error'] = "Word document extraction not supported yet"
            
        else:
            # For other document types
            result['content'] = f"Document file detected: {filename or url} ({content_type})"
            result['title'] = filename or "Document"
            result['success'] = False
            result['error'] = f"Document type ({content_type}) extraction not supported"
        
        return result
        
    except Exception as e:
        result['error'] = f"Document extraction error: {str(e)}"
        result['success'] = False
        return result

def _get_from_wayback(url, timeout):
    """Retrieve content from the Internet Archive's Wayback Machine"""
    result = {
        'content': "",
        'title': "",
        'success': False,
        'source': "archive",
        'error': "",
        'timestamp': datetime.now().isoformat()
    }
    
    try:
        # Get the latest snapshot from Wayback API
        wayback_api_url = f"https://archive.org/wayback/available?url={url}"
        api_response = requests.get(wayback_api_url, timeout=timeout)
        api_response.raise_for_status()
        
        data = api_response.json()
        
        # Check if we have a snapshot
        if data and 'archived_snapshots' in data and 'closest' in data['archived_snapshots']:
            archive_url = data['archived_snapshots']['closest']['url']
            
            # Get the content from the archive
            tool_report_print("Archive found:", f"Retrieving from {archive_url}")
            
            # Get headers for the archive request
            headers = _get_request_headers()
            
            # Fetch the archived page
            archive_response = requests.get(archive_url, headers=headers, timeout=timeout)
            archive_response.raise_for_status()
            
            # Decode content
            content = _decode_content(archive_response.content)
            
            # Parse with BeautifulSoup
            soup = BeautifulSoup(content, 'lxml')
            
            # Remove Wayback Machine UI elements
            for element in soup.select('.wb-header, #wm-ipp-base, #donato'):
                if element:
                    element.decompose()
            
            # Get the title
            title_tag = soup.find('title')
            if title_tag:
                result['title'] = title_tag.get_text(strip=True)
            
            # Store content
            result['content'] = str(soup)
            result['success'] = True
            
            return result
        else:
            result['error'] = "No archive found in Wayback Machine"
            result['success'] = False
            return result
            
    except Exception as e:
        result['error'] = f"Wayback Machine error: {str(e)}"
        result['success'] = False
        return result

# Helper functions

def _get_request_headers(advanced=False):
    """Generate realistic browser headers"""
    user_agent = _get_user_agent()
    
    # Basic headers
    headers = {
        'User-Agent': user_agent,
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
    
    # Add more realistic headers if advanced mode
    if advanced:
        # Common referers
        referers = [
            'https://www.google.com/',
            'https://www.bing.com/',
            'https://duckduckgo.com/',
            'https://www.reddit.com/',
            'https://www.facebook.com/',
            'https://www.twitter.com/',
            'https://www.linkedin.com/'
        ]
        
        headers['Referer'] = random.choice(referers)
        
        # Add random client hints
        if 'Chrome' in user_agent:
            headers['Sec-CH-UA'] = '"Google Chrome";v="133", "Chromium";v="133", "Not-A.Brand";v="99"'
            headers['Sec-CH-UA-Mobile'] = random.choice(['?0', '?1'])
            headers['Sec-CH-UA-Platform'] = random.choice(['"Windows"', '"macOS"', '"Linux"', '"Android"', '"iOS"'])
    
    return headers

def _get_user_agent():
    """Get a realistic user agent string"""
    if UA_GENERATOR_AVAILABLE:
        try:
            ua = UserAgent()
            return ua.random
        except Exception:
            pass
    
    # Fallback to our list
    return random.choice(FALLBACK_USER_AGENTS)

def _decode_content(content):
    """Intelligently detect encoding and decode content"""
    # Try to detect encoding with chardet if available
    if CHARDET_AVAILABLE:
        try:
            detection = chardet.detect(content)
            if detection and detection['confidence'] > 0.7:
                try:
                    return content.decode(detection['encoding'])
                except (UnicodeDecodeError, LookupError):
                    # If detected encoding failed, continue to other methods
                    pass
        except Exception:
            pass
    
    # Try common encodings
    encodings = ['utf-8', 'latin1', 'utf-16', 'windows-1252', 'iso-8859-1']
    for encoding in encodings:
        try:
            return content.decode(encoding)
        except (UnicodeDecodeError, LookupError):
            continue
    
    # Last resort - force with replacement
    return content.decode('utf-8', errors='replace')

def _extract_readable_text(html_content):
    """Extract clean readable text from HTML content"""
    try:
        soup = BeautifulSoup(html_content, 'lxml')
        
        # Remove script, style and other non-content elements
        for element in soup(['script', 'style', 'meta', 'noscript', 'svg']):
            element.decompose()
        
        # For each <br> tag, insert a newline
        for br in soup.find_all('br'):
            br.insert_after('\n')
        
        # Extract text with proper spacing
        text = soup.get_text(separator='\n\n', strip=True)
        
        # Clean up the text
        text = re.sub(r'\n{3,}', '\n\n', text)  # Replace multiple newlines with double
        text = re.sub(r' {2,}', ' ', text)      # Replace multiple spaces
        
        return text
    except Exception as e:
        tool_report_print("Warning:", f"Error extracting readable text: {str(e)}")
        # Return a sanitized version of the HTML if extraction fails
        return re.sub(r'<[^>]+>', ' ', html_content)

def _convert_to_markdown(html_content):
    """Convert HTML content to markdown format"""
    try:
        soup = BeautifulSoup(html_content, 'lxml')
        
        # Remove script, style and unwanted elements
        for element in soup(['script', 'style', 'meta', 'noscript', 'svg']):
            element.decompose()
        
        # Create a result container
        result = []
        
        # Add the title if available
        title_tag = soup.find('title')
        if title_tag and title_tag.get_text(strip=True):
            result.append(f"# {title_tag.get_text(strip=True)}\n")
        
        # Process headings
        for i in range(1, 7):
            for heading in soup.find_all(f'h{i}'):
                text = heading.get_text(strip=True)
                if text:
                    result.append(f"{'#' * i} {text}\n")
        
        # Process paragraphs
        for p in soup.find_all('p'):
            text = p.get_text(strip=True)
            if text:
                # Handle links in paragraphs
                for a in p.find_all('a'):
                    href = a.get('href')
                    link_text = a.get_text(strip=True)
                    if href and link_text:
                        # Make sure href is absolute
                        if not href.startswith(('http://', 'https://')):
                            base_url = soup.find('base', href=True)
                            base = base_url['href'] if base_url else None
                            href = urljoin(base or '', href)
                        
                        # Replace link with markdown format
                        a_text = str(a)
                        p_text = str(p)
                        p_text = p_text.replace(a_text, f"[{link_text}]({href})")
                        p = BeautifulSoup(p_text, 'lxml').p
                
                # Add paragraph text
                result.append(f"{p.get_text(strip=True)}\n\n")
        
        # Process lists
        for ul in soup.find_all('ul'):
            for li in ul.find_all('li'):
                text = li.get_text(strip=True)
                if text:
                    result.append(f"* {text}\n")
            result.append("\n")
        
        for ol in soup.find_all('ol'):
            for i, li in enumerate(ol.find_all('li')):
                text = li.get_text(strip=True)
                if text:
                    result.append(f"{i+1}. {text}\n")
            result.append("\n")
        
        # Join all parts
        markdown_text = ''.join(result)
        
        # Clean up excessive newlines
        markdown_text = re.sub(r'\n{3,}', '\n\n', markdown_text)
        
        return markdown_text
    except Exception as e:
        tool_report_print("Warning:", f"Error converting to markdown: {str(e)}")
        # Fall back to plain text extraction
        return _extract_readable_text(html_content)

def _extract_links(html_content, base_url):
    """Extract and categorize links from HTML content"""
    links = {
        'navigation': [],
        'content': [],
        'external': [],
        'social': []
    }
    
    try:
        soup = BeautifulSoup(html_content, 'lxml')
        base_domain = urlparse(base_url).netloc
        
        # Get all links
        for a in soup.find_all('a', href=True):
            href = a['href']
            text = a.get_text(strip=True)
            
            # Skip empty, javascript, and fragment-only links
            if not href or href.startswith('javascript:') or href == '#':
                continue
            
            # Make sure href is absolute
            if not href.startswith(('http://', 'https://')):
                href = urljoin(base_url, href)
            
            # Check if it's internal or external
            parsed_href = urlparse(href)
            is_internal = parsed_href.netloc == base_domain or not parsed_href.netloc
            
            # Format the link
            link_entry = {
                'text': text or href,
                'url': href
            }
            
            # Categorize the link
            if is_internal:
                # Check if it's likely navigation
                parent = a.parent
                grandparent = parent.parent if parent else None
                
                is_nav = False
                if parent and parent.name in ['nav', 'header', 'footer']:
                    is_nav = True
                elif grandparent and grandparent.name in ['nav', 'header', 'footer']:
                    is_nav = True
                elif a.get('role') == 'navigation' or (parent and parent.get('role') == 'navigation'):
                    is_nav = True
                
                if is_nav:
                    links['navigation'].append(link_entry)
                else:
                    links['content'].append(link_entry)
            else:
                # Check if it's a social media link
                social_domains = ['facebook.com', 'twitter.com', 'linkedin.com', 'instagram.com', 
                                 'youtube.com', 'pinterest.com', 'tiktok.com']
                                 
                is_social = any(domain in parsed_href.netloc for domain in social_domains)
                
                if is_social:
                    links['social'].append(link_entry)
                else:
                    links['external'].append(link_entry)
        
        # Limit the number of links in each category
        for category in links:
            if len(links[category]) > 20:
                links[category] = links[category][:20]
                
        return links
    except Exception as e:
        tool_report_print("Warning:", f"Error extracting links: {str(e)}")
        return links

def _extract_pdf_text(content):
    """Extract text from PDF content"""
    try:
        # Try PyPDF2 first
        try:
            from PyPDF2 import PdfReader
            pdf_file = io.BytesIO(content)
            pdf_reader = PdfReader(pdf_file)
            
            # Extract text from all pages
            pdf_text = []
            for page_num in range(len(pdf_reader.pages)):
                page = pdf_reader.pages[page_num]
                text = page.extract_text() or ""
                pdf_text.append(text)
            
            return "\n\n--- Page Break ---\n\n".join(pdf_text)
        except ImportError:
            # Try pdfplumber if PyPDF2 is not available
            try:
                import pdfplumber
                pdf_file = io.BytesIO(content)
                with pdfplumber.open(pdf_file) as pdf:
                    pdf_text = []
                    for page in pdf.pages:
                        text = page.extract_text() or ""
                        pdf_text.append(text)
                    
                    return "\n\n--- Page Break ---\n\n".join(pdf_text)
            except ImportError:
                return "PDF text extraction requires PyPDF2 or pdfplumber libraries."
    except Exception as e:
        return f"Error extracting PDF text: {str(e)}"

def _is_binary_content(content_type):
    """Check if the content type is binary/non-textual"""
    binary_types = [
        'image/', 'audio/', 'video/', 'application/octet-stream', 
        'application/zip', 'application/x-rar', 'application/x-tar',
        'application/x-7z', 'application/x-gzip'
    ]
    
    return any(btype in content_type for btype in binary_types)

def _is_document_url(url):
    """Check if URL appears to be a document file"""
    document_extensions = ['.pdf', '.doc', '.docx', '.ppt', '.pptx', '.xls', '.xlsx', '.odt', '.rtf']
    return any(url.lower().endswith(ext) for ext in document_extensions)

def _is_bot_protection_page(content):
    """Detect if the page is likely a bot protection/CAPTCHA page"""
    # Common bot protection indicators in content
    bot_indicators = [
        'captcha', 'robot', 'automated', 'bot', 'human verification',
        'cloudflare', 'ddos', 'protection', 'challenge', 'blocked',
        'security check', 'prove you are human', "prove you're human",
        'access denied', 'access to this page has been denied', 
        'please wait', 'please enable javascript', 'checking your browser',
        'press & hold', 'press and hold'
    ]
    
    content_lower = content.lower()
    
    # Count how many indicators are present
    indicator_count = sum(1 for indicator in bot_indicators if indicator in content_lower)
    
    # If content is short and has multiple indicators, likely a protection page
    content_length = len(content)
    if content_length < 10000 and indicator_count >= 2:
        return True
        
    # Check for specific protection services
    protection_services = [
        'cloudflare', 'imperva', 'akamai', 'distil', 'perimeterx',
        'datadome', 'f5', 'incapsula', 'kasada', 'sitelock'
    ]
    
    service_mentions = sum(1 for service in protection_services if service in content_lower)
    if service_mentions > 0 and indicator_count > 0:
        return True
    
    return False

def _try_bypass_protection(driver):
    """Try common techniques to bypass bot protection in Selenium"""
    try:
        # Look for "I'm human" buttons or checkboxes
        human_buttons = driver.find_elements(By.XPATH, 
            "//button[contains(text(), 'human') or contains(text(), 'continue') or contains(text(), 'verify')]")
        
        for button in human_buttons:
            if button.is_displayed():
                button.click()
                time.sleep(2)
                return
        
        # Look for CAPTCHA iframes
        captcha_frames = driver.find_elements(By.CSS_SELECTOR, 
            "iframe[src*='captcha'], iframe[src*='challenge'], iframe[title*='challenge']")
        
        if captcha_frames:
            # Switch to the frame
            driver.switch_to.frame(captcha_frames[0])
            
            # Try to find and click the checkbox
            checkboxes = driver.find_elements(By.CSS_SELECTOR, 
                ".recaptcha-checkbox, input[type='checkbox']")
            
            for checkbox in checkboxes:
                if checkbox.is_displayed():
                    checkbox.click()
                    time.sleep(1)
                    
            # Switch back
            driver.switch_to.default_content()
        
        # Press and hold simulation for some protections
        body = driver.find_element(By.TAG_NAME, "body")
        if "press & hold" in body.text.lower() or "press and hold" in body.text.lower():
            buttons = driver.find_elements(By.CSS_SELECTOR, "button, .button, [role='button']")
            
            for button in buttons:
                if button.is_displayed():
                    actions = ActionChains(driver)
                    actions.click_and_hold(button)
                    actions.pause(3)  # Hold for 3 seconds
                    actions.release()
                    actions.perform()
                    time.sleep(1)
    except Exception:
        # Silently fail - this is just a best effort
        pass

def _cache_page(url, result):
    """Save fetched page to cache"""
    try:
        # Create a unique filename based on URL
        url_hash = hashlib.md5(url.encode()).hexdigest()
        cache_path = CACHE_DIR / f"{url_hash}.json"
        
        # Save result as JSON
        with open(cache_path, 'w', encoding='utf-8') as f:
            # Make a copy to avoid modifying the original
            cache_data = result.copy()
            json.dump(cache_data, f)
            
    except Exception as e:
        tool_report_print("Cache warning:", f"Failed to save to cache: {str(e)}")

def _get_cached_page(url):
    """Get page from cache if available"""
    try:
        # Create a unique filename based on URL
        url_hash = hashlib.md5(url.encode()).hexdigest()
        cache_path = CACHE_DIR / f"{url_hash}.json"
        
        # Check if file exists and is not empty
        if cache_path.exists() and cache_path.stat().st_size > 0:
            with open(cache_path, 'r', encoding='utf-8') as f:
                return json.load(f)
                
    except Exception as e:
        tool_report_print("Cache warning:", f"Failed to read from cache: {str(e)}")
    
    return None

# For backward compatibility
def read_website_content(
    url: str, 
    timeout: int = 5, 
    extract_mode: str = "text",
    extract_links: bool = False
) -> str:
    """
    Legacy function that calls the new fetch_webpage function and returns just the content.
    
    Args:
      url: The URL of the webpage.
      timeout: Request timeout in seconds.
      extract_mode: Content extraction mode ('text' or 'markdown').
                   'text' extracts plain text, 'markdown' preserves some formatting.
      extract_links: Whether to extract and include links from the page.

    Returns: The text content of the website in the requested format, or an error message.
    """
    # Call the new function
    result = fetch_webpage(
        url=url,
        timeout=timeout,
        extract_mode=extract_mode,
        extract_links=extract_links,
        use_cache=True
    )
    
    # Process the result to match the old function's output
    if result['success']:
        content = result['content']
        
        # Add title if available
        if result['title'] and extract_mode != 'text':
            content = f"# {result['title']}\n\n{content}"
            
        # Add extracted links if requested
        if extract_links and result['links']:
            content += "\n\n## Website Navigation\n\n"
            
            if result['links']['navigation']:
                content += "\n### Navigation Links\n"
                for link in result['links']['navigation'][:15]:
                    content += f"- [{link['text']}]({link['url']})\n"
            
            if result['links']['content']:
                content += "\n### Content Links\n"
                for link in result['links']['content'][:20]:
                    content += f"- [{link['text']}]({link['url']})\n"
            
            if result['links']['external']:
                content += "\n### External Links\n"
                for link in result['links']['external'][:10]:
                    content += f"- [{link['text']}]({link['url']})\n"
        
        return content
    else:
        return f"Error fetching webpage content: {result['error']}"

def get_youtube_transcript(
    url_or_id: str,
    languages: List[str] = ["en"],  # Change from list to List[str]
    combine_all: bool = True
) -> str:
    """
    Fetch the transcript of a YouTube video.
    
    Args:
      url_or_id: YouTube URL or video ID.
      languages: List of language codes to try, in order of preference.
      combine_all: If True, combine all transcript parts into a single text.
                  If False, keep timestamp information.
    
    Returns: The transcript text or a structured representation with timestamps.
    """
    # Initial tool announcement
    tool_message_print("get_youtube_transcript", [
        ("url_or_id", url_or_id), 
        ("languages", str(languages)),
        ("combine_all", str(combine_all))
    ])
    
    try:
        # Import the necessary package
        from youtube_transcript_api import YouTubeTranscriptApi, TranscriptsDisabled, NoTranscriptFound
        
        # Extract video ID from URL if needed
        video_id = url_or_id
        if "youtube.com" in url_or_id or "youtu.be" in url_or_id:
            # Handle youtu.be format
            if "youtu.be/" in url_or_id:
                video_id = url_or_id.split("youtu.be/")[1].split("?")[0]
            # Handle regular youtube.com format with v parameter
            elif "v=" in url_or_id:
                video_id = re.search(r'v=([^&]+)', url_or_id).group(1)
            # Handle youtube.com/embed format
            elif "/embed/" in url_or_id:
                video_id = url_or_id.split("/embed/")[1].split("?")[0]
                
        # Show execution output
        tool_message_print("get_youtube_transcript", [
            ("video_id", video_id),
            ("languages", str(languages)),
            ("combine_all", str(combine_all))
        ], is_output=True)
        
        # Get transcript
        transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)
        
        # Try to find a transcript in one of the specified languages
        transcript = None
        available_languages = []
        
        # First try: Look for manual transcripts in the preferred languages
        for lang in languages:
            try:
                transcript = transcript_list.find_transcript([lang])
                tool_report_print("Found:", f"Manual transcript in language: {lang}")
                break
            except NoTranscriptFound:
                continue
        
        # Second try: If no manual transcript in the preferred languages, try auto-generated ones
        if transcript is None:
            for lang in languages:
                try:
                    for t in transcript_list:
                        available_languages.append(t.language_code)
                        if t.language_code == lang and t.is_generated:
                            transcript = t
                            tool_report_print("Found:", f"Auto-generated transcript in language: {lang}")
                            break
                    if transcript:
                        break
                except Exception:
                    continue
                
        # Third try: If still no transcript, get any available transcript and translate if needed
        if transcript is None:
            try:
                default_transcript = transcript_list.find_transcript([])
                if default_transcript:
                    # If the found transcript is not in the preferred languages, try to translate it
                    if default_transcript.language_code not in languages:
                        tool_report_print("Action:", f"Translating transcript from {default_transcript.language_code} to {languages[0]}")
                        transcript = default_transcript.translate(languages[0])
                    else:
                        transcript = default_transcript
                        
                    tool_report_print("Found:", f"Using transcript in {transcript.language_code}")
            except Exception as e:
                tool_report_print("Warning:", f"Translation attempt failed: {str(e)}")
        
        if transcript is None:
            available_langs_str = ", ".join(available_languages) if available_languages else "none found"
            tool_report_print("Error:", f"No transcript available in languages: {languages}. Available: {available_langs_str}", is_error=True)
            return f"Error: No transcript available in the specified languages: {languages}. Available languages: {available_langs_str}"
        
        # Fetch the actual transcript data
        transcript_data = transcript.fetch()
        
        # Format the transcript according to user preference
        if combine_all:
            # Combine all parts into a single text - fix access method
            # transcript_data is a list of dictionaries, not objects
            try:
                full_text = " ".join([item["text"] for item in transcript_data])
                tool_report_print("Success:", f"YouTube transcript fetched for video {video_id}")
                return full_text
            except (TypeError, KeyError) as e:
                # Fallback if the expected dictionary structure isn't available
                try:
                    # Try to handle as objects with attributes
                    full_text = " ".join([str(item.text) if hasattr(item, 'text') else str(item) for item in transcript_data])
                    tool_report_print("Success:", f"YouTube transcript fetched for video {video_id} (attribute access)")
                    return full_text
                except Exception as attr_err:
                    # Last resort - convert entire response to string
                    tool_report_print("Warning:", f"Using fallback method to extract transcript text: {str(e)}, {str(attr_err)}")
                    return f"Transcript found but could not be fully processed. Raw data: {str(transcript_data)[:1000]}"
        else:
            # Keep timestamp information
            formatted_transcript = []
            try:
                for part in transcript_data:
                    try:
                        # Try dictionary access first
                        timestamp = int(part["start"])
                        text = part["text"]
                    except (TypeError, KeyError):
                        # Fall back to attribute access
                        timestamp = int(part.start if hasattr(part, 'start') else 0)
                        text = str(part.text if hasattr(part, 'text') else part)
                        
                    minutes = timestamp // 60
                    seconds = timestamp % 60
                    time_str = f"{minutes:02d}:{seconds:02d}"
                    formatted_transcript.append(f"[{time_str}] {text}")
                
                tool_report_print("Success:", f"YouTube transcript fetched for video {video_id} with timestamps")
                return "\n".join(formatted_transcript)
            except Exception as e:
                # Last resort fallback
                tool_report_print("Warning:", f"Using fallback method for timestamped transcript: {str(e)}")
                return f"Transcript with timestamps found but could not be fully processed: {str(e)}"
            
    except TranscriptsDisabled:
        tool_report_print("Error:", "Transcripts are disabled for this video.", is_error=True)
        return "Error: Transcripts are disabled for this video."
    except NoTranscriptFound:
        tool_report_print("Error:", "No transcript found for this video.", is_error=True)
        return "Error: No transcript found for this video."
    except ImportError:
        tool_report_print("Error:", "The 'youtube-transcript-api' package is not installed.", is_error=True)
        return "Error: The required package 'youtube-transcript-api' is not installed. Please install it using: pip install youtube-transcript-api"
    except Exception as e:
        tool_report_print("Error:", f"Failed to fetch YouTube transcript: {str(e)}", is_error=True)
        return f"Error: Failed to fetch YouTube transcript: {str(e)}. Make sure the YouTube URL or video ID is correct."
