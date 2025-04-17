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
from .api_client import preprocess_messages_for_pollinations
from .image_processor import optimize_images, process_image_for_gemini
from .streaming import StreamHandler
from .tool_handler import process_tool_calls, convert_to_pydantic_model
from .utils import cmd

# Import provider manager for integrated models
from utils.provider_manager import ProviderManager

# Add the missing import for ApiClient
from .api_client import ApiClient

class Assistant:
    """
    Assistant class that handles interactions with the LiteLLM.
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
        stream_handler: bool = True  # Default to True to always use streaming
    ) -> None:
        """
        Initialize an Assistant instance.
        
        Args:
            model: The model to use for completions
            name: Display name for the assistant
            tools: List of callable functions to make available to the assistant
            system_instruction: System prompt for the assistant
            stream_handler: Whether to enable streaming response handling (default is True)
        """
        self.model = model
        self.name = name
        self.system_instruction = system_instruction
        self.messages = []
        
        # Update the available_functions handling to support both callables and dictionaries
        self.available_functions = {}
        
        # Flag to track if final response has been streamed
        self._streamed_final_response = False
        
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
        self.is_processing = False
        self._processing_thread = None
        self._final_response = None

        # Initialize provider manager
        ProviderManager.initialize()
        
        # Set provider to pollinations - no longer using litellm
        self.provider = 'pollinations'
        
        # Normalize the model name for Pollinations
        self.model = model
        
        # Initialize the API client for Pollinations
        self.api_client = ApiClient(model=self.model)
        
        # Initialize streaming handler (always enable for consistency)
        self.stream_handler = StreamHandler(self) if stream_handler else None

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
        Prepare a message for processing.
        
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
                # Replace litellm references
                response = self.api_client.get_completion(
                    preprocess_messages_for_pollinations(self.messages, self.model),
                    tools=self.tools
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
        Send a message and get the response (uses streaming internally for consistency).
        
        Args:
            message: The text message to send
            images: Optional list of image data dictionaries
            
        Returns:
            Dict containing text response and tool call information
        """
        # Clear any previous tool calls and image data
        self.current_tool_calls = []
        self.image_data = []
        
        # Process images based on the model type
        if images:
            print(f"{Fore.CYAN}Processing images for model: {self.model}{Style.RESETALL}")
            
            # Process images - only Gemini supported now
            self.image_data = process_image_for_gemini(images)
            print(f"{Fore.GREEN}Processed images for Gemini model{Style.RESETALL}")
        
        # Prepare the content array if images are present
        if self.image_data:
            content = [{"type": "text", "text": message}]
            content.extend(self.image_data)
            # Add user message with content array
            self.messages.append({"role": "user", "content": content})
        else:
            # Add simple text message
            self.messages.append({"role": "user", "content": message})
        
        # Create a container to collect the final response
        collected_response = {"text": "", "tool_calls": []}
        
        # Define a callback to collect the response from the stream
        def collect_response(event):
            if event["event"] == "token":
                collected_response["text"] += event["data"]
            elif event["event"] == "tool_call":
                # Keep track of tool calls
                collected_response["tool_calls"].append(event["data"])
            elif event["event"] == "final":
                collected_response["text"] = event["data"]  # Replace with complete text
        
        # Use the stream handler to process the message
        for _ in self.stream_handler.stream_send_message(message, self.image_data, collect_response):
            pass  # Process all stream events
        
        return collected_response

    def update_provider(self, provider: str, model: str = None):
        """
        Update the provider and model, reinitializing client if needed.
        Note: We only support LiteLLM now, but keeping this method for compatibility.
        
        Args:
            provider: The provider to use (only 'litellm' is supported)
            model: Optional new model name to use
        """
        updated = False
        
        # Always use LiteLLM, ignore provider parameter
        if self.provider != 'litellm':
            self.provider = 'litellm'
            updated = True
        
        # Update model if provided
        if model is not None and self.model != model:
            self.model = model
            updated = True
        
        # Reinitialize if needed
        if updated:
            pass

    def print_ai(self, msg: str):
        """Print a formatted assistant message to the console."""
        formatted_msg = msg.strip() if msg else ""
        
        print(f"{Fore.YELLOW}┌{'─' * self.border_width}┐{Style.RESETALL}")
        print(f"{Fore.YELLOW}│{Style.RESETALL} {Fore.GREEN}{self.name}:{Style.RESETALL}")
        self.console.print(Markdown(formatted_msg))
        print(f"{Fore.YELLOW}└{'─' * self.border_width}┘{Style.RESETALL}")

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
                f"{Fore.GREEN}Chat session saved to {Fore.BLUE}{final_path}{Style.RESETALL}"
            )
        except Exception as e:
            print(f"{Fore.RED}Error: {e}{Style.RESETALL}")

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
                f"{Fore.GREEN}Chat session loaded from {Fore.BLUE}{final_path}{Style.RESETALL}"
            )
        except FileNotFoundError:
            print(
                f"{Fore.RED}Chat session not found{Style.RESETALL} {Fore.BLUE}{final_path}{Style.RESETALL}"
            )
        except Exception as e:
            print(f"{Fore.RED}Error: {e}{Style.RESETALL}")

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
        # Process images - only Gemini supported now
        if images:
            print(f"{Fore.CYAN}Processing images for model (streaming): {self.model}{Style.RESETALL}")
            processed_images = process_image_for_gemini(images)
            print(f"{Fore.GREEN}Processed images for Gemini model{Style.RESETALL}")
            
            # Pass the processed images to the stream handler
            return self.stream_handler.stream_send_message(message, processed_images, callback)
        else:
            # No images, just pass the message
            return self.stream_handler.stream_send_message(message, None, callback)
