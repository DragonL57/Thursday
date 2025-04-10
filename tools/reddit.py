"""
Functions for Reddit-related operations.
"""

import praw
import time
import random
import threading
import requests
import re
from typing import List, Dict, Union, Optional
from datetime import datetime
from .formatting import tool_message_print, tool_report_print

# Default limit for number of posts/comments to fetch
DEFAULT_LIMIT = 10
DEFAULT_TIMEOUT = 30  # Updated timeout value based on connection testing
DEFAULT_COMMENT_DEPTH = 2

# List of user agents to rotate through to avoid detection
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/119.0"
]

# Add a custom session class to force API usage
class CustomSession(requests.Session):
    def __init__(self):
        super(CustomSession, self).__init__()
        self.hooks['response'].append(self._fix_redirect)
    
    def _fix_redirect(self, response, **kwargs):
        # Force using api.reddit.com or oauth.reddit.com instead of www.reddit.com
        if response.is_redirect and 'www.reddit.com' in response.headers.get('location', ''):
            new_location = response.headers['location'].replace('www.reddit.com', 'api.reddit.com')
            response.headers['location'] = new_location
            tool_report_print("Info:", f"Redirected request to {new_location}", is_error=False)
        return response
    
    def request(self, method, url, *args, **kwargs):
        # Force using API endpoints for all requests
        if 'www.reddit.com' in url:
            url = url.replace('www.reddit.com', 'api.reddit.com')
            tool_report_print("Info:", f"Routing www.reddit.com request to api.reddit.com", is_error=False)
        
        # Extend timeout for all requests
        if 'timeout' not in kwargs or kwargs['timeout'] is None:
            kwargs['timeout'] = DEFAULT_TIMEOUT
        
        # Add retry logic for failed connections
        max_retries = kwargs.pop('max_retries', 3) if 'max_retries' in kwargs else 3
        retry_count = 0
        
        while retry_count <= max_retries:
            try:
                return super(CustomSession, self).request(method, url, *args, **kwargs)
            except (requests.exceptions.ConnectionError, requests.exceptions.Timeout) as e:
                retry_count += 1
                if retry_count <= max_retries:
                    tool_report_print("Warning:", f"Connection attempt {retry_count} failed. Retrying in {retry_count}s...", is_error=True)
                    time.sleep(retry_count)  # Exponential backoff
                else:
                    raise

# Create a custom requestor class for PRAW that uses our session
class CustomRequestor(praw.reddit.Requestor):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._http = CustomSession()

