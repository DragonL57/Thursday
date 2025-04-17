"""
API client for interaction with LLM APIs
"""

import json
import time
import random
import requests
import copy
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
        This method uses the Pollinations API directly.
        """
        # Import config module, no need to import json here as it's at module level
        import config as conf
        
        try:
            # Process messages for Pollinations API format
            processed_messages = preprocess_messages_for_pollinations(messages, self.model)
            
            # Create payload for Pollinations API
            payload = {
                "model": self.model,
                "messages": processed_messages,
                "temperature": conf.TEMPERATURE,
                "top_p": conf.TOP_P,
                "max_tokens": conf.MAX_TOKENS,
                "seed": conf.SEED,
                "referrer": "personal-gem",  # Identify our application to the API
            }
            
            # Add stream parameter if streaming is requested
            if stream:
                payload["stream"] = True
            
            # Add tools if provided, with schema validation for Azure OpenAI compatibility
            if tools:
                # Make a deep copy to avoid modifying the original tools
                normalized_tools = copy.deepcopy(tools)
                
                # Fix schema issues with tools for Azure OpenAI compatibility
                normalized_tools = self._normalize_tool_schema(normalized_tools)
                payload["tools"] = normalized_tools
            
            # Add safety settings if available
            safety_settings = getattr(conf, 'SAFETY_SETTINGS', None)
            if safety_settings:
                payload["safety_settings"] = safety_settings
                
            # Use Pollinations API
            url = "https://text.pollinations.ai/openai"
            headers = {"Content-Type": "application/json"}
            
            print(f"Making request to {url} with model: {self.model}")
            
            # For debugging purposes, log payload size
            payload_json = json.dumps(payload)
            payload_size = len(payload_json)
            print(f"Payload size: {payload_size} bytes")
            
            if payload_size > 100000:
                print("Warning: Large payload size may cause issues with API limits")
                
            response = requests.post(url, json=payload, headers=headers, stream=stream)
            
            # Log the response status code for troubleshooting
            print(f"Response status code: {response.status_code}")
            
            if response.status_code != 200:
                # For error responses, try to extract the error message from the response
                try:
                    error_detail = response.json()
                    print(f"API Error details: {error_detail}")
                except:
                    print(f"Raw error response: {response.text[:500]}...")
                    
            response.raise_for_status()
            
            if stream:
                return response
            else:
                return response.json()
        except Exception as e:
            print(f"Error in get_completion: {e}")
            # If there's an error, print a summarized version of the request payload for debugging
            if 'payload' in locals():
                # Limit the payload output to avoid overwhelming logs
                msg_sample = []
                if 'messages' in payload:
                    for msg in payload['messages']:
                        if isinstance(msg, dict):
                            msg_sample.append({
                                'role': msg.get('role', 'unknown'),
                                'content_length': len(str(msg.get('content', '')))
                            })
                
                print(f"Request payload: {json.dumps({**payload, 'messages': msg_sample})}")
            raise

    def _normalize_tool_schema(self, tools):
        """
        Normalize tool schema to ensure compatibility with Azure OpenAI
        which requires stricter JSON schema validation than other providers.
        """
        if not tools:
            return tools
            
        for tool in tools:
            if not isinstance(tool, dict):
                continue
                
            function = tool.get('function', {})
            params = function.get('parameters', {})
            
            # Fix the required field - must be an array or omitted, never null
            if 'required' in params and params['required'] is None:
                # Either remove the required field or set it as an empty array
                del params['required']
            
            # Ensure properties is an object, not None
            if 'properties' in params and params['properties'] is None:
                params['properties'] = {}
                
        return tools

    def handle_tool_call_followup(self, messages, tool_outputs=None):
        """
        Handle a follow-up request after tool execution using Pollinations API.
        
        Args:
            messages: The conversation history including tool results
            tool_outputs: The results of tool execution
            
        Returns:
            The API response after tool execution
        """
        import config as conf
        
        print("Handling tool call follow-up with Pollinations API")
        
        try:
            # Process messages for the follow-up call
            processed_messages = preprocess_messages_for_pollinations(messages, self.model)
            
            # Create payload for the follow-up call
            payload = {
                "model": self.model,
                "messages": processed_messages,
                "temperature": conf.TEMPERATURE,
                "top_p": conf.TOP_P,
                "max_tokens": conf.MAX_TOKENS,
                "seed": conf.SEED,
                "referrer": "personal-gem",
            }
            
            # Use Pollinations API
            url = "https://text.pollinations.ai/openai"
            headers = {"Content-Type": "application/json"}
            
            print(f"Making follow-up request to {url} with model: {self.model}")
            
            payload_json = json.dumps(payload)
            payload_size = len(payload_json)
            print(f"Follow-up payload size: {payload_size} bytes")
            
            response = requests.post(url, json=payload, headers=headers)
            
            # Log the response status code
            print(f"Follow-up response status code: {response.status_code}")
            
            if response.status_code != 200:
                try:
                    error_detail = response.json()
                    print(f"Follow-up API Error details: {error_detail}")
                except:
                    print(f"Raw follow-up error response: {response.text[:500]}...")
                    
            response.raise_for_status()
            
            return response.json()
        except Exception as e:
            print(f"Error in handle_tool_call_followup: {e}")
            if 'payload' in locals():
                # Print summarized payload for debugging
                msg_sample = []
                if 'messages' in payload:
                    for msg in payload['messages']:
                        if isinstance(msg, dict):
                            msg_sample.append({
                                'role': msg.get('role', 'unknown'),
                                'content_length': len(str(msg.get('content', '')))
                            })
                print(f"Follow-up payload: {json.dumps({**payload, 'messages': msg_sample})}")
            raise


# Helper function to preprocess messages for Pollinations API
def preprocess_messages_for_pollinations(messages, model_name):
    """
    Preprocess messages to ensure proper format for Pollinations,
    particularly for multimodal content.
    
    Args:
        messages: List of message objects
        model_name: Name of the model being used
    
    Returns:
        Processed list of messages
    """
    processed_messages = []
    
    for message in messages:
        # Skip messages without content
        if not message or 'content' not in message:
            processed_messages.append(message)
            continue
            
        # Handle different types of content structures
        content = message['content']
        
        # If content is a string, no special processing needed
        if isinstance(content, str):
            processed_messages.append(message)
            continue
            
        # If content is a list (multimodal), ensure proper format for Pollinations
        elif isinstance(content, list):
            new_content = []
            for item in content:
                if isinstance(item, dict):
                    # Handle image_url items
                    if item.get('type') == 'image_url':
                        # Ensure proper format for images
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
    
    print(f"Processed {len(processed_messages)} messages for Pollinations API")
    return processed_messages
