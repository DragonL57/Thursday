"""
API client for interaction with LLM APIs
"""

import json
import time
import random
import requests
from requests.exceptions import RequestException
from colorama import Fore, Style

class ApiClient:
    """
    Handles API communication with retry logic and error handling
    """
    
    def __init__(self, 
                 base_url=None, 
                 model=None, 
                 retry_count=3, 
                 base_delay=1.0, 
                 max_delay=10.0,
                 request_timeout=60):
        """
        Initialize the API client with configuration.
        
        Args:
            base_url: The base URL for the API - not used with LiteLLM
            model: The model to use for completions
            retry_count: Number of times to retry failed requests
            base_delay: Base delay between retries (will be increased exponentially)
            max_delay: Maximum delay between retries
            request_timeout: Request timeout in seconds
        """
        self.model = model
        self.retry_count = retry_count
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.request_timeout = request_timeout
    
    def get_completion(self, messages, tools=None, stream=False):
        """
        This method is deprecated as we now use litellm directly.
        It's kept for backward compatibility.
        """
        import litellm
        import config as conf
        
        try:
            # Process messages for the appropriate model
            processed_messages = preprocess_messages_for_litellm(messages, self.model)
            
            # Create payload for litellm
            payload = {
                "model": self.model,
                "messages": processed_messages,
                "temperature": conf.TEMPERATURE,
                "top_p": conf.TOP_P,
                "max_tokens": conf.MAX_TOKENS,
                "seed": conf.SEED,
            }
            
            # Add stream parameter if streaming is requested
            if stream:
                payload["stream"] = True
            
            # Add tools if provided
            if tools:
                payload["tools"] = tools
            
            # Use litellm directly
            response = litellm.completion(**payload)
            return response
            
        except Exception as e:
            print(f"API request failed: {e}")
            raise ValueError(f"Error communicating with the API: {str(e)}")

def preprocess_messages_for_litellm(messages, model_name):
    """
    Preprocess messages to ensure proper format for LiteLLM, particularly for Gemini models
    that handle images differently.
    
    Args:
        messages: List of message objects
        model_name: Name of the model being used
    
    Returns:
        Processed list of messages
    """
    # Only do special formatting for Gemini models
    if not model_name or not isinstance(model_name, str) or not model_name.startswith('gemini/'):
        return messages
    
    processed_messages = []
    
    for message in messages:
        # Skip messages without content
        if not message or 'content' not in message:
            processed_messages.append(message)
            continue
            
        # Handle different types of content structures
        content = message['content']
        
        # If content is a string, check for image URLs or base64 data
        if isinstance(content, str):
            # Simple text message - no change needed
            processed_messages.append(message)
            continue
            
        # If content is already a list (multimodal), ensure proper format for Gemini
        elif isinstance(content, list):
            new_content = []
            for item in content:
                if isinstance(item, dict):
                    # Handle image_url items
                    if item.get('type') == 'image_url':
                        # Ensure proper format for Gemini
                        if 'image_url' in item and isinstance(item['image_url'], dict) and 'url' in item['image_url']:
                            # Already in correct format
                            new_content.append(item)
                        elif 'url' in item:
                            # Convert to proper format
                            new_content.append({
                                'type': 'image_url',
                                'image_url': {'url': item['url']}
                            })
                    # Handle text items
                    elif item.get('type') == 'text':
                        new_content.append(item)
                    # Handle other types by passing through
                    else:
                        new_content.append(item)
                # Handle string content items (convert to text type)
                elif isinstance(item, str):
                    new_content.append({
                        'type': 'text',
                        'text': item
                    })
            
            # Create a new message with properly formatted content
            new_message = message.copy()
            new_message['content'] = new_content
            processed_messages.append(new_message)
        else:
            # Pass through messages with unknown content format
            processed_messages.append(message)
    
    print(f"Processed {len(processed_messages)} messages for Gemini model")
    return processed_messages
