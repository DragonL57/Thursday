"""
Functions for web-related operations.
"""

import webbrowser
import requests
import re  # Add missing import for regular expressions
from bs4 import BeautifulSoup
from duckduckgo_search import DDGS
from duckduckgo_search.exceptions import DuckDuckGoSearchException, RatelimitException, TimeoutException
from typing import List, Union  # Add typing imports

from .formatting import tool_message_print, tool_report_print
import config as conf
from urllib.parse import urlparse

DEFAULT_USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36"

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

def read_website_content(
    url: str, 
    timeout: int = 5, 
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
    tool_message_print("read_website_content", [
        ("url", url), 
        ("timeout", str(timeout)),
        ("extract_mode", extract_mode)
    ])
    
    # Show execution output
    tool_message_print("read_website_content", [
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
    
    # Enhanced function to detect encoding with multiple fallbacks
    def detect_and_decode_content(response_content):
        """
        Detect and decode content with multiple fallback options
        Returns a tuple of (decoded_text, encoding_used)
        """
        # Try to extract encoding from content-type header or meta tags first
        encodings_to_try = []
        
        # Use chardet for precise encoding detection
        try:
            import chardet
            detection = chardet.detect(response_content)
            if detection and detection['confidence'] > 0.7:
                encodings_to_try.append(detection['encoding'])
                tool_report_print("Encoding Detection:", f"Detected encoding: {detection['encoding']} (confidence: {detection['confidence']})")
        except ImportError:
            tool_report_print("Notice:", "chardet library not available, using fallback encoding detection")
            
            # If chardet is not available, try to detect encoding from common patterns
            # HTML5 default encoding is UTF-8
            if b'<meta charset="utf-8"' in response_content or b'<meta charset="UTF-8"' in response_content:
                encodings_to_try.append('utf-8')
                tool_report_print("Encoding Detection:", "Found UTF-8 charset in meta tag")
            
            try:
                # Check for other charset declarations
                charset_match = re.search(b'<meta[^>]*charset=[\'"](.*?)[\'"]', response_content)
                if charset_match:
                    detected_charset = charset_match.group(1).decode('ascii', errors='ignore').lower()
                    if detected_charset and detected_charset not in encodings_to_try:
                        encodings_to_try.append(detected_charset)
                        tool_report_print("Encoding Detection:", f"Found charset in meta tag: {detected_charset}")
            except Exception as e:
                tool_report_print("Warning:", f"Error detecting charset from meta tag: {str(e)}")
        
        # Add common encodings as fallbacks
        common_encodings = ['utf-8', 'utf-16', 'iso-8859-1', 'windows-1252', 'latin1', 'cp1252', 'ascii', 'big5', 'euc-jp', 'euc-kr', 'gb2312', 'shift_jis']
        encodings_to_try.extend([enc for enc in common_encodings if enc not in encodings_to_try])
        
        # Try all potential encodings
        for encoding in encodings_to_try:
            if not encoding:
                continue
                
            try:
                decoded_text = response_content.decode(encoding)
                
                # Perform additional validation to check if the decoding is reasonable
                if not is_valid_decoded_text(decoded_text):
                    tool_report_print("Validation:", f"Content decoded with {encoding} failed validation, trying next encoding")
                    continue
                
                return decoded_text, encoding
            except (UnicodeDecodeError, LookupError) as e:
                tool_report_print("Decode Error:", f"Failed with encoding {encoding}: {str(e)}")
                continue
        
        # Last resort: force decode with utf-8, ignoring errors
        try:
            tool_report_print("Fallback:", "Using forced UTF-8 decoding with error replacement")
            decoded_text = response_content.decode('utf-8', errors='replace')
            
            # We need to check if the result is actually usable
            if is_valid_decoded_text(decoded_text):
                return decoded_text, 'utf-8-replace'
            else:
                # Try latin1 which can decode any byte sequence
                tool_report_print("Fallback:", "UTF-8 decode with replacement resulted in unusable content, trying latin1")
                latin1_text = response_content.decode('latin1', errors='replace')
                return latin1_text, 'latin1-forced' if is_valid_decoded_text(latin1_text) else None
        except Exception as e:
            tool_report_print("Error:", f"Failed all decoding attempts: {str(e)}", is_error=True)
            return None, None
    
    # Add a new function to validate if the decoded text is plausible web content
    def is_valid_decoded_text(text):
        if not text:
            return False
            
        # Check 1: Must have some recognizable HTML or text patterns
        if not any(pattern in text.lower() for pattern in ['<html', '<body', '<div', '<p', '<h1', '<h2', '<a href', 'http']):
            # If it doesn't look like HTML, check if it's at least readable text
            # Count readable ASCII characters
            readable_chars = sum(1 for c in text[:500] if 32 <= ord(c) <= 126)
            if readable_chars / min(len(text[:500]), 500) < 0.5:  # Less than 50% readable
                return False
        
        # Check 2: Should not have too many binary or control characters
        binary_chars = sum(1 for c in text[:1000] if ord(c) < 9 or 14 <= ord(c) <= 31)
        if binary_chars > 10:  # Arbitrary threshold
            return False
        
        # Check 3: Detect if text contains mostly mojibake/replacement characters
        replacement_chars = text[:500].count('�')
        if replacement_chars > len(text[:500]) * 0.1:  # More than 10% are replacement chars
            return False
            
        # Check 4: Text should contain a reasonable amount of common words or characters
        common_patterns = ['the', 'and', 'this', 'for', ' a ', ' to ', ' of ', ' in ', '<div', '<p', 'http']
        pattern_matches = sum(1 for pattern in common_patterns if pattern in text.lower())
        if pattern_matches < 2 and len(text) > 200:  # At least 2 common patterns in longer text
            return False
            
        return True

    # Function to clean content of problematic characters
    def sanitize_content(text):
        """Remove or replace problematic characters in the text"""
        if not text:
            return ""
            
        try:
            # Replace control characters except standard whitespace
            text = re.sub(r'[\x00-\x08\x0B\x0C\x0E-\x1F\x7F-\x9F]', '', text)
            
            # Check for high concentration of unusual characters (possible encoding issue)
            unusual_chars = re.findall(r'[^\x00-\x7F]', text[:500])  # Check first 500 chars
            unusual_ratio = len(unusual_chars) / min(len(text[:500]), 500) if text else 0
            
            if unusual_ratio > 0.3:  # If more than 30% are unusual characters
                tool_report_print("Warning:", f"High concentration of non-ASCII characters detected ({unusual_ratio:.1%}), possible encoding issues", is_error=True)
                # More aggressive cleaning for severe encoding issues
                text = re.sub(r'[^\x20-\x7E\s]', '', text)  # Keep only basic ASCII and whitespace
                
            # Replace consecutive replacement characters with a single one
            text = re.sub(r'�{2,}', '�', text)
            
            # Remove null bytes that might have been introduced
            text = text.replace('\x00', '')
            
            return text
        except Exception as e:
            tool_report_print("Warning:", f"Error in sanitize_content: {str(e)}")
            # Provide a basic fallback if regex fails
            return text.replace('\x00', '').replace('�', '')
    
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
    
    # Add debug output when starting
    print(f"Fetching content from URL: {url}")
    
    try:
        # Parse the URL to check if it's valid
        parsed_url = urlparse(url)
        if not parsed_url.scheme or not parsed_url.netloc:
            raise ValueError(f"Invalid URL format: {url}")
            
        # Add protocol if missing
        if not parsed_url.scheme:
            url = "https://" + url
            tool_report_print("URL Update:", f"Added https:// to URL: {url}")
        
        # Check if this is a PDF file before proceeding
        is_pdf = False
        if url.lower().endswith('.pdf') or '/pdf/' in url.lower():
            is_pdf = True
            tool_report_print("URL Type:", "Detected PDF file")
        
        raw_content = None
        used_archive = False
        encoding_used = None
        
        # Try direct access first
        try:
            # First attempt with normal request
            try:
                response = requests.get(url, headers=headers, timeout=timeout)
                response.raise_for_status()
                
                # Check content type - PDF detection
                if not is_pdf and 'application/pdf' in response.headers.get('Content-Type', '').lower():
                    is_pdf = True
                    tool_report_print("Content Type:", "Detected PDF content from headers")
                
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
                                raw_content = archive_content
                                used_archive = True
                            else:
                                raise inner_e
                        else:
                            raise inner_e
                else:
                    raise e
                    
            if raw_content is None:  # If we didn't get content from archive
                raw_content = response.content
                
                # Try to get encoding from response headers first
                if response.encoding and response.encoding.upper() != 'ISO-8859-1':  # ISO-8859-1 is often the default fallback
                    encoding_used = response.encoding
                    tool_report_print("Encoding:", f"Using encoding from response headers: {encoding_used}")
                
        except requests.exceptions.RequestException as direct_e:
            # For any request exception, try the archive
            archive_content, archive_success = try_wayback_machine(url, direct_e)
            if archive_success and archive_content:
                raw_content = archive_content
                used_archive = True
            else:
                raise direct_e
        
        # After getting content but before parsing, check if we need to handle PDF content
        if is_pdf:
            try:
                import io
                # Try to use PyPDF2 first
                try:
                    from PyPDF2 import PdfReader
                    
                    # Create a PDF reader object from the content
                    pdf_file = io.BytesIO(raw_content)
                    pdf_reader = PdfReader(pdf_file)
                    
                    # Extract text from all pages
                    pdf_text = []
                    for page_num in range(len(pdf_reader.pages)):
                        page = pdf_reader.pages[page_num]
                        pdf_text.append(page.extract_text())
                    
                    # Join all pages with separator
                    content_text = "\n\n--- Page Break ---\n\n".join(pdf_text)
                    tool_report_print("PDF Processing:", f"Successfully extracted text from {len(pdf_reader.pages)} pages using PyPDF2")
                    
                except ImportError:
                    # If PyPDF2 is not available, try pdfplumber
                    try:
                        import pdfplumber
                        
                        # Create a PDF plumber object
                        pdf_file = io.BytesIO(raw_content)
                        with pdfplumber.open(pdf_file) as pdf:
                            pdf_text = []
                            for page in pdf.pages:
                                text = page.extract_text() or ""
                                pdf_text.append(text)
                                
                            content_text = "\n\n--- Page Break ---\n\n".join(pdf_text)
                            tool_report_print("PDF Processing:", f"Successfully extracted text from {len(pdf.pages)} pages using pdfplumber")
                    except ImportError:
                        # If neither is available, inform the user
                        return "This URL points to a PDF file, but PDF text extraction libraries (PyPDF2 or pdfplumber) aren't available. Please install one of these libraries or use a different URL."
                    
            except Exception as pdf_error:
                tool_report_print("PDF Processing Error:", str(pdf_error), is_error=True)
                return f"Error extracting text from PDF: {str(pdf_error)}. The URL points to a PDF file, but text extraction failed."
        else:
            # Detect and decode the content with proper encoding
            decoded_content, detected_encoding = detect_and_decode_content(raw_content)
            if decoded_content is None:
                tool_report_print("Error:", "Failed to decode content with any encoding", is_error=True)
                return "Error: The webpage content couldn't be properly decoded. This might be due to an unsupported character encoding or the content being binary data (like images or PDFs). Try a different URL or a text-based webpage."
            
            encoding_used = detected_encoding
            tool_report_print("Encoding:", f"Content decoded using {encoding_used} encoding")
            
            # Check for encoding issues or binary content
            try:
                if '�' in decoded_content[:500] or any(c in decoded_content[:1000] for c in ['\uFFFD', '\x00']):
                    tool_report_print("Warning:", "Replacement characters detected, possible encoding issues", is_error=True)
            except Exception as e:
                tool_report_print("Warning:", f"Error checking for encoding issues: {str(e)}")
            
            # Clean content of problematic characters
            decoded_content = sanitize_content(decoded_content)
            
            # Parse the HTML
            try:
                soup = BeautifulSoup(decoded_content, 'lxml')
            except Exception as parse_error:
                # If parsing fails with the detected encoding, try a more aggressive approach
                tool_report_print("Error:", f"Failed to parse HTML: {str(parse_error)}", is_error=True)
                tool_report_print("Action:", "Trying more aggressive content sanitization")
                
                # Force decode with latin1 which should always work
                decoded_content = raw_content.decode('latin1', errors='ignore')
                decoded_content = sanitize_content(decoded_content)
                
                try:
                    soup = BeautifulSoup(decoded_content, 'lxml')
                except Exception as second_parse_error:
                    return f"Error: Could not parse the webpage content. The page might have malformed HTML or use a non-standard encoding. Error details: {str(second_parse_error)}"
        
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
            if len(body_text) < 200:
                tool_report_print("Warning:", "Retrieved content is very short (<200 chars), likely not the full page", is_error=True)
                if "captcha" in body_text.lower():
                    tool_report_print("Warning:", "Website may be showing a CAPTCHA page or anti-bot measures", is_error=True)
                    return "Error: This website appears to be protected against automated access. It might be showing a CAPTCHA or using anti-bot measures."
                else:
                    tool_report_print("Warning:", "Retrieved content is minimal, might be due to access restrictions or JavaScript-heavy page", is_error=True)
            
            # Process based on extraction mode
            if (extract_mode == "markdown"):
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
                        
                content_text = '\n\n'.join(result)
            else:
                # Default text mode - with better formatting
                # Remove excessive whitespace and newlines
                for br in soup.find_all('br'):
                    br.replace_with('\n')
                    
                content_text = soup.get_text(separator='\n\n', strip=True)
                
                # Clean up the content: remove multiple newlines and spaces
                import re
                content_text = re.sub(r'\n{3,}', '\n\n', content_text)  # Replace 3+ newlines with 2
                content_text = re.sub(r' {2,}', ' ', content_text)      # Replace 2+ spaces with 1
            
            # Final check for encoding issues
            try:
                # Try to encode and then decode the content back - this can catch encoding issues
                test_encode = content_text.encode('utf-8')
                test_decode = test_encode.decode('utf-8')
                
                if test_decode != content_text:
                    tool_report_print("Warning:", "Character encoding inconsistency detected, applying additional sanitization", is_error=True)
                    content_text = sanitize_content(content_text)
            except Exception as encoding_error:
                tool_report_print("Warning:", f"Final encoding check failed: {str(encoding_error)}", is_error=True)
                content_text = sanitize_content(content_text)
        
        # Truncate if content is very long
        if len(content_text) > 50000:
            content_text = content_text[:50000] + "\n\n[Content truncated due to length...]"
            tool_report_print("Notice:", "Content was truncated because it exceeded 50,000 characters")
            
        # Check if the final content is empty or appears to be gibberish
        if not content_text or len(content_text.strip()) < 10:  # At least 10 chars to be considered non-empty
            tool_report_print("Error:", "Extraction resulted in empty content", is_error=True)
            return "Could not extract meaningful content from this website. The page might be protected, empty, or using client-side rendering that requires a browser."
            
        # Check for gibberish content (high concentration of rare characters)
        import re
        
        try:
            # Count non-ASCII characters or unusual sequences in the first part of content
            gibberish_chars = len(re.findall(r'[^\x20-\x7E\s.,;:!?\'"()[\]{}]', content_text[:1000]))
            gibberish_ratio = gibberish_chars / min(len(content_text[:1000]), 1000) if content_text else 0
            
            replacement_ratio = content_text[:1000].count('�') / min(len(content_text[:1000]), 1000) if content_text else 0
            
            if gibberish_ratio > 0.3 or replacement_ratio > 0.1:  # If more than 30% are unusual characters or 10% are replacement chars
                tool_report_print("Error:", f"Content appears to be gibberish or incorrectly decoded ({gibberish_ratio:.1%} unusual characters, {replacement_ratio:.1%} replacement characters)", is_error=True)
                
                # Provide a clearer error message with examples of the problematic content
                sample_text = content_text[:200] + ("..." if len(content_text) > 200 else "")
                return f"""Error: The webpage content appears to be incorrectly encoded or contains mostly non-readable characters. 

This might be due to:
1. The website using a non-standard character encoding
2. Anti-scraping measures on the website
3. The content requiring JavaScript to render
4. The content being binary data (images, PDFs) rather than text

Sample of problematic content:
---
{sample_text}
---

Try a different URL or a site with simpler content structure."""
        except Exception as e:
            tool_report_print("Warning:", f"Error checking for gibberish content: {str(e)}")
        
        tool_report_print("Status:", f"Webpage content fetched successfully using {encoding_used} encoding")
        return content_text
        
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
            
        # More detailed debugging info
        tool_report_print("Full error details:", str(e), is_error=True)
        return error_message
    except Exception as e:
        tool_report_print("Error processing webpage:", str(e), is_error=True)
        return f"Error processing webpage content: {e}"

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
            import re
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
