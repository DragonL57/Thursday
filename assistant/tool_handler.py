"""
Tool execution and processing
"""

import json
import inspect
import time
import random
import litellm  # Add the missing litellm import
from colorama import Fore, Style
from pydantic import BaseModel
from tools import validate_tool_call, tool_report_print
from assistant.api_client import preprocess_messages_for_litellm
import config as conf  # Add missing import for config

def process_tool_calls(assistant, response_json, print_response=True, validation_retries=2, recursion_depth=0, tool_event_callback=None):
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
        tool_event_callback: Optional callback function to handle tool call events
        
    Returns:
        Generator yielding events and finally a dict with the text response
    """
    # We'll still track recursion depth for debugging but won't limit it
    if tool_event_callback:
        for chunk in tool_event_callback("recursion_depth", recursion_depth):
            yield chunk
        
    if not response_json or "choices" not in response_json or not response_json["choices"]:
        print(f"{Fore.RED}Error: Invalid response format from API: {response_json}{Style.RESET_ALL}")
        yield {"final_text": "Error: Received invalid response from API."}
        return

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
        yield {"final_text": response_message.get("content", "")}
        return
    
    # Initialize current_tool_calls if it doesn't exist yet
    if not hasattr(assistant, 'current_tool_calls'):
        assistant.current_tool_calls = []
    
    # Add this response's tool calls to our tracking list
    for tool_call in tool_calls:
        # Check if this tool call is already being tracked (prevent duplicates)
        tool_id = tool_call["id"]
        function_name = tool_call["function"]["name"]
        function_args = tool_call["function"]["arguments"]
        
        # Create a signature for deduplication
        tool_signature = f"{function_name}:{function_args}"
        
        # Check if we're already tracking this exact tool call
        is_duplicate = False
        for existing_tool in assistant.current_tool_calls:
            if existing_tool["name"] == function_name and existing_tool["args"] == function_args:
                is_duplicate = True
                break
        
        # Only add if it's not a duplicate
        if not is_duplicate:
            tool_data = {
                "id": tool_id,
                "name": function_name,
                "args": function_args,
                "status": "pending",
                "result": None
            }
            
            # Notify about the tool call via callback if provided
            if tool_event_callback:
                for chunk in tool_event_callback("tool_call", tool_data):
                    yield chunk
                    
            assistant.current_tool_calls.append(tool_data)
    
    # Print any message content that came with the tool calls
    if print_response and response_message.get("content"):
        print(f"{Fore.YELLOW}│ {Fore.GREEN}{assistant.name}:{Style.RESET_ALL} {Style.DIM}{Fore.WHITE}{response_message['content'].strip()}{Style.RESET_ALL}")
    
    # Process each tool call
    has_errors = False
    processed_tool_ids = set()  # Track which tool calls we've processed
    
    # Check if the message had images - especially relevant for multimodal context
    has_image_content = False
    for msg in assistant.messages[-2:]:  # Check last few messages
        if isinstance(msg.get("content"), list):
            for content_item in msg.get("content", []):
                if isinstance(content_item, dict) and content_item.get("type") == "image_url":
                    has_image_content = True
                    break
    
    if has_image_content:
        print(f"{Fore.CYAN}Processing tool calls for message with image content{Style.RESET_ALL}")
        # If there's an info callback, use it to notify the user
        if tool_event_callback:
            for chunk in tool_event_callback("info", "Analyzing image with tools...", True):
                yield chunk
    
    for tool_call in tool_calls:
        function_name = tool_call["function"]["name"]
        function_to_call = assistant.available_functions.get(function_name)
        tool_id = tool_call["id"]
        
        # Skip if we've already processed this tool ID to prevent duplicate execution
        if tool_id in processed_tool_ids:
            continue
            
        processed_tool_ids.add(tool_id)  # Mark as processed
        
        # Check if the function exists
        if function_to_call is None:
            err_msg = f"Function not found with name: {function_name}"
            print(f"{Fore.RED}Error: {err_msg}{Style.RESET_ALL}")
            
            # Update tool call with error status
            for tc in assistant.current_tool_calls:
                if tc["id"] == tool_id:
                    tc["status"] = "error"
                    tc["result"] = err_msg
                    # Send update via callback
                    if tool_event_callback:
                        for chunk in tool_event_callback("tool_update", tc):
                            yield chunk
                    break
                    
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
            
            # Check for valid parameters
            is_valid, error_message = validate_tool_call(function_name, function_args)
            
            if not is_valid:
                # If validation fails, try to add missing required parameters
                if validation_retries > 0:
                    print(f"{Fore.YELLOW}Tool call validation failed: {error_message}. Retrying with corrected parameters.{Style.RESET_ALL}")
                    # Request a corrected tool call (implement this logic if needed)
                    # For now, just fail with the error message
                    err_msg = f"Error validating tool arguments: {error_message}"
                    print(f"{Fore.RED}Error: {err_msg}{Style.RESET_ALL}")
                    
                    # Update tool call with error status
                    for tc in assistant.current_tool_calls:
                        if tc["id"] == tool_id:
                            tc["status"] = "error"
                            tc["result"] = err_msg
                            # Send update via callback
                            if tool_event_callback:
                                for chunk in tool_event_callback("tool_update", tc):
                                    yield chunk
                            break
                    
                    assistant.add_toolcall_output(tool_id, function_name, err_msg)
                    has_errors = True
                    continue
            
            # Execute the tool in a controlled manner
            print(f"About to execute tool: {function_name}")
            try:
                # Signal tool execution start for real-time UI updates
                from tools.formatting import tool_report_print
                tool_report_print("Running tool:", f"{function_name}({function_args_str})")
                
                # Get function signature
                sig = inspect.signature(function_to_call)
                
                # Convert arguments to appropriate types
                converted_args = function_args.copy()
                for param_name, param in sig.parameters.items():
                    if param_name in converted_args and hasattr(assistant, 'convert_to_pydantic_model'):
                        converted_args[param_name] = assistant.convert_to_pydantic_model(
                            param.annotation, converted_args[param_name]
                        )
                
                # Execute the function with converted arguments
                function_response = function_to_call(**converted_args)
                
                # Signal tool execution completion for real-time UI updates
                print(f"Tool execution completed: {function_name}")
                tool_report_print("Result:", str(function_response))
                
                # Find and update the tool call object with the result
                for tc in assistant.current_tool_calls:
                    if tc["id"] == tool_id:
                        tc["status"] = "completed"
                        tc["result"] = str(function_response)
                        # Send update via callback
                        if tool_event_callback:
                            for chunk in tool_event_callback("tool_update", tc):
                                yield chunk
                        break
                
                # Report tool execution results
                if print_response:
                    print(f"{Fore.CYAN}Tool call: {function_name}({function_args}) => {function_response}{Style.RESET_ALL}")
                
                # Add tool call result to conversation
                assistant.add_toolcall_output(tool_id, function_name, function_response)
                
            except Exception as tool_execution_error:
                # Handle any errors from the tool execution itself
                err_msg = f"Error executing tool {function_name}: {tool_execution_error}"
                print(f"{Fore.RED}{err_msg}{Style.RESET_ALL}")
                tool_report_print("Result:", f"Error: {str(tool_execution_error)}", is_error=True)
                
                # Update tool call with error status
                for tc in assistant.current_tool_calls:
                    if tc["id"] == tool_id:
                        tc["status"] = "error"
                        tc["result"] = f"Error: {str(tool_execution_error)}"
                        # Send update via callback
                        if tool_event_callback:
                            for chunk in tool_event_callback("tool_update", tc):
                                yield chunk
                        break
                
                assistant.add_toolcall_output(tool_id, function_name, f"Error: {str(tool_execution_error)}")
                has_errors = True
            
        except json.JSONDecodeError as e:
            # Handle JSON parsing errors
            err_msg = f"Failed to decode tool arguments for {function_name}: {e}. Arguments: {function_args_str}"
            print(f"{Fore.RED}{err_msg}{Style.RESET_ALL}")
            
            # Update tool call with error status
            for tc in assistant.current_tool_calls:
                if tc["id"] == tool_id:
                    tc["status"] = "error"
                    tc["result"] = err_msg
                    # Send update via callback
                    if tool_event_callback:
                        for chunk in tool_event_callback("tool_update", tc):
                            yield chunk
                    break
            
            assistant.add_toolcall_output(tool_id, function_name, err_msg)
            has_errors = True
        except Exception as e:
            # Handle any other errors during execution
            err_msg = f"Error executing tool {function_name}: {e}"
            print(f"{Fore.RED}{err_msg}{Style.RESET_ALL}")
            
            # Update tool call with error status
            for tc in assistant.current_tool_calls:
                if tc["id"] == tool_id:
                    tc["status"] = "error"
                    tc["result"] = err_msg
                    # Send update via callback
                    if tool_event_callback:
                        for chunk in tool_event_callback("tool_update", tc):
                            yield chunk
                    break
            
            assistant.add_toolcall_output(tool_id, function_name, err_msg)
            has_errors = True

    # Get the next response after processing all tool calls
    try:
        # Just log to console instead
        print("Getting next response after tool execution...")
        
        # Debug log the messages to understand the current conversation state
        print(f"Messages before follow-up call (count: {len(assistant.messages)}):")
        for i, msg in enumerate(assistant.messages[-3:] if len(assistant.messages) > 3 else assistant.messages):
            # Add safer content handling to prevent None subscript error
            content = msg.get('content', '')
            content_preview = str(content)[:50] if content is not None else "None"
            print(f"  Message {i}: role={msg.get('role')}, content={content_preview}...")
            
            if msg.get('role') == 'tool' and 'tool_call_id' in msg:
                # Also handle potential None content in tool results
                tool_content = msg.get('content', '')
                tool_preview = str(tool_content)[:50] if tool_content is not None else "None" 
                print(f"    Tool result for call {msg.get('tool_call_id')}: {tool_preview}...")

        # Process messages to ensure proper format for Gemini vision models
        processed_messages = preprocess_messages_for_litellm(assistant.messages, assistant.model)
        
        completion_args = {
            "model": assistant.model,
            "messages": processed_messages,  # Use processed messages
            "tools": assistant.tools,
            "temperature": conf.TEMPERATURE,
            "top_p": conf.TOP_P,
            "max_tokens": conf.MAX_TOKENS,
            "seed": conf.SEED,
            "tool_choice": "auto",  # This is important to enable tool selection
            "stream": True  # Always enable streaming for consistent behavior
        }
        safety_settings = getattr(conf, 'SAFETY_SETTINGS', None)
        if safety_settings:
            completion_args["safety_settings"] = safety_settings
            
        completion_args = {k: v for k, v in completion_args.items() if v is not None}
        
        print(f"Making follow-up LiteLLM API call with model: {assistant.model}")
        
        # Add retry logic for API calls
        max_retries = 5  # Maximum number of retry attempts
        base_retry_delay = 1  # Base delay in seconds
        max_retry_delay = 3  # Maximum retry delay in seconds
        
        # Inform the user we're processing the tool results
        if tool_event_callback and recursion_depth == 0:
            # Use special message for image-based inputs
            if has_image_content:
                for chunk in tool_event_callback("info", "Analyzing image and generating response...", False):
                    yield chunk
            else:
                for chunk in tool_event_callback("info", "Processing results and generating response...", False):
                    yield chunk
        
        # Initialize retry variables
        retry_count = 0
        last_error = None
        
        while retry_count <= max_retries:
            try:
                if retry_count > 0:
                    # Calculate exponential backoff with jitter
                    delay = min(base_retry_delay * (2 ** (retry_count - 1)) + (0.1 * random.random()), max_retry_delay)
                    print(f"{Fore.YELLOW}Retry attempt {retry_count}/{max_retries} after {delay:.2f}s delay{Style.RESET_ALL}")
                    
                    # Provide informative message to user via callback
                    retry_msg = f"The model is currently busy. Retrying... (attempt {retry_count}/{max_retries})"
                    if tool_event_callback:
                        for chunk in tool_event_callback("info", retry_msg, True):
                            yield chunk
                    
                    time.sleep(delay)  # Wait before retrying
                
                # Use streaming for recursive calls
                stream = litellm.completion(**completion_args)
                print(f"Follow-up API streaming initialized. Processing stream...")
                
                # Process the stream here directly to enable real-time streaming
                accumulated_content = ""
                accumulated_tool_calls = []
                final_chunk = None
                
                for chunk in stream:
                    # Process each chunk from the stream
                    chunk_content = chunk.choices[0].delta.content
                    chunk_tool_calls = chunk.choices[0].delta.tool_calls
                    
                    if chunk_content:
                        accumulated_content += chunk_content
                        # Stream token in real-time
                        if tool_event_callback:
                            for event in tool_event_callback("token", chunk_content):
                                yield event
                    
                    if chunk_tool_calls:
                        # Process tool calls from the stream (similar to chat_routes.py)
                        for tool_call_delta in chunk_tool_calls:
                            index = tool_call_delta.index
                            if index >= len(accumulated_tool_calls):
                                # New tool call started
                                accumulated_tool_calls.append({
                                    "id": tool_call_delta.id or f"tool_{index}",
                                    "type": "function",
                                    "function": {
                                        "name": tool_call_delta.function.name or "",
                                        "arguments": tool_call_delta.function.arguments or ""
                                    }
                                })
                            else:
                                # Append to existing tool call
                                if tool_call_delta.function.name:
                                    accumulated_tool_calls[index]["function"]["name"] += tool_call_delta.function.name
                                if tool_call_delta.function.arguments:
                                    accumulated_tool_calls[index]["function"]["arguments"] += tool_call_delta.function.arguments
                    
                    final_chunk = chunk  # Keep track of the last chunk
                
                # Create the next_response object from accumulated data
                next_response = {
                    "choices": [{
                        "message": {
                            "role": "assistant",
                            "content": accumulated_content,
                            **({"tool_calls": accumulated_tool_calls} if accumulated_tool_calls else {})
                        },
                        "finish_reason": final_chunk.choices[0].finish_reason if final_chunk else "stop"
                    }],
                    "model": assistant.model
                }
                
                # Successful call, break out of retry loop
                break
                
            except Exception as e:
                last_error = e
                retry_count += 1
                
                # Check if this is a retryable error (503, overloaded model, etc.)
                is_retryable = False
                error_str = str(e).lower()
                
                if "503" in error_str or "service unavailable" in error_str or "overloaded" in error_str:
                    is_retryable = True
                    print(f"{Fore.YELLOW}Retryable error detected: {e}{Style.RESET_ALL}")
                elif "429" in error_str or "rate limit" in error_str or "too many requests" in error_str:
                    is_retryable = True
                    print(f"{Fore.YELLOW}Rate limit error detected: {e}{Style.RESET_ALL}")
                elif "timeout" in error_str or "connection" in error_str or "network" in error_str:
                    is_retryable = True
                    print(f"{Fore.YELLOW}Network error detected: {e}{Style.RESET_ALL}")
                
                if not is_retryable or retry_count > max_retries:
                    print(f"{Fore.RED}Error during follow-up LiteLLM API call (not retrying): {e}{Style.RESET_ALL}")
                    raise
                
                print(f"{Fore.YELLOW}Error during follow-up LiteLLM API call (will retry): {e}{Style.RESET_ALL}")
        
        # If we've exhausted all retries without success
        if 'next_response' not in locals():
            raise Exception(f"API call failed after {max_retries} retries. Last error: {last_error}")
        
        # Process the new response recursively, incrementing the recursion depth
        next_generator = process_tool_calls(
            assistant,
            next_response, 
            print_response=print_response, 
            validation_retries=2,
            recursion_depth=recursion_depth+1,
            tool_event_callback=tool_event_callback
        )
        
        # Pass through all events from the recursive call
        final_text = None
        for event in next_generator:
            if isinstance(event, dict) and "final_text" in event:
                final_text = event["final_text"]
            else:
                yield event
                
        # Yield the final text as a special event
        if final_text is not None:
            yield {"final_text": final_text}
            
        # No need to yield token events here as they're already streamed in real-time above
            
    except Exception as e:
        print(f"{Fore.RED}Error in recursive tool call: {e}. Returning partial results.{Style.RESET_ALL}")
        import traceback
        traceback.print_exc()
        # Return partial results if we encounter an error in the recursive call
        fallback = "Error processing follow-up response. Here's what I know so far."
        yield {"final_text": fallback}
        
        # Stream fallback message if at root recursion level
        if tool_event_callback and recursion_depth == 0:
            for chunk in tool_event_callback("token", fallback):
                yield chunk

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
