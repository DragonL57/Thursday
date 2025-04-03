import inspect
import json
import os
from typing import Callable
from typing import Union
import colorama
import requests # Added for API calls
from pydantic import BaseModel
# Removed litellm import
from tools import TOOLS, validate_tool_call, tool_report_print # Updated imports
import pickle
# Removed litellm exception import, will use requests exceptions

from colorama import Fore, Style
from rich.console import Console, Group
from rich.live import Live
from rich.padding import Padding
from rich.markdown import Markdown
import config as conf

from prompt_toolkit import PromptSession
from prompt_toolkit.styles import Style as PromptToolkitStyle
from prompt_toolkit.formatted_text import FormattedText
from prompt_toolkit.auto_suggest import AutoSuggestFromHistory

from func_to_schema import function_to_json_schema
from gem.command import InvalidCommand, CommandNotFound, CommandExecuter, cmd
import gem

from dotenv import load_dotenv

load_dotenv()
# Removed litellm debug suppression


class Assistant:

    def __init__(
        self,
        model: str,
        name: str = "Assistant",
        tools: list[Callable] = [],
        system_instruction: str = "",
    ) -> None:
        self.model = model
        self.name = name
        self.system_instruction = system_instruction
        self.messages = []
        self.available_functions = {func.__name__: func for func in tools}
        self.tools = list(map(function_to_json_schema, tools))

        if system_instruction:
            self.messages.append({"role": "system", "content": system_instruction})

        self.console = Console()
        self.border_width = 100

    def send_message(self, message):
        self.messages.append({"role": "user", "content": message})
        response = self.get_completion()
        return self.__process_response(response)

    def wrap_text(self, text, width):
        """Custom text wrapper that preserves bullet points and indentation."""
        lines = []
        for line in text.split('\n'):
            # Detect bullet points or numbered lists
            is_bullet = line.lstrip().startswith(('•', '-', '*', '1.', '2.', '3.', '4.', '5.', '6.', '7.', '8.', '9.'))
            indent = len(line) - len(line.lstrip())
            
            # If it's a bullet point, reduce available width by indentation
            if is_bullet:
                available_width = width - indent - 2  # -2 for some padding
            else:
                available_width = width
            
            # Wrap this line
            if len(line) > width:
                # Split into words
                words = line.split()
                current_line = []
                current_length = indent
                
                for word in words:
                    if current_length + len(word) + 1 <= available_width:
                        current_line.append(word)
                        current_length += len(word) + 1
                    else:
                        # Add the current line with proper indentation
                        if current_line:
                            lines.append(' ' * indent + ' '.join(current_line))
                        current_line = [word]
                        current_length = indent + len(word)
                
                if current_line:
                    lines.append(' ' * indent + ' '.join(current_line))
            else:
                lines.append(line)
        
        return lines

    def print_ai(self, msg: str):
        formatted_msg = msg.strip() if msg else ""
        
        # Print the box
        print(f"{Fore.YELLOW}┌{'─' * self.border_width}┐{Style.RESET_ALL}")
        print(f"{Fore.YELLOW}│{Style.RESET_ALL} {Fore.GREEN}{self.name}:{Style.RESET_ALL}")
        self.console.print(Markdown(formatted_msg))
        print(f"{Fore.YELLOW}└{'─' * self.border_width}┘{Style.RESET_ALL}")

    def get_completion(self):
        """Get a completion from the Pollinations AI model with the current messages and tools."""
        api_url = "https://text.pollinations.ai/openai" # Pollinations API endpoint
        headers = {"Content-Type": "application/json"}
        payload = {
            "model": self.model,
            "messages": self.messages,
            "tools": self.tools,
            "temperature": conf.TEMPERATURE,
            "top_p": conf.TOP_P,
            "max_tokens": conf.MAX_TOKENS,
            "seed": conf.SEED,
            # No safety_settings for Pollinations
        }
        # Filter out None values from payload, as API might not like null values for optional params
        payload = {k: v for k, v in payload.items() if v is not None}

        try:
            response = requests.post(api_url, headers=headers, json=payload, timeout=60) # Added timeout
            response.raise_for_status() # Raise HTTPError for bad responses (4xx or 5xx)
            return response.json() # Return the JSON response
        except requests.exceptions.HTTPError as http_err:
            if response.status_code == 429:
                print(f"{Fore.RED}Rate limit exceeded. Please wait and try again.{Style.RESET_ALL}")
                # Re-raise or handle specific rate limit logic if needed
                raise ConnectionError("Rate limit exceeded") # Use a generic exception type or define a custom one
            else:
                print(f"{Fore.RED}HTTP error occurred: {http_err} - {response.text}{Style.RESET_ALL}")
                raise # Re-raise other HTTP errors
        except requests.exceptions.RequestException as req_err:
            print(f"{Fore.RED}Error during API request: {req_err}{Style.RESET_ALL}")
            raise # Re-raise other request errors
        except json.JSONDecodeError as json_err:
            print(f"{Fore.RED}Error decoding API response: {json_err} - Response: {response.text}{Style.RESET_ALL}")
            raise # Re-raise JSON errors

    def add_msg_assistant(self, msg: str):
        self.messages.append({"role": "assistant", "content": msg})

    def add_toolcall_output(self, tool_id, name, content):
        self.messages.append(
            {
                "tool_call_id": tool_id,
                "role": "tool",
                "name": name,
                "content": str(content),
            }
        )

    @cmd(["save"], "Saves the current chat session to pickle file.")
    def save_session(self, name: str, filepath=f"chats"):
        """
        Args:
            name: The name of the file to save the session to. (can be either with or without json extension)
            filepath: The path to the directory to save the file to. (default: "/chats")
        """
        try:
            # create directory if default path doesn't exist
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
        Args:
            name: The name of the file to load the session from. (can be either with or without json extension)
            filepath: The path to the directory to load the file from. (default: "/chats")
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
        self.messages = []
        if self.system_instruction:
            self.messages.append({"role": "system", "content": self.system_instruction})

    def convert_to_pydantic_model(self, annotation, arg_value):
        """
        Attempts to convert a value to a Pydantic model.
        """
        if isinstance(annotation, type) and issubclass(annotation, BaseModel):
            try:
                return annotation(**arg_value)
            except (TypeError, ValueError):
                return arg_value  # not a valid Pydantic model or data mismatch
        elif hasattr(annotation, "__origin__"):
            origin = annotation.__origin__
            args = annotation.__args__

            if origin is list:
                return [
                    self.convert_to_pydantic_model(args[0], item) for item in arg_value
                ]
            elif origin is dict:
                return {
                    key: self.convert_to_pydantic_model(args[1], value)
                    for key, value in arg_value.items()
                }
            elif origin is Union:
                for arg_type in args:
                    try:
                        return self.convert_to_pydantic_model(arg_type, arg_value)
                    except (ValueError, TypeError):
                        continue
                raise ValueError(f"Could not convert {arg_value} to any type in {args}")
            elif origin is tuple:
                return tuple(
                    self.convert_to_pydantic_model(args[i], arg_value[i])
                    for i in range(len(args))
                )
            elif origin is set:
                return {
                    self.convert_to_pydantic_model(args[0], item) for item in arg_value
                }
        return arg_value

    def __process_response(self, response_json, print_response=False, validation_retries=2): # Added retry counter, default print_response to False
        # Parse the response structure from requests.json()
        # Assuming OpenAI compatible structure: {'choices': [{'message': {...}}]}
        if not response_json or "choices" not in response_json or not response_json["choices"]:
             print(f"{Fore.RED}Error: Invalid response format from API: {response_json}{Style.RESET_ALL}")
             # Return a dummy structure or raise an error to prevent downstream crashes
             return {"role": "assistant", "content": "Error: Received invalid response from API."} # Provide a basic message object

        # Convert the dict to a more object-like structure if needed, or access via keys
        # For simplicity, we'll access via keys. If complex logic relies on attribute access,
        # consider converting to a SimpleNamespace or a custom class.
        response_message = response_json["choices"][0]["message"] # This is now a dict

        # tool_calls might be missing if no tools were called
        tool_calls_raw = response_message.get("tool_calls") # Use .get() for safety

        # Process tool_calls if present
        tool_calls = []
        if tool_calls_raw:
             # Convert the raw tool call dicts if necessary, or use them directly
             # Assuming the structure matches: [{'id': '...', 'type': 'function', 'function': {'name': '...', 'arguments': '...'}}]
             tool_calls = tool_calls_raw # Use the list of dicts directly
        if tool_calls:
            # Only append the assistant message containing tool calls *if* we intend to process them
            # If all fail validation and retries are exhausted, we might not want this in history.
            # Let's append it for now, assuming corrections will build upon it.
            if response_message not in self.messages: # Avoid duplicates during recursion
                 # response_message is already a dict, suitable for appending
                 self.messages.append(response_message)

            needs_correction_reprompt = False
            successful_tool_call_happened = False
            tool_errors = [] # Store errors for potential reprompt

            for tool_call in tool_calls:
                # Access tool call info via dict keys
                function_name = tool_call['function']['name']
                tool_id = tool_call['id'] # Get the tool_call_id
                function_to_call = self.available_functions.get(function_name)

                if function_to_call is None:
                    err_msg = f"Function not found with name: {function_name}"
                    print(f"{Fore.RED}Error: {err_msg}{Style.RESET_ALL}")
                    self.add_toolcall_output(tool_id, function_name, err_msg)
                    tool_errors.append((tool_id, function_name, err_msg)) # Store error
                    needs_correction_reprompt = True
                    continue

                try: # Wrap parsing, validation, and execution attempt
                    # Access arguments via dict key
                    function_args_str = tool_call['function']['arguments']
                    function_args = json.loads(function_args_str)

                    # <<< VALIDATION STEP >>>
                    is_valid, validation_error = validate_tool_call(function_name, function_args)
                    if not is_valid:
                        err_msg = f"Tool call validation failed: {validation_error}. Please correct the parameters."
                        tool_report_print("Validation Error:", f"Tool call '{function_name}'. Reason: {validation_error}", is_error=True)
                        self.add_toolcall_output(tool_id, function_name, err_msg)
                        tool_errors.append((tool_id, function_name, err_msg)) # Store error
                        needs_correction_reprompt = True
                        continue # Skip executing this invalid call

                    # <<< EXECUTION (if valid) >>>
                    sig = inspect.signature(function_to_call)
                    converted_args = function_args.copy() # Use copy for conversion
                    for param_name, param in sig.parameters.items():
                        if param_name in converted_args:
                            converted_args[param_name] = self.convert_to_pydantic_model(
                                param.annotation, converted_args[param_name]
                            )

                    function_response = function_to_call(**converted_args)

                    # Print intermediate assistant message if it existed before the tool call
                    # Check content key in the response_message dict
                    if response_message.get("content"):
                         pass # Let final text print at the end

                    # Add successful tool output to history
                    self.add_toolcall_output(
                        tool_id, function_name, function_response
                    )
                    successful_tool_call_happened = True # Mark that at least one tool ran

                except json.JSONDecodeError as e:
                    err_msg = f"Failed to decode tool arguments for {function_name}: {e}. Arguments received: {function_args_str}"
                    tool_report_print("Argument Error:", err_msg, is_error=True)
                    self.add_toolcall_output(tool_id, function_name, err_msg)
                    tool_errors.append((tool_id, function_name, err_msg)) # Store error
                    needs_correction_reprompt = True
                    continue
                except Exception as e: # Catch execution errors
                    err_msg = f"Error executing tool {function_name}: {e}"
                    print(f"{Fore.RED}{err_msg}{Style.RESET_ALL}")
                    # traceback.print_exc() # Optional: for more detailed debugging
                    self.add_toolcall_output(tool_id, function_name, err_msg)
                    tool_errors.append((tool_id, function_name, err_msg)) # Store error
                    needs_correction_reprompt = True
                    continue

            # === After processing all tool calls in this batch ===
            if needs_correction_reprompt:
                if validation_retries > 0:
                    print(f"{Fore.YELLOW}Attempting to get corrected tool call(s) from LLM (Retries left: {validation_retries})...{Style.RESET_ALL}")
                    # History now contains the original attempt + error messages
                    new_response = self.get_completion()
                    # Recursively process the new response with decremented retries
                    return self.__process_response(new_response, print_response=print_response, validation_retries=validation_retries - 1)
                else:
                    print(f"{Fore.RED}Max validation retries exceeded. Failed to get valid tool call(s).{Style.RESET_ALL}")
                    # Fallback: Return the last text response content if available, or a generic error.
                    # Access content via dict key
                    final_text_content = response_message.get("content") or f"Could not complete the tool operation(s) ({', '.join([name for _, name, _ in tool_errors])}) after multiple retries due to validation or execution errors."
                    # Ensure the error message is part of the final assistant output
                    if not response_message.get("content"):
                         # Need to add a final assistant message if the original only had tools
                         self.add_msg_assistant(final_text_content)

                    # if print_response:
                    #     self.print_ai(final_text_content) # Commented out print

                    # Return the final text content
                    return final_text_content # Return the text content

            elif successful_tool_call_happened:
                # If tools executed successfully, get the LLM's summary/next step based on tool results
                final_response_after_tools = self.get_completion()
                # Process this final response (might contain text or more tools)
                # Reset retries for this new turn
                return self.__process_response(final_response_after_tools, print_response=print_response, validation_retries=2) # Reset retries
            else:
                # This case should ideally not be reached if tool_calls was not empty initially.
                # If it is, it implies all tool calls failed validation/parsing and retries were exhausted.
                # The logic within needs_correction_reprompt handles the retry exhaustion.
                # If somehow we get here, just print any text content from the original message.
                 # Access content via dict key
                 # if print_response and response_message.get("content"): # Commented out print
                 #    self.print_ai(response_message["content"])
                 return response_message.get("content") # Return the text content or None

        else: # No tool_calls in the initial response message
            # Append the simple text response to history
            # Append the simple text response dict to history
            if response_message not in self.messages:
                 self.messages.append(response_message) # Append the dict
            # Access content via dict key
            # if print_response and response_message.get("content"): # Commented out print
            #     self.print_ai(response_message["content"])
            return response_message.get("content") # Return the text content or None