def _get_reddit_instance(timeout=DEFAULT_TIMEOUT, max_retries=3, use_random_agent=True, read_only=True):
    """
    Get a Reddit API instance using environment variables.
    Returns None if credentials aren't available.
    
    Args:
        timeout: Request timeout in seconds
        max_retries: Number of retries if connection fails
        use_random_agent: Whether to use a random user agent
        read_only: Whether to use read-only mode (no login required)
        
    Returns:
        Reddit instance or None if credentials aren't available
    """
    import os
    from dotenv import load_dotenv
    
    # Load environment variables
    load_dotenv()
    
    # Check for required credentials
    required_vars = ['REDDIT_CLIENT_ID', 'REDDIT_CLIENT_SECRET', 'REDDIT_USER_AGENT']
    for var in required_vars:
        if not os.getenv(var):
            tool_report_print("Error:", f"Missing {var} environment variable", is_error=True)
            return None
    
    # Get base user agent from env or use a default one
    base_user_agent = os.getenv('REDDIT_USER_AGENT')
    
    # Possibly enhance with a random popular browser user agent to avoid detection
    if use_random_agent:
        random_agent = random.choice(USER_AGENTS)
        enhanced_user_agent = f"{base_user_agent} | {random_agent}"
    else:
        enhanced_user_agent = base_user_agent
    
    # Create Reddit instance with enhanced configuration
    retry_count = 0
    while retry_count <= max_retries:
        try:
            config = {
                'client_id': os.getenv('REDDIT_CLIENT_ID'),
                'client_secret': os.getenv('REDDIT_CLIENT_SECRET'),
                'user_agent': enhanced_user_agent,
                'timeout': timeout,
                # These options help with rate limiting
                'check_for_updates': False,
                'check_for_async': False,
                'request_delay': 1.0,  # Add some delay between requests to avoid rate limits
                # Use our custom requestor class instead of the session_cls parameter
                'requestor_class': CustomRequestor
            }
            
            # Only add username/password for authenticated mode
            if not read_only and os.getenv('REDDIT_USERNAME') and os.getenv('REDDIT_PASSWORD'):
                config.update({
                    'username': os.getenv('REDDIT_USERNAME'),
                    'password': os.getenv('REDDIT_PASSWORD')
                })
                
                tool_report_print("Info:", "Using authenticated Reddit session")
            else:
                tool_report_print("Info:", "Using read-only Reddit session")
            
            # Create the Reddit instance
            reddit = praw.Reddit(**config)
            
            # Test the connection with a simple call that doesn't hit API limits
            try:
                # Test connection using API endpoint directly
                public_subreddit = reddit.subreddit('announcements')
                public_subreddit.display_name
                tool_report_print("Info:", "Connection to Reddit API verified (read-only mode)")
                return reddit
            except Exception as e:
                # If connection fails, try a different approach
                if "Connection" in str(e) or "timeout" in str(e).lower():
                    connection_error = str(e)
                    tool_report_print("Warning:", f"Primary connection attempt failed: {str(e)}", is_error=True)
                    
                    try:
                        tool_report_print("Info:", "Trying alternative connection method...")
                        # Use direct API access with requests
                        test_url = "https://api.reddit.com/api/v1/me"
                        headers = {"User-Agent": enhanced_user_agent}
                        response = requests.get(test_url, headers=headers, timeout=timeout/2)
                        
                        if response.status_code == 200 or response.status_code == 401:
                            tool_report_print("Info:", "Alternative connection test succeeded")
                            return reddit
                        else:
                            raise ConnectionError(f"Alternative test failed with status {response.status_code}")
                    except Exception as alt_e:
                        raise ConnectionError(f"Could not connect to Reddit API: {connection_error} | {str(alt_e)}")
                else:
                    raise
            
        except praw.exceptions.RedditAPIException as api_exception:
            retry_count += 1
            error_details = ", ".join([f"{error.error_type}: {error.message}" for error in api_exception.items])
            tool_report_print("Error:", f"Reddit API error: {error_details}", is_error=True)
            
            if retry_count <= max_retries:
                wait_time = 2 ** retry_count  # Exponential backoff
                tool_report_print("Warning:", f"Retrying in {wait_time} seconds (attempt {retry_count}/{max_retries})...", is_error=True)
                time.sleep(wait_time)
            else:
                return None
                
        except praw.exceptions.ClientException as client_error:
            tool_report_print("Error:", f"Reddit client error: {str(client_error)}", is_error=True)
            return None
            
        except (requests.exceptions.RequestException, ConnectionError) as conn_error:
            retry_count += 1
            tool_report_print("Error:", f"Connection error: {str(conn_error)}", is_error=True)
            
            if retry_count <= max_retries:
                wait_time = 2 ** retry_count  # Exponential backoff
                tool_report_print("Warning:", f"Connection attempt {retry_count} failed. Waiting {wait_time}s before retry...", is_error=True)
                time.sleep(wait_time)
            else:
                return None
                
        except praw.exceptions.PRAWException as praw_error:
            retry_count += 1
            tool_report_print("Error:", f"PRAW error: {str(praw_error)}", is_error=True)
            
            if retry_count <= max_retries:
                wait_time = 2 ** retry_count  # Exponential backoff
                tool_report_print("Warning:", f"Reddit connection attempt {retry_count} failed. Waiting {wait_time}s before retry...", is_error=True)
                time.sleep(wait_time)
            else:
                return None
                
        except Exception as e:
            retry_count += 1
            if retry_count <= max_retries:
                wait_time = 2 ** retry_count  # Exponential backoff
                tool_report_print("Warning:", f"Reddit connection attempt {retry_count} failed: {str(e)}. Waiting {wait_time}s before retry...", is_error=True)
                time.sleep(wait_time)
            else:
                tool_report_print("Error:", f"Failed to initialize Reddit instance after {max_retries} retries: {str(e)}", is_error=True)
                return None

