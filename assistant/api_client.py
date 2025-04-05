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
        Get a completion from the LLM API with retry logic for transient errors.
        
        Args:
            messages: Message history to send to the API
            tools: Optional list of tool definitions
        
        Returns:
            API response JSON
        """
        last_exception = None
        
        for attempt in range(self.retry_count + 1):
            try:
                response = self._make_api_request(messages, tools)
                return response
                
            except requests.exceptions.HTTPError as e:
                status_code = e.response.status_code if hasattr(e, 'response') else 0
                
                if status_code == 429:
                    if attempt < self.retry_count:
                        # Use more aggressive backoff for rate limit errors
                        retry_after = int(e.response.headers.get('Retry-After', 3))
                        jitter = random.uniform(0, 2)  # Add jitter to avoid thundering herd
                        delay = max(retry_after, 3) + jitter
                        
                        # If we're sending images, use even longer delays
                        has_images = any(isinstance(msg.get('content', ''), list) for msg in messages)
                        if has_images:
                            delay = delay * 2
                            
                        print(f"{Fore.YELLOW}Rate limit hit. Adding jitter and backing off more aggressively. Retrying in {delay:.1f} seconds...{Style.RESET_ALL}")
                        time.sleep(delay)
                        continue
                    else:
                        last_exception = e
                        if has_images:
                            msg = "Rate limit exceeded when processing images. Try reducing image size or waiting longer between requests."
                            print(f"{Fore.RED}{msg}{Style.RESET_ALL}")
                
                elif status_code in [502, 503, 504]:
                    if attempt < self.retry_count:
                        delay = min(self.base_delay * (2 ** attempt) + random.uniform(0, 0.5), self.max_delay)
                        print(f"{Fore.YELLOW}Server error ({status_code}). Retrying in {delay:.2f} seconds...{Style.RESET_ALL}")
                        time.sleep(delay)
                        continue
                
                last_exception = e
                print(f"{Fore.RED}HTTP error occurred: {e}{Style.RESET_ALL}")
                
            except (requests.exceptions.ConnectionError, requests.exceptions.Timeout) as e:
                if attempt < self.retry_count:
                    delay = min(self.base_delay * (2 ** attempt) + random.uniform(0, 1.0), self.max_delay)
                    print(f"{Fore.YELLOW}Network error. Retrying in {delay:.2f} seconds...{Style.RESET_ALL}")
                    time.sleep(delay)
                    continue
                
                last_exception = e
                print(f"{Fore.RED}Network error: {e}{Style.RESET_ALL}")
            
            except Exception as e:
                last_exception = e
                print(f"{Fore.RED}Unexpected error: {e}{Style.RESET_ALL}")
                break
        
        if last_exception:
            raise last_exception
        raise Exception("Failed to get completion after multiple retries")
    
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
        
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": conf.TEMPERATURE,
            "top_p": conf.TOP_P,
            "max_tokens": conf.MAX_TOKENS,
            "seed": conf.SEED,
        }
        
        # Remove None values from payload
        payload = {k: v for k, v in payload.items() if v is not None}
        
        # Add tools/functions if available
        if tools:
            payload["tools"] = tools
        
        # Add streaming parameter if requested
        if stream:
            payload["stream"] = True
        
        headers = {"Content-Type": "application/json"}
        
        try:
            # Log the request
            print(f"DEBUG: API request to {self.base_url}")
            print(f"DEBUG: - model: {self.model}")
            print(f"DEBUG: - streaming: {stream}")
            print(f"DEBUG: - tools: {len(tools) if tools else 0} tools provided")
            print(f"DEBUG: - messages: {len(messages)} messages")
            
            # Use the timeout from config
            response = requests.post(
                self.base_url, 
                json=payload, 
                headers=headers, 
                timeout=self.request_timeout,
                stream=stream  # Enable streaming at request level
            )
            
            # Log the response status
            print(f"DEBUG: API response status: {response.status_code}")
            
            try:
                response.raise_for_status()
            except requests.exceptions.HTTPError as e:
                print(f"ERROR: API request failed with status {response.status_code}")
                if not stream:
                    # Try to get error details
                    try:
                        error_json = response.json()
                        print(f"ERROR: API error details: {error_json}")
                    except:
                        print(f"ERROR: API error response (raw): {response.text[:500]}")
                raise
                
            # For streaming requests, return the raw response object
            if stream:
                print(f"DEBUG: Returning streaming response object")
                return response
            
            # For regular requests, parse and return the JSON
            response_json = response.json()
            print(f"DEBUG: API returned JSON response")
            
            # Log some basic info from the response
            if "choices" in response_json and response_json["choices"]:
                choice = response_json["choices"][0]
                if "message" in choice:
                    message = choice["message"]
                    if "content" in message:
                        content_preview = message["content"][:50] + "..." if message["content"] and len(message["content"]) > 50 else message["content"]
                        print(f"DEBUG: Response content preview: {content_preview}")
                    if "tool_calls" in message and message["tool_calls"]:
                        print(f"DEBUG: Response contains {len(message['tool_calls'])} tool calls")
            
            return response_json
            
        except Exception as e:
            # Log the error but don't re-raise it here
            # This allows the calling code to handle the error gracefully
            print(f"{Fore.RED}ERROR: Error in API request: {e}{Style.RESET_ALL}")
            import traceback
            traceback.print_exc()
            # Re-raise the exception to be handled by the retry logic
            raise
