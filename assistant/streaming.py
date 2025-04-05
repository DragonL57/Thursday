"""
Streaming response handling for the Assistant
"""

import json
import traceback
from colorama import Fore, Style

class StreamHandler:
    """
    Handles streaming responses from the API
    """
    
    def __init__(self, assistant):
        """
        Initialize the stream handler.
        
        Args:
            assistant: The Assistant instance that owns this stream handler
        """
        self.assistant = assistant
        
    def stream_get_next_response(self, callback=None):
        """
        Get the next response after executing tools.
        This is used for recursive tool call handling.
        
        Args:
            callback: Function to call for each token, tool call, etc.
                     Should accept parameters: (event_type, data)
        
        Returns:
            Generator yielding response chunks
        """
        try:
            # Make a completion request to get the next response
            print(f"DEBUG: stream_get_next_response called with {len(self.assistant.messages)} messages in history")
            
            # Log the most recent messages to understand context
            print(f"DEBUG: Last few messages in conversation history:")
            for i, msg in enumerate(self.assistant.messages[-3:]):
                role = msg.get('role', 'unknown')
                content = msg.get('content', '')
                content_preview = str(content)[:50] + '...' if isinstance(content, str) and len(content) > 50 else content
                print(f"  Message {i}: role={role}, content={content_preview}")
            
            # Make streaming request for a more responsive experience
            print(f"DEBUG: Making API request for recursive call")
            response = self.assistant.api_client._make_api_request(
                messages=self.assistant.messages,
                tools=self.assistant.tools,
                stream=True
            )
            
            # Check if response is None (which can happen if the API call failed)
            if response is None:
                error_msg = "Failed to get a response from the API server"
                print(f"{Fore.RED}ERROR: Error in streaming: {error_msg}{Style.RESET_ALL}")
                
                # Add a fallback response in case of errors
                fallback_response = "I've processed the information, but couldn't get a response from the server."
                self.assistant._final_response = fallback_response
                
                if callback:
                    for chunk in callback("error", error_msg):
                        yield chunk
                    for chunk in callback("token", fallback_response):
                        yield chunk
                return
            
            print(f"DEBUG: Got API response object for recursive call")
            
            # Process the streaming response
            accumulated_content = ""
            accumulated_tool_calls = []
            tool_call_in_progress = None
            
            # Track if we received any content to determine if a follow-up response is needed
            received_any_content = False
            chunks_processed = 0
            
            print(f"DEBUG: Starting to process streaming response chunks")
            for line in response.iter_lines():
                chunks_processed += 1
                if not line:
                    continue
                    
                if line.startswith(b'data: '):
                    data = line[6:].decode('utf-8')
                    
                    # Check for end of stream
                    if data == "[DONE]":
                        print(f"DEBUG: Received [DONE] marker after {chunks_processed} chunks")
                        if callback:
                            for chunk in callback("done", None):
                                yield chunk
                        break
                    
                    try:
                        chunk = json.loads(data)
                        # Safety check to ensure choices exists and has at least one item
                        if not chunk.get('choices') or len(chunk.get('choices', [])) == 0:
                            print(f"WARNING: Received chunk with no choices: {chunk}")
                            continue
                            
                        delta = chunk.get('choices', [{}])[0].get('delta', {})
                        
                        # Handle content chunks
                        content = delta.get('content', '')
                        if content:
                            received_any_content = True
                            accumulated_content += content
                            print(f"DEBUG: Received content token: '{content}'")
                            # Call callback immediately with each token as it arrives
                            if callback:
                                for chunk in callback("token", content):
                                    yield chunk
                        
                        # Handle role (marks beginning of message)
                        role = delta.get('role')
                        if role:
                            # A new message is starting
                            print(f"DEBUG: Starting new message with role: {role}")
                        
                        # Handle tool call chunks
                        tool_calls = delta.get('tool_calls', [])
                        if tool_calls and len(tool_calls) > 0:
                            # Process each tool call update
                            tool_call = tool_calls[0]  # Take first for simplicity
                            print(f"DEBUG: Received tool call chunk: {tool_call}")
                            
                            # Process tool call ID (start of a new tool call)
                            if 'id' in tool_call:
                                tool_call_id = tool_call.get('id')
                                if tool_call_id:
                                    tool_call_in_progress = {
                                        'id': tool_call_id,
                                        'function': {
                                            'name': '',
                                            'arguments': ''
                                        }
                                    }
                                    print(f"DEBUG: Started new tool call with ID: {tool_call_id}")
                            
                            # Process function name
                            if 'function' in tool_call and 'name' in tool_call['function']:
                                if tool_call_in_progress:
                                    tool_call_in_progress['function']['name'] = tool_call['function']['name']
                                    print(f"DEBUG: Tool call function name: {tool_call['function']['name']}")
                            
                            # Process function arguments
                            if 'function' in tool_call and 'arguments' in tool_call['function']:
                                if tool_call_in_progress:
                                    args = tool_call['function']['arguments']
                                    tool_call_in_progress['function']['arguments'] += args
                                    print(f"DEBUG: Added argument chunk: {args}")
                                    
                                    # Check if we have complete JSON
                                    if args.endswith('}'):
                                        try:
                                            # Try to parse to validate completeness
                                            args_str = tool_call_in_progress['function']['arguments']
                                            if not args_str.strip():
                                                args_str = '{}'
                                                
                                            json.loads(args_str)  # Just to validate JSON
                                            print(f"DEBUG: Completed tool call arguments: {args_str}")
                                            
                                            # Create the tool call data for the callback
                                            tool_call_data = {
                                                'id': tool_call_in_progress['id'],
                                                'name': tool_call_in_progress['function']['name'],
                                                'args': args_str,
                                                'status': 'pending'
                                            }
                                            
                                            # Add to accumulated tool calls
                                            accumulated_tool_calls.append(tool_call_in_progress)
                                            print(f"DEBUG: Added complete tool call to accumulated_tool_calls")
                                            
                                            # Add to the current tool calls for the assistant
                                            self.assistant.current_tool_calls.append({
                                                'id': tool_call_data['id'],
                                                'name': tool_call_data['name'],
                                                'args': tool_call_data['args'],
                                                'status': 'pending',
                                                'result': None
                                            })
                                            print(f"DEBUG: Added tool call to assistant.current_tool_calls")
                                            
                                            # Call the callback with the tool call
                                            if callback:
                                                print(f"DEBUG: Calling callback with tool_call event")
                                                for chunk in callback("tool_call", tool_call_data):
                                                    yield chunk
                                            
                                            # Reset tool call in progress
                                            tool_call_in_progress = None
                                        except json.JSONDecodeError as e:
                                            # Arguments not complete yet
                                            print(f"DEBUG: JSON not complete yet: {e}")
                                            pass
                    except json.JSONDecodeError:
                        print(f"ERROR: Error parsing streaming chunk: {data}")
            
            # End of streaming
            print(f"DEBUG: Finished processing {chunks_processed} streaming chunks")
            print(f"DEBUG: Accumulated content: '{accumulated_content}'")
            print(f"DEBUG: Accumulated tool calls: {len(accumulated_tool_calls)}")
            
            # Final message processing
            if accumulated_content:
                # Add assistant message to history if we got content
                print(f"DEBUG: Adding assistant message with content to history")
                self.assistant.messages.append({
                    "role": "assistant",
                    "content": accumulated_content
                })
                # Store the final response
                self.assistant._final_response = accumulated_content
            elif accumulated_tool_calls:
                # Add assistant message with tool calls to history
                print(f"DEBUG: Adding assistant message with tool calls to history")
                self.assistant.messages.append({
                    "role": "assistant",
                    "content": "",
                    "tool_calls": accumulated_tool_calls
                })
            
            # If we didn't get any content, send a synthetic response to ensure continuity
            if not received_any_content and not accumulated_tool_calls and callback:
                fallback_response = "Here's the information I found based on the tool results."
                print(f"DEBUG: No content received, using fallback response: '{fallback_response}'")
                self.assistant._final_response = fallback_response
                
                # Add a synthetic message if needed
                if not any(msg.get("role") == "assistant" and msg.get("content") for msg in self.assistant.messages[-3:]):
                    print(f"DEBUG: Adding synthetic assistant message to history")
                    self.assistant.messages.append({
                        "role": "assistant", 
                        "content": fallback_response
                    })
                
                # Send this as a token for the client to display
                if callback:
                    for chunk in callback("info", "Creating response from tool results..."):
                        yield chunk
                    for chunk in callback("token", fallback_response):
                        yield chunk
            
        except Exception as e:
            error_msg = f"Error getting next response after tool execution: {e}"
            print(f"{Fore.RED}ERROR: {error_msg}{Style.RESET_ALL}")
            traceback.print_exc()  # Print the full stack trace
            
            # Add a fallback response in case of errors
            fallback_response = "I've processed the information, but encountered an error generating a response."
            self.assistant._final_response = fallback_response
            
            if callback:
                for chunk in callback("error", str(e)):
                    yield chunk
                for chunk in callback("token", fallback_response):
                    yield chunk
    
    def stream_send_message(self, message, images=None, callback=None):
        """
        Send a message and stream the response with callback for each chunk.
        
        Args:
            message: The text message to send
            images: Optional list of image data
            callback: Function to call with each token or tool call
                     Should accept parameters: (event_type, data) and yield the formatted events
                     
        Returns:
            Generator yielding SSE formatted events
        """
        from .image_processor import optimize_images
        
        # Clear any previous tool calls and image data
        self.assistant.current_tool_calls = []
        self.assistant.image_data = []
        
        # If images are provided, optimize and store them
        if images:
            self.assistant.image_data = optimize_images(images)
        
        # Prepare the content array if images are present
        if self.assistant.image_data:
            print(f"DEBUG: Adding user message with {len(self.assistant.image_data)} images")
            content = [{"type": "text", "text": message}]
            content.extend(self.assistant.image_data)
            # Add user message with content array
            self.assistant.messages.append({"role": "user", "content": content})
        else:
            # Add simple text message
            print(f"DEBUG: Adding user message with text only")
            self.assistant.messages.append({"role": "user", "content": message})
        
        # Generator to yield tokens in real-time
        def stream_generator():
            try:
                # Make streaming request
                print(f"DEBUG: Making initial API streaming request")
                response = self.assistant.api_client._make_api_request(
                    messages=self.assistant.messages,
                    tools=self.assistant.tools,
                    stream=True
                )
                
                # Check if response is None (which can happen if the API call failed)
                if response is None:
                    error_msg = "Failed to get a response from the API server"
                    print(f"{Fore.RED}ERROR: Error in streaming: {error_msg}{Style.RESET_ALL}")
                    self.assistant._final_response = f"Error during streaming: {error_msg}"
                    
                    # Send error notification
                    if callback:
                        for chunk in callback("error", error_msg):
                            yield chunk
                    return
                
                print(f"DEBUG: Got API response object for initial request")
                
                # Process SSE stream
                accumulated_content = ""
                accumulated_tool_calls = []
                current_tool_call = None
                
                chunk_count = 0
                print(f"DEBUG: Starting to process streaming response chunks")
                for line in response.iter_lines():
                    chunk_count += 1
                    if not line:
                        continue
                        
                    if line.startswith(b'data: '):
                        data = line[6:].decode('utf-8')
                        
                        # Check for end of stream
                        if data == "[DONE]":
                            print(f"DEBUG: Received [DONE] marker after {chunk_count} chunks")
                            if callback:
                                for chunk in callback("done", None):
                                    yield chunk
                            break
                        
                        try:
                            chunk = json.loads(data)
                            # Safety check to ensure choices exists and has at least one item
                            if not chunk.get('choices') or len(chunk.get('choices', [])) == 0:
                                print(f"WARNING: Received chunk with no choices: {chunk}")
                                continue
                                
                            delta = chunk.get('choices', [{}])[0].get('delta', {})
                            
                            # Handle content chunks
                            content = delta.get('content', '')
                            if content:
                                accumulated_content += content
                                print(f"DEBUG: Received content token: '{content}'")
                                # Call callback immediately with each token as it arrives
                                if callback:
                                    for chunk in callback("token", content):
                                        yield chunk
                            
                            # Handle tool call chunks
                            tool_calls = delta.get('tool_calls', [])
                            if tool_calls:
                                # Safely check if tool_calls has items before accessing index 0
                                if len(tool_calls) > 0:
                                    tool_call = tool_calls[0]  # Process one at a time for simplicity
                                    print(f"DEBUG: Tool call chunk: {tool_call}")
                                    
                                    # Initialize tool call if it's new
                                    tool_id = tool_call.get('id')
                                    function_name = tool_call.get('function', {}).get('name')
                                    
                                    if tool_id and not current_tool_call:
                                        current_tool_call = {
                                            'id': tool_id,
                                            'function': {
                                                'name': function_name if function_name else "",
                                                'arguments': ""
                                            }
                                        }
                                        print(f"DEBUG: Started new tool call with ID {tool_id}")
                                        
                                        # Immediately notify about new tool call
                                        if callback:
                                            for chunk in callback("tool_call", current_tool_call):
                                                yield chunk
                                    
                                    # Update the tool call with new information
                                    if function_name and current_tool_call:
                                        current_tool_call['function']['name'] = function_name
                                        print(f"DEBUG: Updated tool call function name: {function_name}")
                                    
                                    # Accumulate arguments
                                    args = tool_call.get('function', {}).get('arguments', '')
                                    if args and current_tool_call:
                                        current_tool_call['function']['arguments'] += args
                                        print(f"DEBUG: Added argument chunk: {args}")
                                    
                                    # Check if this is the end of a tool call (complete arguments)
                                    if args and current_tool_call and (args.endswith('}') or args.strip() == '}'):
                                        try:
                                            # Validate JSON completeness
                                            args_str = current_tool_call['function']['arguments']
                                            args_obj = json.loads(args_str)
                                            print(f"DEBUG: Complete valid JSON arguments: {args_str}")
                                            
                                            # Add to local tracking
                                            accumulated_tool_calls.append(current_tool_call)
                                            
                                            # Add to assistant tracking for future reference
                                            self.assistant.current_tool_calls.append({
                                                "id": current_tool_call["id"],
                                                "name": current_tool_call["function"]["name"],
                                                "args": current_tool_call["function"]["arguments"],
                                                "status": "pending",
                                                "result": None
                                            })
                                            print(f"DEBUG: Added complete tool call to tracking")
                                            
                                            # Notify about the complete tool call
                                            if callback:
                                                # Get the processed version with id, name, args
                                                tool_call_processed = {
                                                    "id": current_tool_call["id"],
                                                    "name": current_tool_call["function"]["name"],
                                                    "args": current_tool_call["function"]["arguments"],
                                                    "status": "pending"
                                                }
                                                print(f"DEBUG: Sending tool_call event to callback")
                                                for chunk in callback("tool_call", tool_call_processed):
                                                    yield chunk
                                            
                                            # Process the tool call
                                            try:
                                                # Get the tool function
                                                function_name = current_tool_call["function"]["name"]
                                                function_args_str = current_tool_call["function"]["arguments"]
                                                function_args = json.loads(function_args_str)
                                                function_to_call = self.assistant.available_functions.get(function_name)
                                                
                                                if function_to_call:
                                                    # Execute the function
                                                    print(f"DEBUG: Executing function {function_name}")
                                                    tool_result = function_to_call(**function_args)
                                                    print(f"DEBUG: Function executed successfully")
                                                    
                                                    # Update tool call result
                                                    for tc in self.assistant.current_tool_calls:
                                                        if tc["id"] == current_tool_call["id"]:
                                                            tc["status"] = "completed"
                                                            tc["result"] = str(tool_result)
                                                            
                                                            # Send tool update notification
                                                            if callback:
                                                                print(f"DEBUG: Sending tool_update event to callback")
                                                                for chunk in callback("tool_update", tc):
                                                                    yield chunk
                                                            
                                                            # Add tool result to message history
                                                            print(f"DEBUG: Adding tool result to message history")
                                                            self.assistant.add_toolcall_output(
                                                                tc["id"], 
                                                                function_name, 
                                                                str(tool_result)
                                                            )
                                                            break
                                            except Exception as e:
                                                # Handle errors in tool execution
                                                error_message = f"Error executing tool {function_name}: {str(e)}"
                                                print(f"ERROR: {error_message}")
                                                traceback.print_exc()
                                                
                                                # Update tool call with error
                                                for tc in self.assistant.current_tool_calls:
                                                    if tc["id"] == current_tool_call["id"]:
                                                        tc["status"] = "error"
                                                        tc["result"] = error_message
                                                        
                                                        # Send tool update notification
                                                        if callback:
                                                            print(f"DEBUG: Sending tool_update event with error")
                                                            for chunk in callback("tool_update", tc):
                                                                yield chunk
                                                        
                                                        # Add error to message history
                                                        print(f"DEBUG: Adding error to message history")
                                                        self.assistant.add_toolcall_output(
                                                            tc["id"], 
                                                            function_name, 
                                                            error_message
                                                        )
                                                        break
                                            
                                            # Reset current tool call
                                            current_tool_call = None
                                            
                                        except json.JSONDecodeError:
                                            # Arguments not complete yet, continue accumulating
                                            pass
                                
                        except json.JSONDecodeError:
                            print(f"ERROR: Error parsing streaming chunk: {data}")
                
                # Process the final response after streaming
                print(f"DEBUG: Finished initial streaming response processing")
                print(f"DEBUG: Accumulated content: '{accumulated_content}'")
                print(f"DEBUG: Accumulated tool calls: {len(accumulated_tool_calls)}")
                
                # After processing all tool calls, attempt to generate a response
                if accumulated_tool_calls:
                    print(f"DEBUG: We had {len(accumulated_tool_calls)} tool calls. Need to get a follow-up response")
                    print(f"DEBUG: Message history now has {len(self.assistant.messages)} messages")
                    
                    # Need to make the recursive call to get a response after tool call execution
                    # This is important! Without this, we won't get a text response after tools.
                    print(f"DEBUG: Making recursive stream_get_next_response call")
                    try:
                        recursive_streamer = self.stream_get_next_response(callback)
                        if recursive_streamer:
                            print(f"DEBUG: Processing chunks from recursive call")
                            chunk_count = 0
                            for chunk in recursive_streamer:
                                chunk_count += 1
                                yield chunk
                            print(f"DEBUG: Processed {chunk_count} chunks from recursive call")
                        else:
                            print(f"ERROR: recursive_streamer was None!")
                    except Exception as e:
                        print(f"ERROR: Failed to make recursive call: {e}")
                        traceback.print_exc()
                
                # Store the response
                self.assistant._final_response = accumulated_content
                
            except Exception as e:
                print(f"{Fore.RED}ERROR: Error in streaming: {e}{Style.RESET_ALL}")
                traceback.print_exc()  # Print the full stack trace
                self.assistant._final_response = f"Error during streaming: {str(e)}"
                
                # Send error notification
                if callback:
                    for chunk in callback("error", str(e)):
                        yield chunk
        
        # Return the generator directly
        return stream_generator()