def search_reddit_posts(
    query: str,
    subreddit: str = "all",
    sort: str = "relevance",
    time_filter: str = "all",
    limit: int = DEFAULT_LIMIT
) -> List[Dict]:
    """
    Search for Reddit posts matching a query.
    
    Args:
        query: The search query
        subreddit: The subreddit to search in (default: "all" for all subreddits)
        sort: How to sort results ("relevance", "hot", "new", "top", "comments")
        time_filter: Time window ("hour", "day", "week", "month", "year", "all")
        limit: Maximum number of results to return
    
    Returns:
        List of posts, each containing title, author, score, url, etc.
    """
    # Initial tool announcement
    tool_message_print("search_reddit_posts", [
        ("query", f"'{query}'"),
        ("subreddit", subreddit),
        ("sort", sort),
        ("time_filter", time_filter),
        ("limit", str(limit))
    ])
    
    # Show execution output
    tool_message_print("search_reddit_posts", [
        ("query", f"'{query}'"),
        ("subreddit", subreddit),
        ("sort", sort),
        ("time_filter", time_filter),
        ("limit", str(limit))
    ], is_output=True)
    
    # Initialize Reddit API with increasing timeout
    for timeout_multiplier in [1, 1.5, 2.0]:
        try:
            # Initialize with increased timeout on each attempt
            custom_timeout = DEFAULT_TIMEOUT * timeout_multiplier
            reddit = _get_reddit_instance(timeout=custom_timeout)
            if not reddit:
                continue  # Try with increased timeout
            
            # Validate sort parameter
            valid_sorts = ["relevance", "hot", "new", "top", "comments"]
            if sort not in valid_sorts:
                tool_report_print("Warning:", f"Invalid sort '{sort}'. Using 'relevance' instead.", is_error=True)
                sort = "relevance"
            
            # Validate time filter parameter
            valid_times = ["all", "day", "hour", "month", "week", "year"]
            if time_filter not in valid_times:
                tool_report_print("Warning:", f"Invalid time_filter '{time_filter}'. Using 'all' instead.", is_error=True)
                time_filter = "all"
            
            # Access the subreddit with timeout handling
            subreddit_obj = reddit.subreddit(subreddit)
            tool_report_print("Searching:", f"Querying r/{subreddit} for '{query}'")
            
            # Define a thread-safe way to fetch results
            search_results = []
            search_error = [None]
            search_completed = threading.Event()
            
            # Thread function for search with timeout
            def perform_search():
                try:
                    nonlocal search_results
                    result_gen = subreddit_obj.search(
                        query=query,
                        sort=sort,
                        time_filter=time_filter,
                        limit=limit
                    )
                    # Collect results
                    for post in result_gen:
                        # Format the creation time
                        created_utc = datetime.fromtimestamp(post.created_utc).strftime('%Y-%m-%d %H:%M:%S')
                        
                        # Extract the data we want
                        post_data = {
                            "id": post.id,
                            "title": post.title,
                            "author": str(post.author) if post.author else "[deleted]",
                            "subreddit": post.subreddit.display_name,
                            "score": post.score,
                            "upvote_ratio": post.upvote_ratio,
                            "url": f"https://www.reddit.com{post.permalink}",
                            "created_utc": created_utc,
                            "num_comments": post.num_comments,
                            "is_self": post.is_self,
                            "is_video": post.is_video,
                            "over_18": post.over_18,
                            "spoiler": post.spoiler,
                            "link": post.url
                        }
                        
                        # Include text content if it's a self post
                        if post.is_self and hasattr(post, 'selftext'):
                            post_data["selftext"] = post.selftext
                        
                        search_results.append(post_data)
                    search_completed.set()
                except Exception as e:
                    search_error[0] = e
                    search_completed.set()
            
            # Start the search in a separate thread
            search_thread = threading.Thread(target=perform_search)
            search_thread.daemon = True
            search_thread.start()
            
            # Wait for the thread to complete with timeout
            if not search_completed.wait(timeout=custom_timeout):
                raise TimeoutError(f"Reddit search timed out after {custom_timeout} seconds")
            
            # Check if there was an error
            if search_error[0]:
                raise search_error[0]
            
            tool_report_print("Status:", f"Found {len(search_results)} posts matching '{query}' in r/{subreddit}")
            return search_results
            
        except TimeoutError as timeout_err:
            tool_report_print("Warning:", f"Search timed out: {str(timeout_err)}. Retrying with increased timeout.", is_error=True)
            continue
        except Exception as e:
            tool_report_print("Error:", f"Failed to search Reddit: {str(e)}", is_error=True)
            return [{"error": f"Failed to search Reddit: {str(e)}"}]
    
    # If we get here, all attempts failed
    tool_report_print("Error:", "Failed to search Reddit after multiple attempts", is_error=True)
    return [{"error": "Failed to search Reddit after multiple attempts with increasing timeouts"}]

