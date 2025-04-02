import inspect
import json
import os
from typing import Callable
from typing import Union
import colorama
from pydantic import BaseModel
import litellm
from tools import TOOLS, validate_tool_call, tool_report_print # Updated imports
import pickle
from litellm.exceptions import RateLimitError

from colorama import Fore, Style
from rich.console import Console
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
litellm.suppress_debug_info = True


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

    def send_message(self, message):
        self.messages.append({"role": "user", "content": message})
        response = self.get_completion()
        return self.__process_response(response)

    def print_ai(self, msg: str):
        print(f"{Fore.YELLOW}┌{'─' * 58}┐{Style.RESET_ALL}")
        print(f"{Fore.YELLOW}│ {Fore.GREEN}{self.name}:{Style.RESET_ALL} ", end="")
        self.console.print(
            Markdown(msg.strip() if msg else ""), end="", soft_wrap=True, no_wrap=False
        )
        print(f"{Fore.YELLOW}└{'─' * 58}┘{Style.RESET_ALL}")

    def get_completion(self):
        """Get a completion from the model with the current messages and tools."""
        return litellm.completion(
            model=self.model,
            messages=self.messages,
            tools=self.tools,
            temperature=conf.TEMPERATURE,
            top_p=conf.TOP_P,
            max_tokens=conf.MAX_TOKENS,
            seed=conf.SEED,
            safety_settings=conf.SAFETY_SETTINGS
        )

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

    def __process_response(self, response, print_response=True, validation_retries=2): # Added retry counter
        response_message = response.choices[0].message
        # Avoid appending the message immediately if it might be replaced by a corrected one
        # self.messages.append(response_message) # Moved appending logic

        tool_calls = response_message.tool_calls

        if tool_calls:
            # Only append the assistant message containing tool calls *if* we intend to process them
            # If all fail validation and retries are exhausted, we might not want this in history.
            # Let's append it for now, assuming corrections will build upon it.
            if response_message not in self.messages: # Avoid duplicates during recursion
                 self.messages.append(response_message)

            needs_correction_reprompt = False
            successful_tool_call_happened = False
            tool_errors = [] # Store errors for potential reprompt

            for tool_call in tool_calls:
                function_name = tool_call.function.name
                function_to_call = self.available_functions.get(function_name)

                if function_to_call is None:
                    err_msg = f"Function not found with name: {function_name}"
                    print(f"{Fore.RED}Error: {err_msg}{Style.RESET_ALL}")
                    self.add_toolcall_output(tool_call.id, function_name, err_msg)
                    tool_errors.append((tool_call.id, function_name, err_msg)) # Store error
                    needs_correction_reprompt = True
                    continue

                try: # Wrap parsing, validation, and execution attempt
                    function_args = json.loads(tool_call.function.arguments)

                    # <<< VALIDATION STEP >>>
                    is_valid, validation_error = validate_tool_call(function_name, function_args)
                    if not is_valid:
                        err_msg = f"Tool call validation failed: {validation_error}. Please correct the parameters."
                        tool_report_print("Validation Error:", f"Tool call '{function_name}'. Reason: {validation_error}", is_error=True)
                        self.add_toolcall_output(tool_call.id, function_name, err_msg)
                        tool_errors.append((tool_call.id, function_name, err_msg)) # Store error
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
                    if response_message.content:
                         # Avoid printing duplicate messages during recursive calls
                         pass # Let final text print at the end

                    # Add successful tool output to history
                    self.add_toolcall_output(
                        tool_call.id, function_name, function_response
                    )
                    successful_tool_call_happened = True # Mark that at least one tool ran

                except json.JSONDecodeError as e:
                    err_msg = f"Failed to decode tool arguments for {function_name}: {e}. Arguments received: {tool_call.function.arguments}"
                    tool_report_print("Argument Error:", err_msg, is_error=True)
                    self.add_toolcall_output(tool_call.id, function_name, err_msg)
                    tool_errors.append((tool_call.id, function_name, err_msg)) # Store error
                    needs_correction_reprompt = True
                    continue
                except Exception as e: # Catch execution errors
                    err_msg = f"Error executing tool {function_name}: {e}"
                    print(f"{Fore.RED}{err_msg}{Style.RESET_ALL}")
                    # traceback.print_exc() # Optional: for more detailed debugging
                    self.add_toolcall_output(tool_call.id, function_name, err_msg)
                    tool_errors.append((tool_call.id, function_name, err_msg)) # Store error
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
                    # Check if the original message had content besides the failed tool calls
                    final_text_content = response_message.content or f"Could not complete the tool operation(s) ({', '.join([name for _, name, _ in tool_errors])}) after multiple retries due to validation or execution errors."
                    # Ensure the error message is part of the final assistant output
                    if not response_message.content:
                         # Need to add a final assistant message if the original only had tools
                         self.add_msg_assistant(final_text_content)

                    if print_response:
                        self.print_ai(final_text_content)

                    # Return the original message object, but the history reflects the errors
                    return response_message

            elif successful_tool_call_happened:
                # If tools executed successfully, get the LLM's summary/next step based on tool results
                print(f"{Fore.YELLOW}Getting LLM response after successful tool execution...{Style.RESET_ALL}")
                final_response_after_tools = self.get_completion()
                # Process this final response (might contain text or more tools)
                # Reset retries for this new turn
                return self.__process_response(final_response_after_tools, print_response=print_response, validation_retries=2) # Reset retries
            else:
                # This case should ideally not be reached if tool_calls was not empty initially.
                # If it is, it implies all tool calls failed validation/parsing and retries were exhausted.
                # The logic within needs_correction_reprompt handles the retry exhaustion.
                # If somehow we get here, just print any text content from the original message.
                 if print_response and response_message.content:
                    self.print_ai(response_message.content)
                 return response_message

        else: # No tool_calls in the initial response message
            # Append the simple text response to history
            if response_message not in self.messages:
                 self.messages.append(response_message)
            if print_response and response_message.content:
                self.print_ai(response_message.content)
            return response_message


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
            print(f"{Fore.CYAN}┌{'─' * 58}┐{Style.RESET_ALL}")
            # msg = input("f{Fore.CYAN}│ {Fore.MAGENTA}You:{Style.RESET_ALL} ")
            # msg = session.prompt()
            msg = session.prompt(prompt_text)
            print(f"{Fore.CYAN}└{'─' * 58}┘{Style.RESET_ALL}")

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
        except RateLimitError as e:
            print(f"{Fore.RED}You are being rate limited\n{e}{Style.RESET_ALL}")
        except Exception as e:
            print(f"{Fore.RED}An error occurred: {e}{Style.RESET_ALL}")
            # traceback.print_exc()
