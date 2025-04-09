"""
Image processing utilities for assistants
"""

import re
import base64
import mimetypes
import requests
import tempfile
import os
from io import BytesIO
from PIL import Image
from colorama import Fore, Style

def optimize_images(images):
    """
    Optimize images to reduce size and improve API response time
    
    Args:
        images: List of image data dictionaries with format:
               [{'type': 'image_url', 'image_url': {'url': image_url_or_base64}}]
               
    Returns:
        List of optimized image data dictionaries
    """
    print(f"{Fore.CYAN}Optimizing images, input type: {type(images)}{Style.RESET_ALL}")
    
    # If no images, return empty list
    if not images:
        return []
    
    # Handle direct base64 string (used by Gemini)
    if isinstance(images, str) and images.startswith('data:image/'):
        print(f"{Fore.CYAN}Found direct base64 string for Gemini{Style.RESET_ALL}")
        return images  # For Gemini, just return the raw base64 string
    
    # Handle standard OpenAI/GitHub format
    optimized_images = []
    
    # Convert to list if it's not already
    image_list = images if isinstance(images, list) else [images]
    
    # Process each image
    for img_data in image_list:
        try:
            url = None
            
            # Extract URL from different possible formats
            if isinstance(img_data, dict):
                if "type" in img_data and img_data["type"] == "image_url":
                    if "image_url" in img_data and isinstance(img_data["image_url"], dict):
                        url = img_data["image_url"].get("url", None)
                elif "url" in img_data:
                    url = img_data["url"]
            elif isinstance(img_data, str) and img_data.startswith('data:image/'):
                url = img_data
                
            # If we found a URL, process it
            if url:
                # Extract image format and base64 data
                pattern = r'data:image/([a-zA-Z]+);base64,(.+)'
                match = re.match(pattern, url)
                
                if match:
                    img_format, base64_data = match.groups()
                    
                    # Decode the base64 image
                    try:
                        img_bytes = base64.b64decode(base64_data)
                    except Exception as e:
                        print(f"{Fore.RED}Error decoding base64: {e}{Style.RESET_ALL}")
                        # If we can't decode, use the original
                        optimized_images.append(img_data)
                        continue
                    
                    # Open image with PIL and resize/compress
                    try:
                        img = Image.open(BytesIO(img_bytes))
                        
                        # Set a maximum dimension (width or height)
                        max_dimension = 800
                        if max(img.width, img.height) > max_dimension:
                            # Resize maintaining aspect ratio
                            if img.width > img.height:
                                new_width = max_dimension
                                new_height = int(img.height * (max_dimension / img.width))
                            else:
                                new_height = max_dimension
                                new_width = int(img.width * (max_dimension / img.height))
                            
                            img = img.resize((new_width, new_height), Image.LANCZOS)
                        
                        # Save the optimized image to a BytesIO object
                        buffer = BytesIO()
                        # Make sure we use RGB mode for JPEG (required)
                        if img_format.lower() == 'jpeg' or img_format.lower() == 'jpg':
                            if img.mode != 'RGB':
                                img = img.convert('RGB')
                        
                        img.save(buffer, format=img_format.upper(), quality=75)  # Use higher quality for API accuracy
                        
                        # Convert back to base64
                        optimized_base64 = base64.b64encode(buffer.getvalue()).decode('utf-8')
                        optimized_url = f"data:image/{img_format};base64,{optimized_base64}"
                        
                        # Create optimized image data dictionary
                        optimized_images.append({
                            "type": "image_url",
                            "image_url": {
                                "url": optimized_url
                            }
                        })
                    except Exception as e:
                        print(f"{Fore.RED}Error processing image with PIL: {e}{Style.RESET_ALL}")
                        # If we can't process, use the original
                        optimized_images.append(img_data)
                else:
                    # If regex didn't match, use the original
                    optimized_images.append(img_data)
            else:
                # If format wasn't recognized, just append original
                optimized_images.append(img_data)
        except Exception as e:
            print(f"{Fore.RED}Error optimizing image: {e}{Style.RESET_ALL}")
            # Still include the original image in case optimization fails
            optimized_images.append(img_data)
    
    return optimized_images