def get_reddit_post(
    post_id: str = None,
    post_url: str = None,
    include_comments: bool = True,
    comment_sort: str = "top",
    comment_limit: int = DEFAULT_LIMIT,
    comment_depth: int = DEFAULT_COMMENT_DEPTH  # New parameter for comment depth
) -> Dict:
    """
    Get a Reddit post and its comments by post ID or URL.
    
    Args:
        post_id: Reddit post ID (either this or post_url must be provided)
        post_url: Full Reddit post URL (alternative to post_id)
        include_comments: Whether to include post comments
        comment_sort: How to sort comments ("top", "best", "new", "controversial", "old", "random")
        comment_limit: Maximum number of comments to return
        comment_depth: How many levels of "load more comments" to process (0=none, None=all)
    
    Returns:
        Dict containing post details and comments if requested
    """
    # Initial tool announcement
    tool_message_print("get_reddit_post", [
        ("post_id", str(post_id) if post_id else "None"),
        ("post_url", post_url if post_url else "None"),
        ("include_comments", str(include_comments)),
        ("comment_sort", comment_sort),
        ("comment_limit", str(comment_limit)),
        ("comment_depth", str(comment_depth))
    ])
    
    # Show execution output
    tool_message_print("get_reddit_post", [
        ("post_id", str(post_id) if post_id else "None"),
        ("post_url", post_url if post_url else "None"),
        ("include_comments", str(include_comments)),
        ("comment_sort", comment_sort),
        ("comment_limit", str(comment_limit)),
        ("comment_depth", str(comment_depth))
    ], is_output=True)
    
    # Validate that we have either post_id or post_url
    if not post_id and not post_url:
        tool_report_print("Error:", "Either post_id or post_url must be provided", is_error=True)
        return {"error": "Either post_id or post_url must be provided"}
    
    # Try main Reddit API first with enhanced retries
    result = _try_get_reddit_post_with_praw(post_id, post_url, include_comments, comment_sort, comment_limit, comment_depth)
    
    # If that fails, try the Pushshift API as a fallback
    if "error" in result:
        tool_report_print("Info:", "Main Reddit API failed. Trying Pushshift API as fallback...", is_error=True)
        try:
            pushshift_result = _try_get_reddit_post_with_pushshift(post_id, post_url)
            if "error" not in pushshift_result:
                return pushshift_result
        except Exception as e:
            tool_report_print("Warning:", f"Pushshift API fallback also failed: {str(e)}", is_error=True)
        
        # Both failed, return the original error
        return result
    
    return result

