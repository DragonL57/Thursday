"""
Core Assistant functionality
"""

import json
import os
import inspect
import pickle
from typing import Callable, Union, Dict, List, Any

import litellm
from colorama import Fore, Style
from rich.console import Console
from rich.markdown import Markdown
from pydantic import BaseModel

import config as conf
from .api_client import ApiClient, preprocess_messages_for_litellm, preprocess_messages_for_pollinations
from .image_processor import optimize_images
from .streaming import StreamHandler
from .tool_handler import process_tool_calls, convert_to_pydantic_model
from .utils import cmd

# Import provider manager for integrated models
from utils.provider_manager import ProviderManager

class Assistant:
    """
    Assistant class that handles interactions with the Pollinations API.
    Includes support for:
    - Message sending and receiving
    - Tool/function calling
    - Streaming responses
    - Image handling
    - Chat history management
    """

    def __init__(
        self,
        model: str,
        name: str = "Assistant",
        tools: list[Callable] = [],
        system_instruction: str = "",
        stream_handler: bool = False
    ) -> None:
        """
        Initialize an Assistant instance.
        
        Args:
            model: The model to use for completions
            name: Display name for the assistant
            tools: List of callable functions to make available to the assistant
            system_instruction: System prompt for the assistant
            stream_handler: Whether to enable streaming response handling
        """
        self.model = model
        self.name = name
        self.system_instruction = system_instruction
        self.messages = []
        
        # Update the available_functions handling to support both callables and dictionaries
        self.available_functions = {}
        for func in tools:
            if callable(func):
                self.available_functions[func.__name__] = func
            elif isinstance(func, dict) and func.get("type") == "function" and "function" in func:
                # Handle the dictionary format for functions
                func_name = func["function"].get("name")
                if func_name:
                    # For dictionary-based tools, we'll store the entire dict
                    # It will be handled specially when called
                    self.available_functions[func_name] = func
        
        # Process tools for API
        self.tools = self._prepare_tools(tools)
        self.current_tool_calls = []  # Track tool calls for the current request
        self.image_data = []  # Track images in the current message
        
        # Streaming support
        self.stream_handler = stream_handler
        self.is_processing = False
        self._processing_thread = None
        self._final_response = None

        # Handle specific model providers
        if model == "pollinations-gpt4o":
            # Initialize provider manager
            ProviderManager.initialize()
            # Get appropriate provider and model
            provider, actual_model = ProviderManager.get_provider_and_model('pollinations-gpt4o')
            self.provider = provider
            self.model = actual_model
        elif model == "github-gpt4o":
            # Initialize provider manager
            ProviderManager.initialize()
            # Get appropriate provider and model
            provider, actual_model = ProviderManager.get_provider_and_model('github-gpt4o')
            self.provider = provider
            self.model = actual_model
        elif model == "gpt4o-integrated":
            # Legacy model name - use pollinations as default for migrating users
            print("Warning: Using legacy gpt4o-integrated model name. Please update to either 'pollinations-gpt4o' or 'github-gpt4o'.")
            ProviderManager.initialize()
            provider, actual_model = ProviderManager.get_provider_and_model('pollinations-gpt4o')
            self.provider = provider
            self.model = actual_model
        else:
            # Determine if this is a litellm model (contains a slash)
            if "/" in model:
                self.provider = 'litellm'
                self.model = model
            else:
                # Use standard provider selection
                self.provider = getattr(conf, 'API_PROVIDER', 'pollinations')
                self.model = model
        
        # Initialize API client if using Pollinations
        if self.provider == 'pollinations':
            self.api_client = ApiClient(
                base_url="https://text.pollinations.ai/openai",
                model=self.model,
                retry_count=getattr(conf, 'API_RETRY_COUNT', 3),
                base_delay=getattr(conf, 'API_BASE_DELAY', 1.0),
                max_delay=getattr(conf, 'API_MAX_DELAY', 10.0),
                request_timeout=conf.WEB_REQUEST_TIMEOUT
            )
        else:
            self.api_client = None  # Not needed for litellm
        
        # Initialize streaming handler
        self.stream_handler = StreamHandler(self)

        # Add system instruction if provided
        if system_instruction:
            self.messages.append({"role": "system", "content": system_instruction})

        # Setup console for rich output
        self.console = Console()
        self.border_width = 100
    
    # Function to schema conversion
    def _function_to_schema(self, func):
        """Convert a function to a JSON schema for the API."""
        from func_to_schema import function_to_json_schema
        return function_to_json_schema(func)

    def _prepare_tools(self, tools):
        """Prepare tools list for API by converting functions to schemas when needed"""
        api_tools = []
        for tool in tools:
            if callable(tool):
                # Convert callable to schema
                api_tools.append(self._function_to_schema(tool))
            elif isinstance(tool, dict) and tool.get("type") == "function":
                # Already in schema format
                api_tools.append(tool)
        return api_tools

    def prepare_message(self, message, images=None):
        """
                    }
        This starts a background thread for processing.
        
        Args:
            message: The text message to send
            images: Optional list of image data dictionaries
        """
        # Clear any previous tool calls and results
        self.current_tool_calls = []
        self._final_response = None
        self.image_data = []
        
        # If images are provided, optimize and store them
        if images:
            self.image_data = optimize_images(images)
            
        # Add user message with content array if images exist
        if self.image_data:
            content = [{"type": "text", "text": message}]
            content.extend(self.image_data)
            self.messages.append({"role": "user", "content": content})
        else:
            # Add simple text message
            self.messages.append({"role": "user", "content": message})
        
        # Start processing in a background thread
        self.is_processing = True
        self._process_message_thread()
    
    def _process_message_thread(self):
        """Process the message and execute tools."""
        try:
            # Get completion based on provider
            if self.provider == 'pollinations':
                if not self.api_client:
                    raise ValueError("Pollinations provider selected but api_client is not initialized.")
                response = self.api_client.get_completion(
                    messages=self.messages,
                    tools=self.tools
                )
            elif self.provider == 'litellm':
                # Special handling for GitHub models to ensure the API key is set
                if self.model.startswith('github/') and not os.environ.get('GITHUB_API_KEY'):
                    # Try to get it from config if it exists
                    import config as conf
                    if hasattr(conf, 'GITHUB_API_KEY') and conf.GITHUB_API_KEY:
                        os.environ['GITHUB_API_KEY'] = conf.GITHUB_API_KEY
                    else:
                        print("Warning: Using a GitHub model but GITHUB_API_KEY is not set in environment or config")
                
                response = litellm.completion(
                    model=self.model,
                    messages=self.messages,
                    tools=self.tools,
                    temperature=conf.TEMPERATURE,
                    top_p=conf.TOP_P,
                    max_tokens=conf.MAX_TOKENS,
                    seed=conf.SEED,
                    safety_settings=conf.SAFETY_SETTINGS
                )
            else:
                raise ValueError(f"Unsupported provider: {self.provider}")

            result = process_tool_calls(self, response)
            
            # Store the final response
            if isinstance(result, str):
                self._final_response = result
            elif isinstance(result, dict) and "text" in result:
                self._final_response = result["text"]
            else:
                self._final_response = "Processing completed but no response was generated."
                
        except Exception as e:
            print(f"Error in processing: {e}")
            self._final_response = f"Error during processing: {str(e)}"
        finally:
            self.is_processing = False
    
    def send_message(self, message, images=None):
        """
        Send a message and get the response (non-streaming mode).
        
        Args:
            message: The text message to send
            images: Optional list of image data dictionaries
            
        Returns:
            Dict containing text response and tool call information
        """
        # Clear any previous tool calls and image data
        self.current_tool_calls = []
        self.image_data = []
        
        # If images are provided, optimize and store them
        if images:
            self.image_data = optimize_images(images)
        
        # Prepare the content array if images are present
        if self.image_data:
            content = [{"type": "text", "text": message}]
            content.extend(self.image_data)
            # Add user message with content array
            self.messages.append({"role": "user", "content": content})
        else:
            # Add simple text message
            self.messages.append({"role": "user", "content": message})
            
        # Get completion using either Pollinations API or litellm
        if getattr(conf, 'API_PROVIDER', 'pollinations') == 'pollinations':
            try:
                # Import the proper preprocessing function
                from assistant.api_client import preprocess_messages_for_pollinations
                
                # Make sure the API client is initialized
                if not self.api_client:
                    from assistant.api_client import ApiClient
                    self.api_client = ApiClient()
                
                response = self.api_client.get_completion(
                    messages=self.messages,
                    tools=self.tools
                )
            except Exception as e:
                print(f"Error in Pollinations API call: {e}")
                # Return an error response
                return {
                    "text": f"Sorry, I encountered an error while processing your request: {str(e)}",
                    "tool_calls": self.current_tool_calls
                }
        else:
            response = litellm.completion(
                model=self.model,
                messages=self.messages,
                tools=self.tools,
                temperature=conf.TEMPERATURE,
                top_p=conf.TOP_P,
                max_tokens=conf.MAX_TOKENS,
                seed=conf.SEED,
                safety_settings=conf.SAFETY_SETTINGS
            )
        
        # Process the response and return both text and tool calls
        result = process_tool_calls(self, response)
        
        # If result is just a string, return it as is for backward compatibility
        if isinstance(result, str):
            return {"text": result, "tool_calls": self.current_tool_calls}
        
        # Otherwise return the structured response
        return result

    def update_provider(self, provider: str, model: str = None):
        """
        Update the provider and model, reinitializing client if needed.
        
        Args:
            provider: The provider to use ('pollinations' or 'litellm')
            model: Optional new model name to use
        """
        updated = False
        
        # Update provider if changed
        if self.provider != provider:
            self.provider = provider
            updated = True
        
        # Update model if provided
        if model is not None and self.model != model:
            self.model = model
            updated = True
            
        # Only reinitialize if something changed
        if updated:
            # Initialize API client for Pollinations or clean up for other providers
            if self.provider == 'pollinations':
                self.api_client = ApiClient(
                    base_url="https://text.pollinations.ai/openai",
                    model=self.model,
                    retry_count=getattr(conf, 'API_RETRY_COUNT', 3),
                    base_delay=getattr(conf, 'API_BASE_DELAY', 1.0),
                    max_delay=getattr(conf, 'API_MAX_DELAY', 10.0),
                    request_timeout=conf.WEB_REQUEST_TIMEOUT
                )
            else:
                self.api_client = None
                
            print(f"Assistant provider updated to: {self.provider} with model: {self.model}")

    def print_ai(self, msg: str):
        """Print a formatted assistant message to the console."""
        formatted_msg = msg.strip() if msg else ""
        
        print(f"{Fore.YELLOW}┌{'─' * self.border_width}┐{Style.RESET_ALL}")
        print(f"{Fore.YELLOW}│{Style.RESET_ALL} {Fore.GREEN}{self.name}:{Style.RESET_ALL}")
        self.console.print(Markdown(formatted_msg))
        print(f"{Fore.YELLOW}└{'─' * self.border_width}┘{Style.RESET_ALL}")

    def add_msg_assistant(self, msg: str):
        """Add an assistant message to the conversation history."""
        self.messages.append({"role": "assistant", "content": msg})

    def add_toolcall_output(self, tool_id, name, content):
        """Add a tool call result to the conversation history."""
        self.messages.append(
            {
                "tool_call_id": tool_id,
                "role": "tool",
                "name": name,
                "content": str(content),
            }
        )
        # Update the current tool call status and result
        for tool_call in self.current_tool_calls:
            if tool_call.get("id") == tool_id:
                tool_call["status"] = "completed" if "Error" not in str(content) else "error"
                tool_call["result"] = str(content)
                break

    @cmd(["save"], "Saves the current chat session to pickle file.")
    def save_session(self, name: str, filepath=f"chats"):
        """
        Save the current chat session to a file.
        
        Args:
            name: The name of the file to save the session to
            filepath: The path to the directory to save the file to
        """
        try:
            if filepath == "chats":
                os.makedirs(filepath, exist_ok=True)

            final_path = os.path.join(filepath, name + ".pkl")
            with open(final_path, "wb") as f:
                pickle.dump(self.messages, f)

            print(
                f"{Fore.GREEN}Chat session saved to {Fore.BLUE}{final_path}{Style.RESET_ALL}"
            )
        except Exception as e:
            print(f"{Fore.RED}Error: {e}{Style.RESET_ALL}")

    @cmd(["load"], "Loads a chat session from a pickle file. Resets the session.")
    def load_session(self, name: str, filepath=f"chats"):
        """
        Load a chat session from a file.
        
        Args:
            name: The name of the file to load the session from
            filepath: The path to the directory to load the file from
        """
        try:
            final_path = os.path.join(filepath, name + ".pkl")
            with open(final_path, "rb") as f:
                self.messages = pickle.load(f)
            print(
                f"{Fore.GREEN}Chat session loaded from {Fore.BLUE}{final_path}{Style.RESET_ALL}"
            )
        except FileNotFoundError:
            print(
                f"{Fore.RED}Chat session not found{Style.RESET_ALL} {Fore.BLUE}{final_path}{Style.RESET_ALL}"
            )
        except Exception as e:
            print(f"{Fore.RED}Error: {e}{Style.RESET_ALL}")

    @cmd(["reset"], "Resets the chat session.")
    def reset_session(self):
        """Reset the chat session, keeping only the system prompt."""
        self.messages = []
        if self.system_instruction:
            self.messages.append({"role": "system", "content": self.system_instruction})

    def get_final_response(self):
        """Get the final text response after all processing is complete."""
        if hasattr(self, '_final_response') and self._final_response is not None:
            return self._final_response
        # Fallback in case _final_response isn't set yet
        if self.messages and len(self.messages) > 0:
            # Try to get the last assistant message
            for msg in reversed(self.messages):
                if msg.get("role") == "assistant" and "content" in msg:
                    return msg["content"]
        return "Processing completed but no response was generated."

    # Methods that are now in streaming.py, exposed for backward compatibility
    def stream_get_next_response(self, callback=None):
        """
        Get the next response after executing tools.
        This is used for recursive tool call handling.
        """
        return self.stream_handler.stream_get_next_response(callback)
        
    def stream_send_message(self, message, images=None, callback=None):
        """
        Send a message and stream the response with callback for each chunk.
        """
        return self.stream_handler.stream_send_message(message, images, callback)