def process_image_for_github(image_data):
    """
    Process images specifically for GitHub model compatibility
    
    Args:
        image_data: Image data in various formats (string, dict, or list)
        
    Returns:
        Processed image data compatible with GitHub model input format
    """
    print(f"{Fore.CYAN}Processing image for GitHub model, input type: {type(image_data)}{Style.RESET_ALL}")
    
    # If image_data is None or empty, return None
    if not image_data:
        return None
    
    try:
        # Handle direct base64 string from the UI
        if isinstance(image_data, str) and image_data.startswith('data:image/'):
            return _process_base64_image_for_github(image_data)
        
        # Handle properly formatted dictionary (standard OpenAI format)
        elif isinstance(image_data, dict):
            if image_data.get("type") == "image_url" and "image_url" in image_data:
                url = image_data["image_url"].get("url")
                if url and isinstance(url, str) and url.startswith('data:image/'):
                    # Process the base64 URL inside the standard format
                    processed_base64 = _process_base64_image_for_github(url)
                    if processed_base64:
                        return {
                            "type": "image_url",
                            "image_url": {"url": processed_base64}
                        }
                return image_data  # Return as is if it's already in correct format
            
            return _process_dict_image_for_github(image_data)
            
        # Handle list input - process only first image
        elif isinstance(image_data, list) and len(image_data) > 0:
            print(f"{Fore.CYAN}Processing first image from list of {len(image_data)}{Style.RESET_ALL}")
            first_item = image_data[0]
            
            # If it's already in the right format, just process that one
            if isinstance(first_item, dict) and first_item.get("type") == "image_url":
                return process_image_for_github(first_item)
                
            return process_image_for_github(first_item)
        
        print(f"{Fore.RED}Could not process image data for GitHub - unsupported format{Style.RESET_ALL}")
        return None
        
    except Exception as e:
        print(f"{Fore.RED}Error in process_image_for_github: {e}{Style.RESET_ALL}")
        return None

def process_image_for_gemini(image_data):
    """
    Process images specifically for Gemini model compatibility
    
    Args:
        image_data: Image data in various formats (string, dict, or list)
        
    Returns:
        Processed image data compatible with Gemini model input format
    """
    print(f"{Fore.CYAN}Processing image for Gemini, input type: {type(image_data)}{Style.RESET_ALL}")
    
    # If image_data is None or empty, return None
    if not image_data:
        return None
    
    try:
        # Handle direct base64 string - this is the expected format from the UI for Gemini
        if isinstance(image_data, str) and image_data.startswith('data:image/'):
            print(f"{Fore.CYAN}Image data is already base64 string for Gemini{Style.RESET_ALL}")
            return _process_base64_image_for_gemini(image_data)
        
        # Handle dictionary format (already structured)
        elif isinstance(image_data, dict):
            # If it's in standard OpenAI format, extract the base64 URL
            if image_data.get("type") == "image_url" and "image_url" in image_data:
                url = image_data["image_url"].get("url")
                if url and isinstance(url, str) and url.startswith('data:image/'):
                    return _process_base64_image_for_gemini(url)
            
            return _process_dict_image_for_gemini(image_data)
            
        # Handle list input - process only first image for Gemini
        elif isinstance(image_data, list) and len(image_data) > 0:
            print(f"{Fore.CYAN}Processing first image from list of {len(image_data)}{Style.RESET_ALL}")
            first_item = image_data[0]
            
            # If it's in standard OpenAI format, extract the base64 URL
            if isinstance(first_item, dict) and first_item.get("type") == "image_url":
                url = first_item.get("image_url", {}).get("url")
                if url and isinstance(url, str) and url.startswith('data:image/'):
                    return _process_base64_image_for_gemini(url)
            
            return process_image_for_gemini(first_item)
        
        # If we get here and no formatting was applied, return None with warning
        print(f"{Fore.RED}Could not process image data for Gemini - unsupported format{Style.RESET_ALL}")
        return None
        
    except Exception as e:
        print(f"{Fore.RED}Error in process_image_for_gemini: {e}{Style.RESET_ALL}")
        return None