def _try_get_reddit_post_with_praw(
    post_id: str = None,
    post_url: str = None,
    include_comments: bool = True,
    comment_sort: str = "top",
    comment_limit: int = DEFAULT_LIMIT,
    comment_depth: int = DEFAULT_COMMENT_DEPTH
) -> Dict:
    """
    Internal function to get Reddit post using PRAW with retry logic.
    """
    # Try with different timeout values and retry logic
    max_retries = 3
    retry_count = 0
    
    while retry_count <= max_retries:
        try:
            # Initialize Reddit API with increasing timeout on each retry
            timeout = DEFAULT_TIMEOUT * (retry_count + 1)
            reddit = _get_reddit_instance(timeout=timeout)
            if not reddit:
                return {"error": "Failed to initialize Reddit API. Check if REDDIT_CLIENT_ID, REDDIT_CLIENT_SECRET, and REDDIT_USER_AGENT environment variables are set."}
            
            # Extract post ID from URL if provided
            if post_url and not post_id:
                # Enhanced regex to handle more URL formats
                patterns = [
                    r'reddit\.com/r/[^/]+/comments/([a-zA-Z0-9]+)',  # Standard format
                    r'redd\.it/([a-zA-Z0-9]+)',                      # Short URL
                    r'/comments/([a-zA-Z0-9]+)/',                    # Comments only
                    r'reddit\.com/comments/([a-zA-Z0-9]+)',          # Direct comment link
                    r'reddit\.com/r/[^/]+/s/([a-zA-Z0-9]+)',         # New Reddit UI format
                    r'reddit\.app\.link/([a-zA-Z0-9]+)',             # Mobile app links
                    r'sh\.reddit\.com/r/[^/]+/comments/([a-zA-Z0-9]+)', # Share URLs
                    r'v\.redd\.it/([a-zA-Z0-9]+)',                   # Video URLs
                    r'gallery/([a-zA-Z0-9]+)',                       # Gallery URLs
                    r'www\.reddit\.com/r/[^/]+/comments/([a-zA-Z0-9]+)' # Full URL with www
                ]
                
                for pattern in patterns:
                    match = re.search(pattern, post_url)
                    if match:
                        post_id = match.group(1)
                        tool_report_print("Info:", f"Extracted post ID: {post_id} from URL: {post_url}")
                        break
                        
                if not post_id:
                    # For complex URLs, try the direct URL fetch approach as last resort
                    try:
                        submission = reddit.submission(url=post_url)
                        post_id = submission.id
                        tool_report_print("Info:", f"Extracted post ID: {post_id} from direct URL lookup")
                    except Exception as url_error:
                        tool_report_print("Error:", f"Could not extract post ID from URL: {post_url}", is_error=True)
                        return {"error": f"Could not extract post ID from URL: {post_url}. Error: {str(url_error)}"}
            
            # Validate comment sort parameter
            valid_sorts = ["top", "best", "new", "controversial", "old", "random", "qa"]
            if comment_sort not in valid_sorts:
                tool_report_print("Warning:", f"Invalid comment_sort '{comment_sort}'. Using 'top' instead.", is_error=True)
                comment_sort = "top"
            
            # Get the post
            tool_report_print("Fetching:", f"Getting Reddit post with ID: {post_id}")
            post = reddit.submission(id=post_id)
            
            # Fetch the post attributes immediately to check if it's accessible
            title = post.title  # This will trigger a request and may fail if post doesn't exist
            
            # Format the creation time
            created_utc = datetime.fromtimestamp(post.created_utc).strftime('%Y-%m-%d %H:%M:%S')
            
            # Extract post data with enhanced error handling
            try:
                post_data = {
                    "id": post.id,
                    "title": post.title,
                    "author": str(post.author) if post.author else "[deleted]",
                    "subreddit": post.subreddit.display_name,
                    "score": post.score,
                    "upvote_ratio": post.upvote_ratio,
                    "url": f"https://www.reddit.com{post.permalink}",
                    "created_utc": created_utc,
                    "num_comments": post.num_comments,
                    "is_self": post.is_self,
                    "is_video": post.is_video,
                    "over_18": post.over_18,
                    "spoiler": post.spoiler if hasattr(post, 'spoiler') else False,
                    "link": post.url
                }
                
                # Add additional fields if available
                if hasattr(post, 'poll_data') and post.poll_data:
                    post_data["has_poll"] = True
                    try:
                        poll_options = []
                        for option in post.poll_data.options:
                            poll_options.append({"text": option.text, "votes": option.vote_count})
                        post_data["poll_options"] = poll_options
                    except:
                        post_data["poll_data_available"] = False
                
                # Check if post is a gallery
                if hasattr(post, 'is_gallery') and post.is_gallery:
                    post_data["is_gallery"] = True
                    try:
                        # Try to extract gallery items if available
                        gallery_items = []
                        for item_id, item in post.media_metadata.items():
                            if 'p' in item and item['p']:  # If preview images exist
                                gallery_items.append({
                                    "id": item_id,
                                    "url": item['p'][0]['u'].replace("preview", "i") if item['p'] else None
                                })
                        post_data["gallery_items"] = gallery_items
                    except:
                        post_data["gallery_items_available"] = False
                
            except Exception as attr_error:
                tool_report_print("Warning:", f"Error retrieving some post attributes: {str(attr_error)}. Continuing with partial data.", is_error=True)
                # Create a minimal post data structure with just the essentials
                post_data = {
                    "id": post.id,
                    "title": getattr(post, 'title', '[Title not available]'),
                    "url": f"https://www.reddit.com/comments/{post.id}/",
                    "created_utc": created_utc,
                    "error_details": f"Some post data couldn't be retrieved: {str(attr_error)}"
                }
            
            # Include text content if it's a self post
            if getattr(post, 'is_self', False) and hasattr(post, 'selftext'):
                post_data["selftext"] = post.selftext
            
            # Get comments if requested
            if include_comments:
                tool_report_print("Fetching:", f"Getting up to {comment_limit} comments sorted by {comment_sort}")
                post.comment_sort = comment_sort
                
                # Try to get comments with timeout handling
                try:
                    # Configure the comment loading based on depth parameter
                    if comment_depth == 0:
                        # Skip loading more comments completely
                        tool_report_print("Info:", "Skipping 'load more' comment expansion as comment_depth=0")
                        replace_more_limit = 0
                    elif comment_depth is None:
                        # Load all comments (might hit rate limits)
                        tool_report_print("Info:", "Loading all available comments (comment_depth=None)")
                        replace_more_limit = None
                    else:
                        # Load specified number of 'load more' comments
                        tool_report_print("Info:", f"Loading up to {comment_depth} levels of 'load more' comments")
                        replace_more_limit = comment_depth
                    
                    # Helper function to safely replace more comments
                    def replace_more_safely():
                        try:
                            # Setup event for inter-thread communication
                            done_event = threading.Event()
                            error = [None]  # List to store any errors
                            
                            # Function to run in thread
                            def replace_more_thread():
                                try:
                                    post.comments.replace_more(limit=replace_more_limit)
                                    done_event.set()  # Signal completion
                                except Exception as e:
                                    error[0] = e
                                    done_event.set()  # Signal completion even with error
                            
                            # Start thread to replace more comments
                            thread = threading.Thread(target=replace_more_thread)
                            thread.daemon = True
                            thread.start()
                            
                            # Wait with timeout
                            done = done_event.wait(timeout=timeout)
                            
                            if not done:
                                raise TimeoutError("Comment loading timed out")
                            
                            if error[0]:
                                raise error[0]
                                
                        except Exception as e:
                            if isinstance(e, TimeoutError):
                                raise e
                            raise RuntimeError(f"Error replacing more comments: {str(e)}")
                    
                    # Replace more comments based on the depth setting
                    try:
                        replace_more_safely()
                    except TimeoutError:
                        tool_report_print("Warning:", "Comment loading timed out, proceeding with partial comments", is_error=True)
                    except Exception as replace_error:
                        tool_report_print("Warning:", f"Error expanding comments: {str(replace_error)}", is_error=True)
                    
                    # Process comments, using list() or flattening manually if needed
                    try:
                        if comment_depth == 0:
                            # Only grab top-level comments
                            comment_list = list(post.comments)[:comment_limit]
                        else:
                            # Try to get all comments in a flattened list
                            comment_list = list(post.comments.list())[:comment_limit]
                    except Exception as list_error:
                        # Fall back to just top-level comments
                        tool_report_print("Warning:", f"Error flattening comments: {str(list_error)}. Using top-level comments only.", is_error=True)
                        comment_list = list(post.comments)[:comment_limit]
                    
                    # Process comments
                    comments = []
                    for comment in comment_list:
                        if hasattr(comment, 'body'):  # Ensure it's a regular comment
                            try:
                                comment_data = {
                                    "id": comment.id,
                                    "author": str(comment.author) if comment.author else "[deleted]",
                                    "body": comment.body,
                                    "score": comment.score if hasattr(comment, 'score') else 0,
                                    "created_utc": datetime.fromtimestamp(comment.created_utc).strftime('%Y-%m-%d %H:%M:%S') if hasattr(comment, 'created_utc') else "Unknown"
                                }
                                # Add parent ID if available to show reply structure
                                if hasattr(comment, 'parent_id'):
                                    comment_data["parent_id"] = comment.parent_id
                                
                                # Add link_id to identify which submission this belongs to
                                if hasattr(comment, 'link_id'):
                                    comment_data["link_id"] = comment.link_id
                                
                                # Add depth to show nesting level
                                if hasattr(comment, 'depth'):
                                    comment_data["depth"] = comment.depth
                                
                                comments.append(comment_data)
                            except Exception as comment_error:
                                tool_report_print("Warning:", f"Error processing a comment: {str(comment_error)}", is_error=True)
                    
                    post_data["comments"] = comments
                    tool_report_print("Status:", f"Retrieved post and {len(comments)} comments")
                except Exception as comment_error:
                    tool_report_print("Warning:", f"Failed to get all comments: {str(comment_error)}. Continuing with post only.", is_error=True)
                    post_data["comments"] = []
                    post_data["comment_error"] = str(comment_error)
            else:
                tool_report_print("Status:", "Retrieved post (comments excluded)")
            
            return post_data
            
        except praw.exceptions.RedditAPIException as api_exception:
            retry_count += 1
            error_details = ", ".join([f"{error.error_type}: {error.message}" for error in api_exception.items])
            
            if retry_count <= max_retries:
                wait_time = 2 ** retry_count  # Exponential backoff
                tool_report_print("Warning:", f"Reddit API error: {error_details}. Retrying in {wait_time}s (attempt {retry_count}/{max_retries})...", is_error=True)
                time.sleep(wait_time)
            else:
                tool_report_print("Error:", f"Reddit API error: {error_details}", is_error=True)
                return {"error": f"Reddit API error: {error_details}"}
                
        except praw.exceptions.ClientException as client_error:
            tool_report_print("Error:", f"Reddit client error: {str(client_error)}", is_error=True)
            return {"error": f"Reddit client error: {str(client_error)}"}
            
        except praw.exceptions.PRAWException as praw_error:
            retry_count += 1
            
            if retry_count <= max_retries:
                wait_time = 2 ** retry_count  # Exponential backoff
                tool_report_print("Warning:", f"PRAW error: {str(praw_error)}. Retrying in {wait_time}s (attempt {retry_count}/{max_retries})...", is_error=True)
                time.sleep(wait_time)
            else:
                tool_report_print("Error:", f"PRAW error: {str(praw_error)}", is_error=True)
                return {"error": f"PRAW error: {str(praw_error)}"}
                
        except Exception as e:
            retry_count += 1
            if retry_count <= max_retries:
                wait_time = 2 ** retry_count  # Exponential backoff
                tool_report_print("Warning:", f"Reddit fetch attempt {retry_count} failed: {str(e)}. Waiting {wait_time}s before retry...", is_error=True)
                time.sleep(wait_time)
            else:
                tool_report_print("Error:", f"Failed to get Reddit post after {max_retries} retries: {str(e)}", is_error=True)
                return {"error": f"Failed to get Reddit post: {str(e)}"}
    
    # This should not be reached due to the final error return above, but just in case
    return {"error": "Failed to get Reddit post due to unknown errors"}

