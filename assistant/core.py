"""
Core Assistant functionality
"""

import json
import os
import inspect
import pickle
from typing import Callable, Union, Dict, List, Any

from colorama import Fore, Style
from rich.console import Console
from rich.markdown import Markdown
from pydantic import BaseModel

import config as conf
from .api_client import ApiClient
from .image_processor import optimize_images
from .streaming import StreamHandler
from .tool_handler import process_tool_calls, convert_to_pydantic_model
from .utils import cmd

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
        self.available_functions = {func.__name__: func for func in tools}
        self.tools = list(map(self._function_to_schema, tools))
        self.current_tool_calls = []  # Track tool calls for the current request
        self.image_data = []  # Track images in the current message
        
        # Streaming support
        self.stream_handler = stream_handler
        self.is_processing = False
        self._processing_thread = None
        self._final_response = None
        
        # Initialize API client
        self.api_client = ApiClient(
            base_url="https://text.pollinations.ai/openai",
            model=model,
            retry_count=getattr(conf, 'API_RETRY_COUNT', 3),
            base_delay=getattr(conf, 'API_BASE_DELAY', 1.0),
            max_delay=getattr(conf, 'API_MAX_DELAY', 10.0),
            request_timeout=conf.WEB_REQUEST_TIMEOUT
        )
        
        # Initialize streaming handler
        self.stream_handler = StreamHandler(self)

        # Add system instruction if provided
        if system_instruction:
            self.messages.append({"role": "system", "content": system_instruction})

        # Setup console for rich output
        self.console = Console()
        self.border_width = 100
        
    def _function_to_schema(self, func):
        """Convert a function to a JSON schema for the API."""
        from func_to_schema import function_to_json_schema
        return function_to_json_schema(func)

    def prepare_message(self, message, images=None):
        """
        Prepare to process a message in streaming mode.
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
            response = self.api_client.get_completion(
                messages=self.messages,
                tools=self.tools
            )
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
            
        # Get completion from API
        response = self.api_client.get_completion(
            messages=self.messages,
            tools=self.tools
        )
        
        # Process the response and return both text and tool calls
        result = process_tool_calls(self, response)
        
        # If result is just a string, return it as is for backward compatibility
        if isinstance(result, str):
            return {"text": result, "tool_calls": self.current_tool_calls}
        
        # Otherwise return the structured response
        return result

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