def _process_base64_image_for_github(image_data_url):
    """
    Process a base64 image data URL for GitHub
    
    GitHub models require image URLs, not base64 content directly.
    Since we can't easily create public URLs, we remove image support
    and return a message about the limitation.
    
    Args:
        image_data_url: Base64 image data URL
    
    Returns:
        None - GitHub models cannot process base64 images directly
    """
    print(f"{Fore.YELLOW}GitHub models do not support base64 encoded images directly{Style.RESET_ALL}")
    
    # Inform the system this is unsupported
    return None

def _process_dict_image_for_github(image_dict):
    """
    Process a dictionary containing image data for GitHub
    
    Args:
        image_dict: Dictionary containing image data
        
    Returns:
        None or URL if a valid public URL is found
    """
    # Check for a valid URL (not base64)
    if 'type' in image_dict and image_dict['type'] == 'image_url' and 'image_url' in image_dict:
        url = image_dict['image_url'].get('url')
        if url and isinstance(url, str) and not url.startswith('data:'):
            # If it's already a public URL, we can use it
            print(f"{Fore.GREEN}Found valid public image URL for GitHub model{Style.RESET_ALL}")
            return image_dict
    
    # For base64 or invalid URLs, return None
    print(f"{Fore.YELLOW}GitHub models require public image URLs, not base64 data{Style.RESET_ALL}")
    return None

def _process_base64_image_for_gemini(image_data_url):
    """
    Process a base64 image data URL for Gemini
    
    Args:
        image_data_url: Base64 image data URL
    
    Returns:
        Processed image in Gemini-compatible format
    """
    print(f"{Fore.CYAN}Processing base64 image for Gemini{Style.RESET_ALL}")
    
    # Extract format and base64 content
    pattern = r'data:image/([a-zA-Z]+);base64,(.+)'
    match = re.match(pattern, image_data_url)
    
    if not match:
        print(f"{Fore.RED}Invalid image data URL format{Style.RESET_ALL}")
        return None
    
    try:
        img_format, base64_content = match.groups()
        
        # Decode and process the image
        img_bytes = base64.b64decode(base64_content)
        img = Image.open(BytesIO(img_bytes))
        
        # Gemini prefers JPEG format
        if img_format.lower() not in ['jpeg', 'jpg', 'png']:
            img_format = 'jpeg'
            if img.mode != 'RGB':
                img = img.convert('RGB')
        
        # Resize if needed - optimize for Gemini's requirements
        max_dim = 1024  # Reasonable dimension for Gemini
        if max(img.width, img.height) > max_dim:
            if img.width > img.height:
                new_width = max_dim
                new_height = int(img.height * (max_dim / img.width))
            else:
                new_height = max_dim
                new_width = int(img.width * (max_dim / img.height))
            
            img = img.resize((new_width, new_height), Image.LANCZOS)
        
        # Re-encode the image
        buffer = BytesIO()
        img.save(buffer, format=img_format.upper(), quality=85)
        
        # Convert back to base64
        processed_base64 = base64.b64encode(buffer.getvalue()).decode('utf-8')
        processed_url = f"data:image/{img_format};base64,{processed_base64}"
        
        # Return in format expected by Gemini
        return {
            "type": "image_url", 
            "image_url": {"url": processed_url}
        }
    except Exception as e:
        print(f"{Fore.RED}Error processing base64 image: {e}{Style.RESET_ALL}")
        # Return simpler format as fallback if processing fails
        return {"type": "image_url", "image_url": {"url": image_data_url}}

def _process_dict_image_for_gemini(image_dict):
    """
    Process an image dictionary for Gemini
    
    Args:
        image_dict: Dictionary containing image data
    
    Returns:
        Processed image in Gemini-compatible format
    """
    # Already in correct format with image_url.url
    if ('type' in image_dict and image_dict['type'] == 'image_url' and 
            'image_url' in image_dict and 'url' in image_dict['image_url']):
        url = image_dict['image_url']['url']
        if isinstance(url, str) and url.startswith('data:image/'):
            # Process the URL for better compatibility
            processed_result = _process_base64_image_for_gemini(url)
            if processed_result:
                return processed_result
    
    # If dict has a url directly
    if 'url' in image_dict and isinstance(image_dict['url'], str):
        if image_dict['url'].startswith('data:image/'):
            return _process_base64_image_for_gemini(image_dict['url'])
    
    print(f"{Fore.YELLOW}Using original dictionary image format{Style.RESET_ALL}")
    return image_dict