if __name__ == "__main__":
    colorama.init(autoreset=True)

    sys_instruct = conf.get_system_prompt().strip()

    assistant = Assistant(
        model=conf.MODEL, system_instruction=sys_instruct, tools=TOOLS
    )

    # handle commands
    command = gem.CommandExecuter.register_commands(
        gem.builtin_commands.COMMANDS + [assistant.save_session, assistant.load_session, assistant.reset_session]
    )
    COMMAND_PREFIX = "/"
    # set command prefix (default is /)
    CommandExecuter.command_prefix = COMMAND_PREFIX

    if conf.CLEAR_BEFORE_START:
        gem.clear_screen()


    # Customize autocomplete style
    custom_style = PromptToolkitStyle.from_dict({
        "prompt": "fg:ansiblue", 
        "completion-menu": "bg:ansiblack fg:ansigreen",
        "completion-menu.completion": "bg:ansiblack fg:ansiblue",  
        "completion-menu.completion.current": "bg:ansigray fg:ansipurple", 
    })

    session = PromptSession(
        completer=gem.SlashCompleter([COMMAND_PREFIX + name for name in CommandExecuter.get_command_names()]),
        complete_while_typing=True, 
        auto_suggest=AutoSuggestFromHistory(),
        style=custom_style  
    )

    prompt_text = FormattedText([
        ("fg:ansicyan", "│ "),    
        ("fg:ansimagenta", "You: "), 
        ("", "")
    ])

    gem.print_header(f"{conf.NAME} CHAT INTERFACE")
    while True:
        try:
            border_width = 100
            print(f"{Fore.CYAN}┌{'─' * border_width}┐{Style.RESET_ALL}")
            # msg = input("f{Fore.CYAN}│ {Fore.MAGENTA}You:{Style.RESET_ALL} ")
            # msg = session.prompt()
            msg = session.prompt(prompt_text)
            print(f"{Fore.CYAN}└{'─' * border_width}┘{Style.RESET_ALL}")

            if not msg:
                continue

            if msg.startswith("/"):
                CommandExecuter.execute(msg)
                continue

            assistant.send_message(msg)

        except KeyboardInterrupt:
            print(
                f"\n\n{Fore.GREEN}Chat session interrupted.{Style.RESET_ALL}"
            )
            break
        except InvalidCommand as e:
            print(f"{Fore.RED}Error: {e}{Style.RESET_ALL}")
        except CommandNotFound as e:
            print(f"{Fore.RED}Error: {e}{Style.RESET_ALL}")
        # Catch the generic ConnectionError we raise for rate limits, or other request errors
        except ConnectionError as e:
            # Error is already printed in get_completion or __process_response
            pass # Or add specific handling if needed
        except Exception as e:
            print(f"{Fore.RED}An error occurred: {e}{Style.RESET_ALL}")
            # traceback.print_exc()
