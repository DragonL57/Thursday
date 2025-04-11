"""
Streaming response handling for the Assistant
"""

import time
import threading
import json
import traceback
from typing import Optional, List, Dict, Callable, Iterator, Union, Any
from colorama import Fore, Style

import litellm
from .image_processor import optimize_images, process_image_for_gemini, process_image_for_github

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
        self.is_streaming = False
        self.stream_thread = None
        self.stream_abort = False
        self.stream_buffer = []
        
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
            last_token = ""  # Track last token to prevent duplicates
            
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
                            # Check for duplicate tokens
                            if content == last_token:
                                print(f"DEBUG: Skipping duplicate token: '{content}'")
                                continue
                            
                            received_any_content = True
                            accumulated_content += content
                            last_token = content  # Update last token
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
            
            # If accumulated content appears duplicated, fix it
            if accumulated_content and self._is_duplicated_content(accumulated_content):
                print(f"DEBUG: Detected duplicated content in final message, fixing...")
                accumulated_content = self._remove_duplicate_content(accumulated_content)
            
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
    
    def _is_duplicated_content(self, text):
        """Check if content appears duplicated."""
        if not text or len(text) < 20:
            return False
            
        # Check for exact duplicated halves
        half_len = len(text) // 2
        if text[:half_len] == text[half_len:half_len*2]:
            return True
            
        # Check for repeated sentences
        sentences = text.split('. ')
        if len(sentences) >= 2:
            for i in range(len(sentences) - 1):
                if sentences[i] and sentences[i] == sentences[i+1]:
                    return True
                    
        return False

    def _remove_duplicate_content(self, text):
        """Remove duplicated content from text."""
        if not text:
            return text
            
        # Check for exact duplicated halves
        half_len = len(text) // 2
        if text[:half_len] == text[half_len:half_len*2]:
            return text[:half_len]
            
        # Check for repeated sentences and deduplicate
        sentences = text.split('. ')
        if len(sentences) >= 2:
            deduped = []
            for i, sentence in enumerate(sentences):
                if i == 0 or sentence != sentences[i-1]:
                    deduped.append(sentence)
            return '. '.join(deduped)
            
        return text

    def stream_send_message(
        self, message: str, images: Optional[List[Dict]] = None, callback: Optional[Callable] = None
    ) -> Iterator[Dict]:
        """
        Send a message and stream the response with callback for each chunk.
        
        Args:
            message: The message text
            images: Optional list of image data dictionaries
            callback: Optional callback function for each chunk
            
        Yields:
            Dict with event type and data
        """
        # Use the parent assistant's internal state
        assistant = self.assistant
        
        # Clean up any existing stream
        if self.is_streaming:
            self.stream_abort = True
            if self.stream_thread and self.stream_thread.is_alive():
                self.stream_thread.join(0.5)
            self.is_streaming = False
            self.stream_buffer = []
        
        # Reset state for new stream
        self.stream_abort = False
        
        # Reset the streaming flag on the assistant
        assistant._streamed_final_response = False
        
        # Process any provided images
        formatted_images = self._prepare_images(images)
        
        try:
            # Construct user message content with any images
            user_message = self._construct_user_message(message, formatted_images)
            
            # Add the user message to conversation history
            assistant.messages.append(user_message)
            
            # Print debug info about the message
            self._log_message_info(message, formatted_images)
            
            # Mark streaming as active
            self.is_streaming = True
            
            # Yield the start event
            yield {"event": "start"}
            
            # Generate response based on the provider
            if assistant.provider == 'litellm':
                yield from self._handle_litellm_streaming(callback)
            else:  # Use Pollinations API
                yield from self._handle_pollinations_streaming(callback)
                
            # Always send done event
            yield {"event": "done"}
            
        except Exception as e:
            print(f"{Fore.RED}Error in stream_send_message: {str(e)}{Style.RESET_ALL}")
            traceback.print_exc()  # Print full stack trace for debugging
            yield {"event": "error", "data": f"API error: {str(e)}"}
        finally:
            # Mark streaming as done
            self.is_streaming = False
            
    def _prepare_images(self, images):
        """Prepare images for the appropriate model format."""
        if not images:
            return None
            
        # Check provider and model to determine proper formatting
        provider = self.assistant.provider
        model = self.assistant.model
        
        # Special handling for different model families
        if provider == 'litellm':
            if 'gemini' in model:
                print(f"{Fore.YELLOW}Processing image for Gemini model{Style.RESET_ALL}")
                return process_image_for_gemini(images)
            elif 'github' in model:
                print(f"{Fore.YELLOW}Processing image for GitHub model{Style.RESET_ALL}")
                processed = process_image_for_github(images)
                
                if not processed:
                    # If image processing fails for GitHub, don't include the image
                    # and instead append note to the message
                    print(f"{Fore.YELLOW}GitHub models don't support base64 images - removing image from request{Style.RESET_ALL}")
                    # Modify the last message to include a note about image support
                    if self.assistant.messages and len(self.assistant.messages) > 0:
                        last_message = self.assistant.messages[-1]
                        if isinstance(last_message.get('content'), str):
                            note = "\n\n[Note: Images must be provided as public URLs for GitHub models, not as file uploads]"
                            if not last_message['content'].endswith(note):
                                last_message['content'] += note
                
                return processed
            else:
                # Standard optimization for other LiteLLM models
                return optimize_images(images)
        else:
            # Standard optimization for Pollinations
            return optimize_images(images)
            
    def _construct_user_message(self, message, images):
        """Construct the user message with text and optional images."""
        if not images:
            return {"role": "user", "content": message}
            
        # For Gemini with a single image dict
        if isinstance(images, dict) and self.assistant.provider == 'litellm' and 'gemini' in self.assistant.model:
            return {
                "role": "user", 
                "content": [
                    {"type": "text", "text": message},
                    images  # Already in the correct format
                ]
            }
        # For lists of images or other formats
        elif isinstance(images, list):
            content = [{"type": "text", "text": message}]
            content.extend(images)
            return {"role": "user", "content": content}
        # Fall back to a simpler format if needed
        else:
            content = [
                {"type": "text", "text": message},
                {"type": "image_url", "image_url": {"url": images}}
            ]
            return {"role": "user", "content": content}
            
    def _log_message_info(self, message, images):
        """Log debug information about the message being sent."""
        is_multimodal = images is not None
        print(f"{Fore.CYAN}Added {'multimodal' if is_multimodal else 'text-only'} message to history{Style.RESET_ALL}")
        
        # Debug - show what messages we're sending
        print(f"{Fore.CYAN}Sending messages to {self.assistant.provider}:{Style.RESET_ALL}")
        for i, msg in enumerate(self.assistant.messages[-3:]):
            role = msg.get('role', 'unknown')
            content = msg.get('content', '')
            if isinstance(content, list):
                content_types = [f"{p.get('type', 'unknown')}" for p in content if isinstance(p, dict)]
                print(f"  Message {i}: role={role}, content types={content_types}")
            else:
                content_preview = str(content)[:30] + '...' if len(str(content)) > 30 else content
                print(f"  Message {i}: role={role}, content={content_preview}")
                
    def _handle_litellm_streaming(self, callback):
        """Handle streaming with litellm provider."""
        assistant = self.assistant
        
        try:
            # Import config for temperature and other parameters
            import config as conf
            
            # Initialize the stream with all necessary parameters
            completion_args = {
                'model': assistant.model,
                'messages': assistant.messages,
                'tools': assistant.tools,
                'temperature': conf.TEMPERATURE,
                'top_p': conf.TOP_P,
                'max_tokens': conf.MAX_TOKENS,
                'seed': conf.SEED,
                'stream': True  # Always stream for consistency
            }
            
            # Always enable tool_choice for tool use regardless of whether message has images
            completion_args["tool_choice"] = "auto"
            
            # Add safety settings if available
            safety_settings = getattr(conf, 'SAFETY_SETTINGS', None)
            if safety_settings:
                completion_args["safety_settings"] = safety_settings
                
            # Remove None values
            completion_args = {k: v for k, v in completion_args.items() if v is not None}
            
            # Debug info
            print(f"{Fore.CYAN}Starting LiteLLM stream with model: {assistant.model}{Style.RESET_ALL}")
            
            # Add retry logic for empty responses
            max_empty_retries = 3
            retry_count = 0
            content_received = False
            
            while retry_count < max_empty_retries:
                if retry_count > 0:
                    # Inform the user about the retry
                    retry_msg = f"No response received, retrying... (attempt {retry_count + 1}/{max_empty_retries})"
                    print(f"{Fore.YELLOW}{retry_msg}{Style.RESET_ALL}")
                    if callback:
                        callback({"event": "info", "data": retry_msg})
                    
                    # Slightly increase temperature on retries to encourage different responses
                    completion_args['temperature'] = min(1.0, (completion_args.get('temperature', 0.7) + 0.1))
                
                # Start the stream
                stream = litellm.completion(**completion_args)
                
                # Process the stream
                accumulated_content = ""
                accumulated_tool_calls = []
                last_content = None
                chunk_count = 0
                
                for chunk in stream:
                    chunk_count += 1
                    # Check if streaming was aborted
                    if self.stream_abort:
                        print("Stream aborted by user")
                        break
                    
                    if not hasattr(chunk, 'choices') or len(chunk.choices) == 0:
                        continue
                    
                    choice = chunk.choices[0]
                    
                    # Extract content if present
                    delta_content = None
                    try:
                        delta_content = choice.delta.content
                    except (AttributeError, KeyError):
                        pass
                    
                    # Process content if present
                    if delta_content:
                        content_received = True  # Mark that we received some content
                        # Deduplicate identical tokens that sometimes occur in streams
                        if delta_content != last_content:
                            accumulated_content += delta_content
                            yield {"event": "token", "data": delta_content}
                            
                            # Call the callback if provided
                            if callback:
                                callback({"event": "token", "data": delta_content})
                                
                            last_content = delta_content
                    
                    # Process tool calls if present
                    try:
                        if hasattr(choice.delta, 'tool_calls') and choice.delta.tool_calls:
                            content_received = True  # Tool calls also count as content
                            for tool_call_delta in choice.delta.tool_calls:
                                # Process tool call data
                                index = tool_call_delta.index
                                
                                # Handle new tool call
                                if index >= len(accumulated_tool_calls):
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
                                    if hasattr(tool_call_delta, 'function'):
                                        if hasattr(tool_call_delta.function, 'name') and tool_call_delta.function.name:
                                            accumulated_tool_calls[index]["function"]["name"] += tool_call_delta.function.name
                                        if hasattr(tool_call_delta.function, 'arguments') and tool_call_delta.function.arguments:
                                            accumulated_tool_calls[index]["function"]["arguments"] += tool_call_delta.function.arguments
                                        
                                # Check if we have a complete tool call that we can yield
                                if (accumulated_tool_calls[index]["function"]["name"] and
                                    accumulated_tool_calls[index]["function"]["arguments"] and
                                    accumulated_tool_calls[index]["function"]["arguments"].strip().endswith('}')):
                                    try:
                                        # Parse the arguments as JSON to validate completeness
                                        args_str = accumulated_tool_calls[index]["function"]["arguments"]
                                        if args_str.strip():
                                            json.loads(args_str)
                                            
                                        # Create tool call data format compatible with UI expectations
                                        tool_data = {
                                            "id": accumulated_tool_calls[index]["id"],
                                            "name": accumulated_tool_calls[index]["function"]["name"],
                                            "args": accumulated_tool_calls[index]["function"]["arguments"],
                                            "status": "pending",
                                            "result": None
                                        }
                                        
                                        # Yield the tool call event
                                        yield {"event": "tool_call", "data": tool_data}
                                        
                                        # Call the callback if provided
                                        if callback:
                                            callback({"event": "tool_call", "data": tool_data})
                                            
                                    except json.JSONDecodeError:
                                        # Arguments not complete yet, keep accumulating
                                        pass
                    except (AttributeError, KeyError) as e:
                        print(f"Warning: Error processing tool call: {e}")
                        pass
                
                # Check if we received any content
                if content_received:
                    # We got content, process it and break the retry loop
                    break
                elif chunk_count == 0:
                    # No chunks received at all, likely an API error
                    print(f"{Fore.RED}No response chunks received from API{Style.RESET_ALL}")
                    retry_count += 1
                    if retry_count >= max_empty_retries:
                        raise Exception("Failed to get any response after multiple retries")
                    continue
                else:
                    # Got chunks but no content, might be incomplete response
                    print(f"{Fore.YELLOW}Got {chunk_count} chunks but no content{Style.RESET_ALL}")
                    retry_count += 1
                    if retry_count >= max_empty_retries:
                        raise Exception("Received empty responses after multiple retries")
                    continue
                
            # Process the end of stream
            if accumulated_content:
                # Add the assistant's response to the conversation history if it's not already there
                content_already_added = False
                for msg in assistant.messages[-3:]:
                    if msg.get('role') == 'assistant' and msg.get('content') == accumulated_content:
                        content_already_added = True
                        break
                        
                if not content_already_added:
                    assistant.messages.append({"role": "assistant", "content": accumulated_content})
                
                # Set the final response
                assistant._final_response = accumulated_content
                
                # Mark that we've streamed the final response
                assistant._streamed_final_response = True
                
                # Send final event
                yield {"event": "final", "data": accumulated_content}
                
                # Call the callback with final response
                if callback:
                    callback({"event": "final", "data": accumulated_content})
            
            # Process tool calls if they weren't already processed during streaming
            if accumulated_tool_calls:
                # Add the tool calls to the message
                message_with_tool_calls = {
                    "role": "assistant",
                    "content": accumulated_content or "",
                    "tool_calls": accumulated_tool_calls
                }
                
                # Check if we've already added this exact message to avoid duplicates
                already_added = False
                for msg in assistant.messages[-3:]:
                    if (msg.get('role') == 'assistant' and 
                        msg.get('content') == message_with_tool_calls.get('content') and
                        'tool_calls' in msg):
                        already_added = True
                        break
                
                # Only add if not already added
                if not already_added:
                    assistant.messages.append(message_with_tool_calls)
                
                # Add tool calls to current_tool_calls for processing
                for tool_call in accumulated_tool_calls:
                    # Skip already processed tool calls
                    tool_id = tool_call["id"]
                    if any(tc["id"] == tool_id for tc in assistant.current_tool_calls):
                        continue
                        
                    assistant.current_tool_calls.append({
                        "id": tool_call["id"],
                        "name": tool_call["function"]["name"],
                        "args": tool_call["function"]["arguments"],
                        "status": "pending",
                        "result": None
                    })
                    
                # If we only received tool calls but no content, make sure UI knows we're processing tools
                if not accumulated_content and callback:
                    yield {"event": "info", "data": "Processing image using tools...", "temporary": True}
                    
        except Exception as e:
            print(f"{Fore.RED}LiteLLM completion error: {str(e)}{Style.RESET_ALL}")
            traceback.print_exc()
            yield {"event": "error", "data": f"API error: {str(e)}"}
            
    def _handle_pollinations_streaming(self, callback):
        """Handle streaming with Pollinations API provider."""
        assistant = self.assistant
        
        # Verify API client is initialized
        if not assistant.api_client:
            error = "Pollinations API client not initialized"
            yield {"event": "error", "data": f"API error: {error}"}
            return
        
        try:
            # Start streaming
            api_stream = assistant.api_client.stream_get_completion(
                messages=assistant.messages,
                tools=assistant.tools
            )
            
            # Process the stream
            for chunk in api_stream:
                # Check if streaming was aborted
                if self.stream_abort:
                    print("Stream aborted by user")
                    break
                    
                # Process content chunks
                if "content" in chunk:
                    content = chunk["content"]
                    yield {"event": "token", "data": content}
                    
                    # Call the callback if provided
                    if callback:
                        callback({"event": "token", "data": content})
                        
            # Add the final message from the API client
            final_message = assistant.api_client.last_completion_content
            if final_message:
                # Add the assistant's response to the conversation history
                assistant.messages.append({"role": "assistant", "content": final_message})
                
                # Final response
                yield {"event": "final", "data": final_message}
                
                # Call the callback with final response
                if callback:
                    callback({"event": "final", "data": final_message})
                    
        except Exception as e:
            print(f"{Fore.RED}Pollinations API error: {str(e)}{Style.RESET_ALL}")
            yield {"event": "error", "data": f"API error: {str(e)}"}