def _try_get_reddit_post_with_pushshift(post_id: str = None, post_url: str = None) -> Dict:
    """
    Try to get a Reddit post using the Pushshift API as a fallback.
    
    Args:
        post_id: Reddit post ID
        post_url: Reddit post URL
    
    Returns:
        Dict containing post details (without comments, as Pushshift doesn't support them well)
    """
    import requests
    import time
    from datetime import datetime
    
    # Extract post ID from URL if needed
    if not post_id and post_url:
        import re
        patterns = [
            r'reddit\.com/r/[^/]+/comments/([a-zA-Z0-9]+)',
            r'redd\.it/([a-zA-Z0-9]+)',
            r'/comments/([a-zA-Z0-9]+)/',
            r'reddit\.com/comments/([a-zA-Z0-9]+)'
        ]
        for pattern in patterns:
            match = re.search(pattern, post_url)
            if match:
                post_id = match.group(1)
                break
    
    if not post_id:
        return {"error": "No post ID available for Pushshift API"}
    
    try:
        # Use the new Pushshift API endpoint
        url = f"https://api.pushshift.io/reddit/submission/search?ids={post_id}"
        
        headers = {
            'User-Agent': random.choice(USER_AGENTS)
        }
        
        tool_report_print("Info:", f"Fetching post {post_id} from Pushshift API")
        response = requests.get(url, headers=headers, timeout=DEFAULT_TIMEOUT)
        response.raise_for_status()
        
        data = response.json()
        
        if not data.get('data') or len(data['data']) == 0:
            return {"error": "Post not found in Pushshift API"}
        
        post = data['data'][0]
        
        # Format creation time
        created_utc = datetime.fromtimestamp(post['created_utc']).strftime('%Y-%m-%d %H:%M:%S') if 'created_utc' in post else 'Unknown'
        
        # Create post data dictionary
        post_data = {
            "id": post.get('id', post_id),
            "title": post.get('title', '[Title Not Available]'),
            "author": post.get('author', '[deleted]'),
            "subreddit": post.get('subreddit', 'Unknown'),
            "score": post.get('score', 0),
            "url": f"https://www.reddit.com/r/{post.get('subreddit', 'all')}/comments/{post_id}/",
            "created_utc": created_utc,
            "num_comments": post.get('num_comments', 0),
            "is_self": post.get('is_self', False),
            "selftext": post.get('selftext', ''),
            "note": "This data was retrieved from Pushshift API archives and may not be current"
        }
        
        tool_report_print("Status:", "Successfully retrieved post from Pushshift API archive")
        return post_data
        
    except Exception as e:
        tool_report_print("Warning:", f"Pushshift API request failed: {str(e)}", is_error=True)
        return {"error": f"Pushshift API request failed: {str(e)}"}

