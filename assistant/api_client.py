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
    
    def __init__(self, base_url, model, retry_count=3, base_delay=1.0, max_delay=10.0, request_timeout=30):
        """
        Initialize API client.
        
        Args:
            base_url: Base URL for API requests
            model: Model identifier to use
            retry_count: Number of retries for failed requests
            base_delay: Base delay between retries in seconds
            max_delay: Maximum delay between retries in seconds
            request_timeout: HTTP request timeout in seconds
        """
        self.base_url = base_url
        self.model = model
        self.retry_count = retry_count
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.request_timeout = request_timeout
    
    def get_completion(self, messages, tools=None):
        """
        Send a completion request to the API
        """
        # Process messages to ensure proper format for the API
        processed_messages = preprocess_messages_for_pollinations(messages)
        
        payload = {
            "model": "openai-large",  # Default model for Pollinations
            "messages": processed_messages,
        }

        if tools:
            # Format tools to match OpenAI's expected structure
            formatted_tools = self._format_tools(tools)
            payload["tools"] = formatted_tools
            payload["tool_choice"] = "auto"

        try:
            return self._make_api_request(messages, tools)
        except Exception as e:
            print(f"API request failed: {e}")
            # Return a minimal response structure to avoid breaking the process
            return {
                "choices": [
                    {
                        "message": {
                            "role": "assistant",
                            "content": f"Sorry, there was an error communicating with the API: {e}"
                        }
                    }
                ]
            }
    
    def _format_tools(self, tools):
        """
        Format tools to match the OpenAI-compatible API format expected by Pollinations.
        
        Args:
            tools: List of tool definitions
            
        Returns:
            List of formatted tool definitions
        """
        formatted_tools = []
        
        for tool in tools:
            # Check if tool is already in the right format
            if isinstance(tool, dict) and "function" in tool:
                formatted_tools.append(tool)
            # If it's a raw schema, wrap it in the proper format
            elif isinstance(tool, dict) and "name" in tool:
                formatted_tools.append({
                    "type": "function",
                    "function": tool
                })
            # If it doesn't match expected formats, skip it
            else:
                print(f"Warning: Skipping tool with unexpected format: {tool}")
                
        return formatted_tools
    
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
        
        payload = {
            "model": self.model,
            "messages": processed_messages,
            "temperature": conf.TEMPERATURE,
            "top_p": conf.TOP_P,
            "max_tokens": conf.MAX_TOKENS,
            "seed": conf.SEED,
        }
        
        # Remove None values from payload
        payload = {k: v for k, v in payload.items() if v is not None}
        
        # Add tools/functions if available
        if tools:
            payload["tools"] = self._format_tools(tools)
            payload["tool_choice"] = "auto"
        
        # Add streaming parameter if requested
        if stream:
            payload["stream"] = True
            
        # Make the API request with retry logic
        for attempt in range(self.retry_count + 1):
            try:
                response = requests.post(
                    self.base_url,
                    json=payload,
                    headers={"Content-Type": "application/json"},
                    timeout=self.request_timeout,
                    stream=stream
                )
                
                response.raise_for_status()
                
                if stream:
                    return response
                else:
                    return response.json()
                    
            except requests.exceptions.RequestException as e:
                if attempt < self.retry_count:
                    delay = min(self.base_delay * (2 ** attempt), self.max_delay)
                    print(f"API request failed: {e}. Retrying in {delay:.1f} seconds...")
                    time.sleep(delay)
                else:
                    raise
        
        # This should not be reached due to the raise in the except block
        raise RuntimeError("Unexpected error in API request")

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
                            content_copy.append(item.copy())
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
