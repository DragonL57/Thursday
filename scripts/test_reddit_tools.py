#!/usr/bin/env python3
# filepath: /home/long/personal-gem/scripts/test_reddit_tools.py
"""
Test script for Reddit tools in the personal-gem project.
This script tests all Reddit tools with various parameters and provides detailed output.

Usage:
    python test_reddit_tools.py --all                  # Test all functions
    python test_reddit_tools.py --search "python"      # Test search with custom query
    python test_reddit_tools.py --post "140zie6"       # Test get post with custom ID
    python test_reddit_tools.py --subreddit "Python"   # Test subreddit posts with custom subreddit
    python test_reddit_tools.py --save results.json    # Save results to a file
"""

import sys
import os
import json
import argparse
import time
from typing import Dict, List, Any, Optional
import traceback
import importlib.util

# Check for required dependencies before proceeding
required_packages = ['bs4', 'praw', 'requests', 'traceback']
missing_packages = []

for package in required_packages:
    if importlib.util.find_spec(package) is None:
        missing_packages.append(package)

if missing_packages:
    print(f"Error: Missing required dependencies: {', '.join(missing_packages)}")
    print("Please install the missing dependencies using:")
    print(f"pip install {' '.join(missing_packages)}")
    print("or")
    print("pip install -r requirements.txt")
    sys.exit(1)

# Add the parent directory to the path to import the tools module
parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(parent_dir)

# Try importing the Reddit tools
try:
    from tools.reddit import search_reddit_posts, get_reddit_post, get_subreddit_posts
except ImportError as e:
    print(f"Error: Could not import Reddit tools: {e}")
    print("Make sure you're running this script from the correct directory")
    print(f"Current directory: {os.getcwd()}")
    print(f"Path: {sys.path}")
    sys.exit(1)

# Global variables
ALL_RESULTS = {}
COLORS = {
    'HEADER': '\033[95m',
    'BLUE': '\033[94m',
    'CYAN': '\033[96m',
    'GREEN': '\033[92m',
    'YELLOW': '\033[93m',
    'RED': '\033[91m',
    'ENDC': '\033[0m',
    'BOLD': '\033[1m',
    'UNDERLINE': '\033[4m'
}

def colorize(text, color):
    """Add color to terminal output."""
    return f"{COLORS.get(color, '')}{text}{COLORS['ENDC']}"

def print_header(text):
    """Print a formatted header."""
    print(f"\n{colorize('=' * 80, 'BOLD')}")
    print(f"{colorize(text, 'BOLD')}")
    print(f"{colorize('=' * 80, 'BOLD')}")

def pretty_print_results(results, title=None):
    """Print results in a readable format."""
    if title:
        print(f"\n{colorize(title, 'HEADER')}")
    
    if isinstance(results, list):
        print(f"Total results: {len(results)}")
        for i, result in enumerate(results[:3], 1):
            print(f"\n{colorize(f'Result {i}:', 'BOLD')}")
            pretty_print_dict(result)
        if len(results) > 3:
            print(f"\n... and {len(results) - 3} more results")
    else:
        pretty_print_dict(results)
    
    return results

def pretty_print_dict(data, indent=0):
    """Print a dictionary in a readable format."""
    if not isinstance(data, dict):
        print(f"{' ' * indent}{data}")
        return
        
    for key, value in data.items():
        if key == "comments" and isinstance(value, list):
            print(f"{' ' * indent}{colorize(key, 'CYAN')}:")
            print(f"{' ' * indent}  Total comments: {len(value)}")
            # Print first 2 comments
            for i, comment in enumerate(value[:2]):
                print(f"{' ' * indent}  {colorize(f'Comment {i+1}:', 'BOLD')}")
                pretty_print_dict(comment, indent + 4)
            if len(value) > 2:
                print(f"{' ' * indent}  ... and {len(value) - 2} more comments")
        elif key == "selftext" and isinstance(value, str) and len(value) > 100:
            print(f"{' ' * indent}{colorize(key, 'CYAN')}: {value[:100]}... (truncated)")
        elif isinstance(value, dict):
            print(f"{' ' * indent}{colorize(key, 'CYAN')}:")
            pretty_print_dict(value, indent + 2)
        elif isinstance(value, list) and value and isinstance(value[0], dict):
            print(f"{' ' * indent}{colorize(key, 'CYAN')}:")
            for i, item in enumerate(value[:2]):
                print(f"{' ' * indent}  Item {i+1}:")
                pretty_print_dict(item, indent + 4)
            if len(value) > 2:
                print(f"{' ' * indent}  ... and {len(value) - 2} more items")
        else:
            if isinstance(value, str) and len(value) > 100:
                print(f"{' ' * indent}{colorize(key, 'CYAN')}: {value[:100]}... (truncated)")
            else:
                print(f"{' ' * indent}{colorize(key, 'CYAN')}: {value}")

