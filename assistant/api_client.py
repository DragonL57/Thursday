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
    
    def __init__(self, base_url="https://text.pollinations.ai/openai", 
                model="openai", retry_count=3, base_delay=1.0, max_delay=10.0,
                request_timeout=60):
        """
        Initialize the API client with configuration.
        
        Args:
            base_url: The base URL for the API
            model: The model to use for completions
            retry_count: Number of times to retry failed requests
            base_delay: Base delay between retries (will be increased exponentially)
            max_delay: Maximum delay between retries
            request_timeout: Request timeout in seconds
        """
        self.base_url = base_url
        self.model = model
        self.retry_count = retry_count
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.request_timeout = request_timeout
    
    def get_completion(self, messages, tools=None, stream=False):
        """
        Get a completion from the API.
        
        Args:
            messages: Message history to send to the API
            tools: Optional list of tool definitions
            stream: Whether to request a streaming response
            
        Returns:
            For regular requests: Response JSON
            For streaming requests: The requests.Response object
        """
        return self._make_api_request(messages, tools, stream)
    
    def _make_api_request(self, messages, tools=None, stream=False):
        """
        Implementation of API request to Pollinations AI using the openai-large model.
        
        Args:
            messages: Message history to send to the API
            tools: Optional list of tool definitions
            stream: Whether to request a streaming response
            
        Returns:
            For regular requests: Response JSON
            For streaming requests: The requests.Response object
        """
        import config as conf
        
        # Process messages to ensure proper format for the API
        processed_messages = preprocess_messages_for_pollinations(messages)
        
        # Use the model name directly - do NOT modify openai-large
        model_name = self.model
        
        payload = {
            "model": model_name,  # Use original model name without conversion
            "messages": processed_messages,
            "temperature": conf.TEMPERATURE,
            "top_p": conf.TOP_P,
            "max_tokens": conf.MAX_TOKENS,
            "seed": conf.SEED,
        }
        
        # Add stream parameter if streaming is requested
        if stream:
            payload["stream"] = True
        
        # Add tools if provided and correctly format them
        if tools:
            # Ensure tools are properly formatted for Pollinations
            # Pollinations expects a specific structure for tools
            formatted_tools = []
            for tool in tools:
                # Skip any tool that's not a properly formatted dictionary
                if not isinstance(tool, dict):
                    continue
                    
                # Make sure the tool has the required structure
                if "type" not in tool or tool.get("type") != "function" or "function" not in tool:
                    continue
                    
                # Add properly formatted tool
                formatted_tools.append(tool)
                
            if formatted_tools:
                payload["tools"] = formatted_tools
        
        # Remove None values from payload
        payload = {k: v for k, v in payload.items() if v is not None}
        
        # Print the request information for debugging (without full message content)
        debug_payload = payload.copy()
        if "messages" in debug_payload:
            debug_payload["messages"] = f"[{len(debug_payload['messages'])} messages]"
        if "tools" in debug_payload:
            debug_payload["tools"] = f"[{len(debug_payload['tools'])} tools]"
        print(f"Sending request to {self.base_url} with payload: {debug_payload}")
        
        # Make the API request with retries
        retry_count = self.retry_count
        current_delay = self.base_delay
        
        while True:
            try:
                headers = {"Content-Type": "application/json"}
                
                response = requests.post(
                    self.base_url,
                    headers=headers,
                    json=payload,
                    timeout=self.request_timeout,
                    stream=stream
                )
                
                # Raise an exception for HTTP errors
                response.raise_for_status()
                
                # If streaming, return the raw response
                if stream:
                    return response
                
                # Otherwise, parse the response JSON
                try:
                    return response.json()
                except json.JSONDecodeError:
                    raise ValueError(f"Invalid JSON response: {response.text[:500]}...")
                
            except (requests.RequestException, ValueError) as e:
                retry_count -= 1
                
                # If we have retries left, wait and try again
                if retry_count > 0:
                    print(f"API request failed: {e}. Retrying in {current_delay} seconds...")
                    time.sleep(current_delay)
                    current_delay = min(current_delay * 2, self.max_delay)
                else:
                    # No more retries, raise the exception
                    print(f"API request failed after multiple retries: {e}")
                    
                    # Include more detailed error information
                    error_details = str(e)
                    if hasattr(e, 'response') and hasattr(e.response, 'text'):
                        try:
                            error_json = e.response.json()
                            error_details += f" - API Error: {error_json}"
                        except:
                            error_details += f" - Response: {e.response.text[:500]}"
                    
                    raise ValueError(f"Error communicating with the API: {error_details}")

def preprocess_messages_for_pollinations(messages):
    """
    Preprocess messages for the Pollinations API to ensure they're JSON serializable.
    
    Args:
        messages: List of message objects
        
    Returns:
        List of properly formatted message dictionaries
    """
    processed_messages = []
    
    for message in messages:
        # Handle both dictionary-style messages and object-style messages
        if isinstance(message, dict):
            # For dictionary messages, ensure all fields are JSON serializable
            msg_copy = message.copy()
            
            # Special handling for content field which might be a complex object
            if 'content' in msg_copy:
                # If content is None, convert to empty string
                if msg_copy['content'] is None:
                    msg_copy['content'] = ""
                    
                # If content is a list (multimodal), ensure all items are serializable
                elif isinstance(msg_copy['content'], list):
                    # Deep copy the content to avoid modifying the original
                    content_copy = []
                    for item in msg_copy['content']:
                        if isinstance(item, dict):
                            # For image items, ensure they have the right format
                            if item.get('type') == 'image_url' and 'image_url' in item:
                                # Make sure image_url is properly structured
                                if isinstance(item['image_url'], dict) and 'url' in item['image_url']:
                                    # This is already in the correct format
                                    content_copy.append(item.copy())
                                elif isinstance(item['image_url'], str):
                                    # Convert simple string URL to proper format
                                    content_copy.append({
                                        'type': 'image_url',
                                        'image_url': {
                                            'url': item['image_url']
                                        }
                                    })
                                else:
                                    # Invalid format, skip
                                    print(f"Warning: Skipping invalid image item: {item}")
                            else:
                                # For non-image dictionaries, just copy
                                content_copy.append(item.copy())
                        elif isinstance(item, str):
                            # Wrap text content in proper format
                            content_copy.append({
                                'type': 'text',
                                'text': item
                            })
                        else:
                            # Convert any non-dict items to string representation
                            content_copy.append(str(item))
                    msg_copy['content'] = content_copy
            
            processed_messages.append(msg_copy)
        else:
            # For object-style messages, convert to dictionary
            msg_dict = {
                'role': getattr(message, 'role', 'user'),
                'content': getattr(message, 'content', '')
            }
            
            # Handle tool calls if present
            if hasattr(message, 'tool_calls') and message.tool_calls:
                msg_dict['tool_calls'] = []
                for tool_call in message.tool_calls:
                    if isinstance(tool_call, dict):
                        msg_dict['tool_calls'].append(tool_call.copy())
                    else:
                        # Convert object to dictionary
                        tool_call_dict = {
                            'id': getattr(tool_call, 'id', ''),
                            'function': {
                                'name': getattr(getattr(tool_call, 'function', {}), 'name', ''),
                                'arguments': getattr(getattr(tool_call, 'function', {}), 'arguments', '{}')
                            }
                        }
                        msg_dict['tool_calls'].append(tool_call_dict)
            
            # Add tool_call_id if present
            if hasattr(message, 'tool_call_id') and message.tool_call_id:
                msg_dict['tool_call_id'] = message.tool_call_id
                
            processed_messages.append(msg_dict)
    
    return processed_messages

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
