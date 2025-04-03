import inspect
import json
import os
from typing import Callable
from typing import Union, Dict, List, Any
import colorama
import requests
from requests.exceptions import RequestException
from pydantic import BaseModel
from tools import TOOLS, validate_tool_call, tool_report_print
import pickle
import time
import random

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
        self.current_tool_calls = []  # Track tool calls for the current request
        
        # Fixed Pollinations API URL for OpenAI-compatible endpoint
        self.api_base_url = "https://text.pollinations.ai/openai"
        
        # Set retry parameters from config or defaults
        self.retry_count = getattr(conf, 'API_RETRY_COUNT', 3)
        self.base_delay = getattr(conf, 'API_BASE_DELAY', 1.0)
        self.max_delay = getattr(conf, 'API_MAX_DELAY', 10.0)
        self.request_timeout = conf.WEB_REQUEST_TIMEOUT

        if system_instruction:
            self.messages.append({"role": "system", "content": system_instruction})

        self.console = Console()
        self.border_width = 100
    
    def send_message(self, message):
        # Clear any previous tool calls
        self.current_tool_calls = []
        
        # Add user message and get completion
        self.messages.append({"role": "user", "content": message})
        response = self.get_completion()
        
        # Process the response and return both text and tool calls
        result = self.__process_response(response)
        
        # If result is just a string, return it as is for backward compatibility
        if isinstance(result, str):
            return {"text": result, "tool_calls": self.current_tool_calls}
        
        # Otherwise return the structured response
        return result

    def wrap_text(self, text, width):
        """Custom text wrapper that preserves bullet points and indentation."""
        lines = []
        for line in text.split('\n'):
            is_bullet = line.lstrip().startswith(('•', '-', '*', '1.', '2.', '3.', '4.', '5.', '6.', '7.', '8.', '9.'))
            indent = len(line) - len(line.lstrip())
            
            if is_bullet:
                available_width = width - indent - 2
            else:
                available_width = width
            
            if len(line) > width:
                words = line.split()
                current_line = []
                current_length = indent
                
                for word in words:
                    if current_length + len(word) + 1 <= available_width:
                        current_line.append(word)
                        current_length += len(word) + 1
                    else:
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
        
        print(f"{Fore.YELLOW}┌{'─' * self.border_width}┐{Style.RESET_ALL}")
        print(f"{Fore.YELLOW}│{Style.RESET_ALL} {Fore.GREEN}{self.name}:{Style.RESET_ALL}")
        self.console.print(Markdown(formatted_msg))
        print(f"{Fore.YELLOW}└{'─' * self.border_width}┘{Style.RESET_ALL}")

    def get_completion(self, retry_count=None, base_delay=None, max_delay=None):
        """
        Get a completion from the LLM API with retry logic for transient errors.
        
        Args:
            retry_count: Maximum number of retries (defaults to self.retry_count)
            base_delay: Base delay between retries in seconds (defaults to self.base_delay)
            max_delay: Maximum delay between retries in seconds (defaults to self.max_delay)
        
        Returns:
            API response JSON
        """
        # Use instance values if parameters not provided
        retry_count = retry_count if retry_count is not None else self.retry_count
        base_delay = base_delay if base_delay is not None else self.base_delay
        max_delay = max_delay if max_delay is not None else self.max_delay
        
        last_exception = None
        
        for attempt in range(retry_count + 1):
            try:
                response = self._make_api_request()
                return response
                
            except requests.exceptions.HTTPError as e:
                status_code = e.response.status_code if hasattr(e, 'response') else 0
                
                if status_code == 429:
                    if attempt < retry_count:
                        retry_after = int(e.response.headers.get('Retry-After', 3))
                        delay = max(retry_after, 3)
                        print(f"{Fore.YELLOW}Rate limit hit. Retrying in {delay} seconds...{Style.RESET_ALL}")
                        time.sleep(delay)
                        continue
                
                elif status_code in [502, 503, 504]:
                    if attempt < retry_count:
                        delay = min(base_delay * (2 ** attempt) + random.uniform(0, 0.5), max_delay)
                        print(f"{Fore.YELLOW}Server error ({status_code}). Retrying in {delay:.2f} seconds...{Style.RESET_ALL}")
                        time.sleep(delay)
                        continue
                
                last_exception = e
                print(f"{Fore.RED}HTTP error occurred: {e}{Style.RESET_ALL}")
                
            except (requests.exceptions.ConnectionError, requests.exceptions.Timeout) as e:
                if attempt < retry_count:
                    delay = min(base_delay * (2 ** attempt) + random.uniform(0, 1.0), max_delay)
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
    
    def _make_api_request(self):
        """
        Implementation of API request to Pollinations AI using the openai-large model.
        """
        payload = {
            "model": self.model,
            "messages": self.messages,
            "temperature": conf.TEMPERATURE,
            "top_p": conf.TOP_P,
            "max_tokens": conf.MAX_TOKENS,
            "seed": conf.SEED,
        }
        
        # Remove None values from payload
        payload = {k: v for k, v in payload.items() if v is not None}
        
        # Add tools/functions if available
        if self.tools:
            payload["tools"] = self.tools
        
        headers = {"Content-Type": "application/json"}
        
        # Use the timeout from config
        response = requests.post(
            self.api_base_url, 
            json=payload, 
            headers=headers, 
            timeout=self.request_timeout
        )
        response.raise_for_status()
        
        return response.json()

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
        # Update the current tool call status and result
        for tool_call in self.current_tool_calls:
            if tool_call.get("id") == tool_id:
                tool_call["status"] = "completed" if "Error" not in str(content) else "error"
                tool_call["result"] = str(content)
                break

    @cmd(["save"], "Saves the current chat session to pickle file.")
    def save_session(self, name: str, filepath=f"chats"):
        """
        Args:
            name: The name of the file to save the session to. (can be either with or without json extension)
            filepath: The path to the directory to save the file to. (default: "/chats")
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
                return arg_value
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

    def __process_response(self, response_json, print_response=False, validation_retries=2):
        if not response_json or "choices" not in response_json or not response_json["choices"]:
            print(f"{Fore.RED}Error: Invalid response format from API: {response_json}{Style.RESET_ALL}")
            return {"text": "Error: Received invalid response from API.", "tool_calls": []}

        response_message = response_json["choices"][0]["message"]

        tool_calls_raw = response_message.get("tool_calls")

        tool_calls = []
        if tool_calls_raw:
            tool_calls = tool_calls_raw
        if tool_calls:
            # Track tool calls for this response
            for tool_call in tool_calls:
                self.current_tool_calls.append({
                    "id": tool_call["id"],
                    "name": tool_call["function"]["name"],
                    "args": tool_call["function"]["arguments"],
                    "status": "pending",
                    "result": None
                })
            
            if response_message not in self.messages:
                self.messages.append(response_message)

            needs_correction_reprompt = False
            successful_tool_call_happened = False
            tool_errors = []

            for tool_call in tool_calls:
                function_name = tool_call['function']['name']
                tool_id = tool_call['id']
                function_to_call = self.available_functions.get(function_name)

                if function_to_call is None:
                    err_msg = f"Function not found with name: {function_name}"
                    print(f"{Fore.RED}Error: {err_msg}{Style.RESET_ALL}")
                    self.add_toolcall_output(tool_id, function_name, err_msg)
                    tool_errors.append((tool_id, function_name, err_msg))
                    needs_correction_reprompt = True
                    continue

                try:
                    function_args_str = tool_call['function']['arguments']
                    function_args = json.loads(function_args_str)

                    is_valid, validation_error = validate_tool_call(function_name, function_args)
                    if not is_valid:
                        err_msg = f"Tool call validation failed: {validation_error}. Please correct the parameters."
                        tool_report_print("Validation Error:", f"Tool call '{function_name}'. Reason: {validation_error}", is_error=True)
                        self.add_toolcall_output(tool_id, function_name, err_msg)
                        tool_errors.append((tool_id, function_name, err_msg))
                        needs_correction_reprompt = True
                        continue

                    sig = inspect.signature(function_to_call)
                    converted_args = function_args.copy()
                    for param_name, param in sig.parameters.items():
                        if param_name in converted_args:
                            converted_args[param_name] = self.convert_to_pydantic_model(
                                param.annotation, converted_args[param_name]
                            )

                    function_response = function_to_call(**converted_args)

                    if response_message.get("content"):
                        pass

                    self.add_toolcall_output(
                        tool_id, function_name, function_response
                    )
                    successful_tool_call_happened = True

                except json.JSONDecodeError as e:
                    err_msg = f"Failed to decode tool arguments for {function_name}: {e}. Arguments received: {function_args_str}"
                    tool_report_print("Argument Error:", err_msg, is_error=True)
                    self.add_toolcall_output(tool_id, function_name, err_msg)
                    tool_errors.append((tool_id, function_name, err_msg))
                    needs_correction_reprompt = True
                    continue
                except Exception as e:
                    err_msg = f"Error executing tool {function_name}: {e}"
                    print(f"{Fore.RED}{err_msg}{Style.RESET_ALL}")
                    self.add_toolcall_output(tool_id, function_name, err_msg)
                    tool_errors.append((tool_id, function_name, err_msg))
                    needs_correction_reprompt = True
                    continue

            if needs_correction_reprompt:
                if validation_retries > 0:
                    print(f"{Fore.YELLOW}Attempting to get corrected tool call(s) from LLM (Retries left: {validation_retries})...{Style.RESET_ALL}")
                    new_response = self.get_completion()
                    return self.__process_response(new_response, print_response=print_response, validation_retries=validation_retries - 1)
                else:
                    print(f"{Fore.RED}Max validation retries exceeded. Failed to get valid tool call(s).{Style.RESET_ALL}")
                    final_text_content = response_message.get("content") or f"Could not complete the tool operation(s) ({', '.join([name for _, name, _ in tool_errors])}) after multiple retries due to validation or execution errors."
                    if not response_message.get("content"):
                        self.add_msg_assistant(final_text_content)

                    return {"text": final_text_content, "tool_calls": self.current_tool_calls}

            elif successful_tool_call_happened:
                final_response_after_tools = self.get_completion()
                return self.__process_response(final_response_after_tools, print_response=print_response, validation_retries=2)
            else:
                return {"text": response_message.get("content", ""), "tool_calls": self.current_tool_calls}

        else:
            if response_message not in self.messages:
                self.messages.append(response_message)
            return {"text": response_message.get("content", ""), "tool_calls": self.current_tool_calls}


if __name__ == "__main__":
    colorama.init(autoreset=True)

    sys_instruct = conf.get_system_prompt().strip()

    assistant = Assistant(
        model=conf.MODEL, system_instruction=sys_instruct, tools=TOOLS
    )

    command = gem.CommandExecuter.register_commands(
        gem.builtin_commands.COMMANDS + [assistant.save_session, assistant.load_session, assistant.reset_session]
    )
    COMMAND_PREFIX = "/"
    CommandExecuter.command_prefix = COMMAND_PREFIX

    if conf.CLEAR_BEFORE_START:
        gem.clear_screen()

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
        except ConnectionError as e:
            pass
        except Exception as e:
            print(f"{Fore.RED}An error occurred: {e}{Style.RESET_ALL}")