def test_search_reddit_posts(query="python programming", subreddit="all", sort="relevance", time_filter="all", limit=5):
    """Test the search_reddit_posts function."""
    print_header(f"Testing search_reddit_posts with query='{query}', subreddit='{subreddit}'")
    
    try:
        # First check API connectivity
        print(colorize("Checking API connectivity before test...", "BLUE"))
        for domain in ["api.reddit.com", "oauth.reddit.com", "www.reddit.com"]:
            try:
                print(f"Testing connection to https://{domain}/...")
                response = requests.get(f"https://{domain}/", 
                                      headers={"User-Agent": "personal-gem:test_script:v1.0"},
                                      timeout=10)
                print(colorize(f"  ✓ {domain}: {response.status_code} ({response.elapsed.total_seconds():.2f}s)", "GREEN"))
            except Exception as e:
                print(colorize(f"  ✗ {domain}: {str(e)}", "RED"))
        
        print(f"Parameters: sort='{sort}', time_filter='{time_filter}', limit={limit}")
        start_time = time.time()
        results = search_reddit_posts(query=query, subreddit=subreddit, sort=sort, time_filter=time_filter, limit=limit)
        elapsed_time = time.time() - start_time
        
        title = f"Search results for '{query}' in r/{subreddit} (took {elapsed_time:.2f}s)"
        pretty_print_results(results, title)
        
        # Check for errors in the response
        if isinstance(results, list) and results and "error" in results[0]:
            print(colorize(f"Error in response: {results[0]['error']}", "RED"))
        
        ALL_RESULTS['search_reddit_posts'] = results
        return results
    except Exception as e:
        print(colorize(f"Error testing search_reddit_posts: {e}", "RED"))
        traceback.print_exc()
        return {"error": str(e)}

def test_get_reddit_post(post_id=None, post_url=None, include_comments=True, comment_sort="top", comment_limit=10, comment_depth=2):
    """Test the get_reddit_post function."""
    
    # If neither post_id nor post_url is provided, use a default
    if not post_id and not post_url:
        post_id = "140zie6"  # A sample post ID from r/Python
        
    identifier = post_id if post_id else post_url
    print_header(f"Testing get_reddit_post with identifier='{identifier}'")
    
    try:
        print(f"Parameters: include_comments={include_comments}, comment_sort='{comment_sort}', " +
              f"comment_limit={comment_limit}, comment_depth={comment_depth}")
        
        start_time = time.time()
        results = get_reddit_post(
            post_id=post_id, 
            post_url=post_url, 
            include_comments=include_comments, 
            comment_sort=comment_sort, 
            comment_limit=comment_limit, 
            comment_depth=comment_depth
        )
        elapsed_time = time.time() - start_time
        
        title = f"Post details for {identifier} (took {elapsed_time:.2f}s)"
        pretty_print_results(results, title)
        
        # Check for errors in the response
        if isinstance(results, dict) and "error" in results:
            print(colorize(f"Error in response: {results['error']}", "RED"))
        
        ALL_RESULTS['get_reddit_post'] = results
        return results
    except Exception as e:
        print(colorize(f"Error testing get_reddit_post: {e}", "RED"))
        traceback.print_exc()
        return {"error": str(e)}

def test_get_subreddit_posts(subreddit="Python", sort="hot", time_filter="all", limit=5):
    """Test the get_subreddit_posts function."""
    print_header(f"Testing get_subreddit_posts with subreddit='{subreddit}', sort='{sort}'")
    
    try:
        print(f"Parameters: time_filter='{time_filter}', limit={limit}")
        start_time = time.time()
        results = get_subreddit_posts(subreddit=subreddit, sort=sort, time_filter=time_filter, limit=limit)
        elapsed_time = time.time() - start_time
        
        title = f"{sort.capitalize()} posts from r/{subreddit} (took {elapsed_time:.2f}s)"
        pretty_print_results(results, title)
        
        # Check for errors in the response
        if isinstance(results, list) and results and "error" in results[0]:
            print(colorize(f"Error in response: {results[0]['error']}", "RED"))
        
        ALL_RESULTS['get_subreddit_posts'] = results
        return results
    except Exception as e:
        print(colorize(f"Error testing get_subreddit_posts: {e}", "RED"))
        traceback.print_exc()
        return {"error": str(e)}

