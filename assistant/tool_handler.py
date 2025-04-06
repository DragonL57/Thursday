"""
Tool execution and processing
"""

import json
import inspect
from colorama import Fore, Style
from pydantic import BaseModel
from tools import validate_tool_call, tool_report_print

def process_tool_calls(assistant, response_json, print_response=True, validation_retries=2, recursion_depth=0):
    """
    Process a response from the API, handling any tool calls and follow-up responses.
    
    This method recursively processes tool calls until no more are requested,
    allowing for multi-turn tool calls in a single conversation turn.
    
    Args:
        assistant: The Assistant instance
        response_json: The JSON response from the API
        print_response: Whether to print the final response to console
        validation_retries: Number of retries left for tool validation issues
        recursion_depth: Current recursion depth to prevent infinite recursion
        
    Returns:
        Dict containing the final text response and tool call information
    """
    # Limit recursion depth to prevent stack overflow
    max_recursion_depth = 5  # Reasonable limit for most use cases
    if recursion_depth >= max_recursion_depth:
        print(f"{Fore.YELLOW}Maximum recursion depth ({max_recursion_depth}) reached. Stopping tool call processing.{Style.RESET_ALL}")
        return {"text": "Maximum tool call depth reached. I'll stop here and provide my current understanding.", 
                "tool_calls": assistant.current_tool_calls}
        
    if not response_json or "choices" not in response_json or not response_json["choices"]:
        print(f"{Fore.RED}Error: Invalid response format from API: {response_json}{Style.RESET_ALL}")
        return {"text": "Error: Received invalid response from API.", "tool_calls": []}

    # Extract the message from the response
    response_message = response_json["choices"][0]["message"]
    
    # Add the message to our conversation history
    if response_message not in assistant.messages:
        assistant.messages.append(response_message)
    
    # Check if there are any tool calls in the response
    tool_calls = response_message.get("tool_calls", [])
    
    # If no tool calls, this is a regular response - print and return it
    if not tool_calls:
        if print_response and response_message.get("content"):
            assistant.print_ai(response_message.get("content"))
        return {"text": response_message.get("content", ""), "tool_calls": assistant.current_tool_calls}
    
    # Add this response's tool calls to our tracking list
    for tool_call in tool_calls:
        assistant.current_tool_calls.append({
            "id": tool_call["id"],
            "name": tool_call["function"]["name"],
            "args": tool_call["function"]["arguments"],
            "status": "pending",
            "result": None
        })
    
    # Print any message content that came with the tool calls
    if print_response and response_message.get("content"):
        print(f"{Fore.YELLOW}│ {Fore.GREEN}{assistant.name}:{Style.RESET_ALL} {Style.DIM}{Fore.WHITE}{response_message['content'].strip()}{Style.RESET_ALL}")
    
    # Process each tool call
    has_errors = False
    processed_tool_ids = set()  # NEW: Track which tool calls we've processed
    
    # Log recursion depth for debugging
    max_recursion_depth = 3  # Limit recursive depth to avoid infinite loops
    if recursion_depth > max_recursion_depth:
        print(f"{Fore.RED}Maximum tool call recursion depth reached ({max_recursion_depth}). Stopping further tool calls.{Style.RESET_ALL}")
        return {"text": "Maximum tool call depth reached. I'll stop here and provide my current understanding.", 
                "tool_calls": assistant.current_tool_calls}
    
    if recursion_depth > 0:
        print(f"{Fore.CYAN}Tool call recursion depth: {recursion_depth}/{max_recursion_depth}{Style.RESET_ALL}")
    
    for tool_call in tool_calls:
        function_name = tool_call["function"]["name"]
        function_to_call = assistant.available_functions.get(function_name)
        tool_id = tool_call["id"]
        processed_tool_ids.add(tool_id)  # NEW: Mark this tool as processed
        
        # Check if the function exists
        if function_to_call is None:
            err_msg = f"Function not found with name: {function_name}"
            print(f"{Fore.RED}Error: {err_msg}{Style.RESET_ALL}")
            assistant.add_toolcall_output(tool_id, function_name, err_msg)
            has_errors = True
            continue
        
        try:
            # Parse and validate arguments
            function_args_str = tool_call["function"]["arguments"]
            
            # Handle empty arguments by providing an empty object
            if not function_args_str.strip():
                function_args_str = "{}"
                
            function_args = json.loads(function_args_str)
            
            # Validate tool call if we have a validation function
            is_valid, validation_error = validate_tool_call(function_name, function_args)
            if not is_valid:
                err_msg = f"Tool call validation failed: {validation_error}. Please correct the parameters."
                tool_report_print("Validation Error:", f"Tool call '{function_name}'. Reason: {validation_error}", is_error=True)
                assistant.add_toolcall_output(tool_id, function_name, err_msg)
                has_errors = True
                continue
            
            # Convert arguments to appropriate types using Pydantic models
            sig = inspect.signature(function_to_call)
            converted_args = function_args.copy()
            for param_name, param in sig.parameters.items():
                if param_name in converted_args:
                    converted_args[param_name] = convert_to_pydantic_model(
                        param.annotation, converted_args[param_name]
                    )
            
            # Execute the function with converted arguments
            function_response = function_to_call(**converted_args)
            
            # Report tool execution results
            tool_report_print(function_name, function_args, function_response)
            
            # Add tool call result to conversation
            assistant.add_toolcall_output(tool_id, function_name, function_response)
            
        except json.JSONDecodeError as e:
            # Handle JSON parsing errors
            err_msg = f"Failed to decode tool arguments for {function_name}: {e}. Arguments: {function_args_str}"
            print(f"{Fore.RED}{err_msg}{Style.RESET_ALL}")
            assistant.add_toolcall_output(tool_id, function_name, err_msg)
            has_errors = True
        except Exception as e:
            # Handle any other errors during execution
            err_msg = f"Error executing tool {function_name}: {e}"
            print(f"{Fore.RED}{err_msg}{Style.RESET_ALL}")
            assistant.add_toolcall_output(tool_id, function_name, err_msg)
            has_errors = True
    
    # NEW: Ensure all tool calls have responses before continuing
    # Check if any tool calls in current_tool_calls don't have responses yet
    if hasattr(assistant, 'current_tool_calls'):
        for tool_call in assistant.current_tool_calls:
            if tool_call.get("id") not in processed_tool_ids and tool_call.get("result") is None:
                tool_id = tool_call.get("id")
                function_name = tool_call.get("name", "unknown_tool")
                print(f"{Fore.YELLOW}WARNING: Tool call {tool_id} ({function_name}) has no response. Adding error response.{Style.RESET_ALL}")
                
                # Add an error response
                assistant.add_toolcall_output(
                    tool_id,
                    function_name,
                    "Error: Tool execution was skipped or failed. Please try again."
                )
                has_errors = True
    
    # If we had errors and have retries left, try again with a new API call
    if has_errors and validation_retries > 0:
        print(f"{Fore.YELLOW}Some tool calls failed. Trying to get corrected tool calls (Retries left: {validation_retries})...{Style.RESET_ALL}")
        try:
            new_response = assistant.api_client.get_completion(
                messages=assistant.messages,
                tools=assistant.tools
            )
            return process_tool_calls(
                assistant,
                new_response, 
                print_response=print_response, 
                validation_retries=validation_retries-1,
                recursion_depth=recursion_depth
            )
        except Exception as e:
            print(f"{Fore.RED}Error getting corrected tool calls: {e}. Continuing with current results.{Style.RESET_ALL}")
            return {"text": "Error processing tool calls. I'll stop here.", "tool_calls": assistant.current_tool_calls}
    
    # Get the next response after processing all tool calls
    # This allows multi-turn tool calling - the model may make more tool calls in its next response
    try:
        next_response = assistant.api_client.get_completion(
            messages=assistant.messages,
            tools=assistant.tools
        )
        
        # Process the new response recursively, incrementing the recursion depth
        return process_tool_calls(
            assistant,
            next_response, 
            print_response=print_response, 
            validation_retries=2,
            recursion_depth=recursion_depth+1
        )
    except Exception as e:
        print(f"{Fore.RED}Error in recursive tool call: {e}. Returning partial results.{Style.RESET_ALL}")
        # Return partial results if we encounter an error in the recursive call
        return {"text": "Error processing follow-up response. Here's what I know so far.", 
                "tool_calls": assistant.current_tool_calls}

def convert_to_pydantic_model(annotation, arg_value):
    """
    Attempts to convert a value to a Pydantic model.
    
    Args:
        annotation: Type annotation
        arg_value: Value to convert
        
    Returns:
        Converted value
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
                convert_to_pydantic_model(args[0], item) for item in arg_value
            ]
        elif origin is dict:
            return {
                key: convert_to_pydantic_model(args[1], value)
                for key, value in arg_value.items()
            }
        elif origin is Union:
            for arg_type in args:
                try:
                    return convert_to_pydantic_model(arg_type, arg_value)
                except (ValueError, TypeError):
                    continue
            raise ValueError(f"Could not convert {arg_value} to any type in {args}")
        elif origin is tuple:
            return tuple(
                convert_to_pydantic_model(args[i], arg_value[i])
                for i in range(len(args))
            )
        elif origin is set:
            return {
                convert_to_pydantic_model(args[0], item) for item in arg_value
            }
    return arg_value
