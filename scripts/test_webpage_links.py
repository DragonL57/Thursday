#!/usr/bin/env python3
"""
Test script for the link extraction feature in the web tools.
This script tests the read_website_content function with link extraction enabled.
"""

import os
import sys
import argparse
from pathlib import Path

# Add the parent directory to the path to import the tools module
parent_dir = str(Path(__file__).resolve().parent.parent)
sys.path.append(parent_dir)

try:
    from tools.web import read_website_content
except ImportError as e:
    print(f"Error: Could not import web tools: {e}")
    sys.exit(1)

def test_link_extraction(url, timeout=10):
    """Test link extraction from a webpage."""
    print(f"Testing link extraction from: {url}")
    print("This may take a few moments...")
    
    result = read_website_content(url, timeout=timeout, extract_mode="markdown", extract_links=True)
    
    # Save the result to a file for inspection
    output_file = os.path.join(parent_dir, "webpage_with_links.md")
    with open(output_file, "w", encoding="utf-8") as f:
        f.write(result)
    
    print(f"\nContent saved to: {output_file}")
    
    # Print a summary
    link_count = result.count("](http")
    print(f"Total links extracted: {link_count}")
    
    # Look for the navigation sections
    nav_section = "### Navigation Links" in result
    content_section = "### Content Links" in result
    external_section = "### External Links" in result
    
    print("\nLink sections found:")
    print(f"  Navigation links: {'Yes' if nav_section else 'No'}")
    print(f"  Content links: {'Yes' if content_section else 'No'}")
    print(f"  External links: {'Yes' if external_section else 'No'}")
    
    return result

def main():
    parser = argparse.ArgumentParser(description="Test webpage link extraction")
    parser.add_argument("url", help="URL of the webpage to test")
    parser.add_argument("--timeout", type=int, default=10, help="Timeout in seconds (default: 10)")
    args = parser.parse_args()
    
    test_link_extraction(args.url, args.timeout)

if __name__ == "__main__":
    main()