def test_error_handling():
    """Test error handling in Reddit tools."""
    print_header("Testing Error Handling")
    
    # Test 1: Invalid subreddit
    print(f"\n{colorize('Test 1: Invalid subreddit', 'BOLD')}")
    try:
        results = get_subreddit_posts(subreddit="this_subreddit_does_not_exist_12345")
        if isinstance(results, list) and results and "error" in results[0]:
            print(colorize(f"✅ Expected error received: {results[0]['error']}", "GREEN"))
        else:
            print(colorize("❌ Expected an error, but got results.", "RED"))
            pretty_print_results(results)
    except Exception as e:
        print(colorize(f"Exception raised: {e}", "RED"))
        traceback.print_exc()
    
    # Test 2: Invalid post ID
    print(f"\n{colorize('Test 2: Invalid post ID', 'BOLD')}")
    try:
        results = get_reddit_post(post_id="this_is_not_a_valid_post_id_12345")
        if isinstance(results, dict) and "error" in results:
            print(colorize(f"✅ Expected error received: {results['error']}", "GREEN"))
        else:
            print(colorize("❌ Expected an error, but got results.", "RED"))
            pretty_print_results(results)
    except Exception as e:
        print(colorize(f"Exception raised: {e}", "RED"))
        traceback.print_exc()
    
    # Test 3: Invalid sort parameter
    print(f"\n{colorize('Test 3: Invalid sort parameter with auto-correction', 'BOLD')}")
    try:
        results = get_subreddit_posts(subreddit="Python", sort="invalid_sort")
        # This should not fail due to graceful handling, but use a default sort
        pretty_print_results(results)
        print(colorize("✅ Function handled invalid sort parameter gracefully", "GREEN"))
    except Exception as e:
        print(colorize(f"❌ Exception raised: {e}", "RED"))
        traceback.print_exc()

def save_results_to_file(filename="reddit_test_results.json"):
    """Save all test results to a JSON file."""
    try:
        with open(filename, 'w') as f:
            json.dump(ALL_RESULTS, f, indent=2)
        print(colorize(f"\nResults saved to {filename}", "GREEN"))
    except Exception as e:
        print(colorize(f"Error saving results to file: {e}", "RED"))
        traceback.print_exc()

def main():
    parser = argparse.ArgumentParser(description='Test Reddit tools')
    parser.add_argument('--search', nargs='?', const="python programming", 
                      help='Test search_reddit_posts with optional query')
    parser.add_argument('--post', nargs='?', const=None, 
                      help='Test get_reddit_post with optional post ID')
    parser.add_argument('--post-url', 
                      help='Test get_reddit_post with post URL')
    parser.add_argument('--subreddit', nargs='?', const="Python", 
                      help='Test get_subreddit_posts with optional subreddit name')
    parser.add_argument('--error', action='store_true', 
                      help='Test error handling')
    parser.add_argument('--all', action='store_true', 
                      help='Test all functions')
    parser.add_argument('--save', nargs='?', const="reddit_test_results.json", 
                      help='Save results to a file')
    
    # Additional parameters
    parser.add_argument('--sort', default="relevance", 
                      help='Sort parameter for searches/listings')
    parser.add_argument('--time', default="all", 
                      help='Time filter (day, week, month, year, all)')
    parser.add_argument('--limit', type=int, default=5, 
                      help='Limit number of results')
    parser.add_argument('--comment-sort', default="top", 
                      help='Comment sort for post details (top, best, new, etc)')
    parser.add_argument('--comment-limit', type=int, default=10, 
                      help='Limit number of comments')
    parser.add_argument('--comment-depth', type=int, default=2, 
                      help='Comment depth (0=top level only, None=all)')
    parser.add_argument('--no-comments', action='store_true', 
                      help='Exclude comments when fetching posts')
    
    args = parser.parse_args()
    
    # Initial welcome message
    print_header("Reddit Tools Test Suite")
    print(f"Running from: {os.path.abspath(__file__)}")
    print(f"Current time: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    
    # If no test args specified, test all
    run_all = not (args.search or args.post or args.post_url or args.subreddit or args.error) or args.all
    
    # Run tests based on arguments
    if run_all or args.search:
        query = args.search if isinstance(args.search, str) else "python programming"
        test_search_reddit_posts(
            query=query, 
            sort=args.sort, 
            time_filter=args.time, 
            limit=args.limit
        )
    
    if run_all or args.post or args.post_url:
        test_get_reddit_post(
            post_id=args.post, 
            post_url=args.post_url,
            include_comments=not args.no_comments,
            comment_sort=args.comment_sort,
            comment_limit=args.comment_limit,
            comment_depth=args.comment_depth
        )
    
    if run_all or args.subreddit:
        subreddit = args.subreddit if isinstance(args.subreddit, str) else "Python"
        test_get_subreddit_posts(
            subreddit=subreddit, 
            sort=args.sort, 
            time_filter=args.time, 
            limit=args.limit
        )
    
    if run_all or args.error:
        test_error_handling()
    
    # Save results if requested
    if args.save:
        filename = args.save if isinstance(args.save, str) else "reddit_test_results.json"
        save_results_to_file(filename)

    print_header("Test Summary")
    print(f"Tests completed at: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Total result sets: {len(ALL_RESULTS)}")

if __name__ == "__main__":
    main()