def get_subreddit_posts(
    subreddit: str,
    sort: str = "hot",
    time_filter: str = "all",
    limit: int = DEFAULT_LIMIT
) -> List[Dict]:
    """
    Get posts from a specific subreddit.
    
    Args:
        subreddit: The name of the subreddit (without the 'r/')
        sort: How to sort posts ("hot", "new", "top", "rising", "controversial")
        time_filter: Time filter for 'top' and 'controversial' ("hour", "day", "week", "month", "year", "all")
        limit: Maximum number of posts to return
    
    Returns:
        List of posts from the subreddit
    """
    # Initial tool announcement
    tool_message_print("get_subreddit_posts", [
        ("subreddit", subreddit),
        ("sort", sort),
        ("time_filter", time_filter),
        ("limit", str(limit))
    ])
    
    # Show execution output
    tool_message_print("get_subreddit_posts", [
        ("subreddit", subreddit),
        ("sort", sort),
        ("time_filter", time_filter),
        ("limit", str(limit))
    ], is_output=True)
    
    # Initialize Reddit API
    reddit = _get_reddit_instance()
    if not reddit:
        return [{"error": "Failed to initialize Reddit API. Check if REDDIT_CLIENT_ID, REDDIT_CLIENT_SECRET, and REDDIT_USER_AGENT environment variables are set."}]
    
    try:
        # Validate sort parameter
        valid_sorts = ["hot", "new", "top", "rising", "controversial"]
        if sort not in valid_sorts:
            tool_report_print("Warning:", f"Invalid sort '{sort}'. Using 'hot' instead.", is_error=True)
            sort = "hot"
        
        # Validate time filter parameter (only matters for 'top' and 'controversial')
        valid_times = ["all", "day", "hour", "month", "week", "year"]
        if time_filter not in valid_times:
            tool_report_print("Warning:", f"Invalid time_filter '{time_filter}'. Using 'all' instead.", is_error=True)
            time_filter = "all"
        
        # Access the subreddit
        subreddit_obj = reddit.subreddit(subreddit)
        tool_report_print("Fetching:", f"Getting {sort} posts from r/{subreddit}")
        
        # Get the posts based on sort method
        if sort == "hot":
            posts_generator = subreddit_obj.hot(limit=limit)
        elif sort == "new":
            posts_generator = subreddit_obj.new(limit=limit)
        elif sort == "rising":
            posts_generator = subreddit_obj.rising(limit=limit)
        elif sort == "top":
            posts_generator = subreddit_obj.top(time_filter=time_filter, limit=limit)
        elif sort == "controversial":
            posts_generator = subreddit_obj.controversial(time_filter=time_filter, limit=limit)
        
        # Process results
        posts = []
        for post in posts_generator:
            # Format the creation time
            created_utc = datetime.fromtimestamp(post.created_utc).strftime('%Y-%m-%d %H:%M:%S')
            
            # Extract the data we want
            post_data = {
                "id": post.id,
                "title": post.title,
                "author": str(post.author) if post.author else "[deleted]",
                "score": post.score,
                "upvote_ratio": post.upvote_ratio,
                "url": f"https://www.reddit.com{post.permalink}",
                "created_utc": created_utc,
                "num_comments": post.num_comments,
                "is_self": post.is_self,
                "is_video": post.is_video,
                "over_18": post.over_18,
                "spoiler": post.spoiler,
                "link": post.url
            }
            
            # Include text content if it's a self post
            if post.is_self and hasattr(post, 'selftext'):
                post_data["selftext"] = post.selftext
            
            posts.append(post_data)
        
        tool_report_print("Status:", f"Retrieved {len(posts)} posts from r/{subreddit}")
        return posts
    
    except Exception as e:
        tool_report_print("Error:", f"Failed to get subreddit posts: {str(e)}", is_error=True)
        return [{"error": f"Failed to get subreddit posts: {str(e)}"}]
