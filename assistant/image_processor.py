"""
Image processing utilities for assistants
"""

import re
import base64
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
    optimized_images = []
    
    for img_data in images:
        try:
            # Check if this is already a properly formatted image object
            if isinstance(img_data, dict) and img_data.get("type") == "image_url":
                url = img_data.get("image_url", {}).get("url", "")
                
                # If it's a data URL, optimize it
                if url.startswith('data:image/'):
                    # Extract image format and base64 data
                    pattern = r'data:image/([a-zA-Z]+);base64,(.+)'
                    match = re.match(pattern, url)
                    
                    if match:
                        img_format, base64_data = match.groups()
                        
                        # Decode the base64 image
                        img_bytes = base64.b64decode(base64_data)
                        
                        # Open image with PIL and resize/compress
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
                    else:
                        # If regex didn't match, use the original
                        optimized_images.append(img_data)
                else:
                    # If not a data URL, keep as is
                    optimized_images.append(img_data)
            else:
                # If not properly formatted, just pass it through
                optimized_images.append(img_data)
        except Exception as e:
            print(f"{Fore.RED}Error optimizing image: {e}{Style.RESET_ALL}")
            # Still include the original image in case optimization fails
            optimized_images.append(img_data)
    
    return optimized_images
