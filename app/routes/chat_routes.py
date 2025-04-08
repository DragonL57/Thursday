"""
Chat-related routes for the application
"""

from flask import Blueprint, jsonify, request, session, Response, current_app, g
import json
import traceback
import litellm # Add litellm import
import os
from assistant import Assistant
import config as conf
from tools import formatting, TOOLS
from assistant.tool_handler import process_tool_calls
from app.utils.helpers import chunk_text
from utils.provider_manager import ProviderManager

chat_bp = Blueprint('chat', __name__)

@chat_bp.route('/stream', methods=['POST'])
def chat_stream():
    """Streaming endpoint for chat messages."""
    if not current_app.assistant:
        return jsonify({"error": "Assistant not initialized"}), 500

    try:
        # Initialize provider manager
        ProviderManager.initialize()
        
        user_message = request.json.get('message')
        image_data = request.json.get('imageData')
        
        if not user_message and not image_data:
            return jsonify({"error": "No message or image provided"}), 400

        # Get session ID (or client IP if no session available)
        session_id = session.get('user_id', request.remote_addr)
        
        # Determine whether to use integrated GPT-4o mode
        use_integrated_model = conf.MODEL == "gpt4o-integrated"
        
        # Get appropriate provider and model based on our fallback strategy
        if use_integrated_model:
            provider, model_name = ProviderManager.get_provider_and_model('gpt4o')
            print(f"Using provider {provider} with model {model_name}")
        else:
            # Use configured provider and model
            provider = getattr(conf, 'API_PROVIDER', 'pollinations')
            model_name = conf.MODEL
        
        # Create or get user-specific assistant instance
        if session_id not in current_app.assistants:
            current_app.assistants[session_id] = Assistant(
                model=model_name,
                system_instruction=conf.get_system_prompt().strip(),
                tools=TOOLS  # Use the imported TOOLS directly
            )
            # Set the correct provider based on fallback strategy
            if use_integrated_model:
                current_app.assistants[session_id].update_provider(provider)
        else:
            # Update existing assistant with current model and provider
            current_app.assistants[session_id].model = model_name
            if use_integrated_model:
                current_app.assistants[session_id].update_provider(provider)
        
        user_assistant = current_app.assistants[session_id]
        
        # Prepare image data if provided
        images = None
        if image_data:
            # Create the content array format required by the API
            images = [{
                "type": "image_url",
                "image_url": {
                    "url": image_data
                }
            }]
            
        def generate():
            # Send start event
            yield f"data: {json.dumps({'event': 'start'})}\n\n"
            
            # Reset notes for the new message
            from tools.notes import reset_notes
            reset_notes()
            
            # Add user message to assistant's conversation history - only if there's content
            if user_message or images:
                user_assistant.messages.append({
                    "role": "user",
                    "content": user_message if not images else [
                        {"type": "text", "text": user_message},
                        *images
                    ]
                })
            
            # Create tool tracking list for this conversation
            user_assistant.current_tool_calls = []
            
            # Track tool calls by function name+args to prevent duplicates
            seen_tool_calls = set()
            
            # Save original tool_report_print function
            from tools.formatting import tool_report_print as original_print
            
            # Define the monkey-patched function
            def patched_tool_report(msg, value, is_error=False):
                # Call the original function
                original_print(msg, value, is_error)
                
                # Process tool execution start
                if msg.startswith("Running tool:"):
                    tool_info = value.strip()
                    if '(' in tool_info and ')' in tool_info:
                        tool_name = tool_info.split('(')[0].strip()
                        args_part = tool_info[tool_info.find('(')+1:tool_info.rfind(')')]
                        
                        # Create a signature to detect duplicates
                        tool_signature = f"{tool_name}:{args_part}"
                        
                        # Skip if we've already seen this exact tool call
                        if tool_signature in seen_tool_calls:
                            print(f"Skipping duplicate tool call: {tool_signature}")
                            return None
                            
                        seen_tool_calls.add(tool_signature)
                        
                        # Create unique tool ID
                        tool_id = f"tool_{len(user_assistant.current_tool_calls) + 1}"
                        
                        tool_data = {
                            "id": tool_id,
                            "name": tool_name,
                            "args": args_part,
                            "status": "pending",
                            "result": None
                        }
                        
                        # Store tool call data
                        user_assistant.current_tool_calls.append(tool_data)
                        
                        # Stream tool call event immediately rather than buffering
                        event_data = f"data: {json.dumps({'event': 'tool_call', 'data': tool_data})}\n\n"
                        yield event_data
                        return event_data
                
                # Process tool execution completion
                elif msg == "Result:":
                    if user_assistant.current_tool_calls:
                        # Get the most recent tool call
                        tool_call = user_assistant.current_tool_calls[-1]
                        tool_id = tool_call["id"]
                        
                        # Track if this result is empty
                        result_str = str(value)
                        is_empty_result = not result_str or result_str.strip() == '""'
                        
                        # Update the tool call result
                        if is_empty_result:
                            tool_call["result"] = "No meaningful content could be extracted from this website."
                        else:
                            tool_call["result"] = result_str
                            
                        tool_call["status"] = "completed" if "Error" not in str(value) else "error"
                        
                        # Stream tool update event immediately rather than buffering
                        event_data = f"data: {json.dumps({'event': 'tool_update', 'data': tool_call})}\n\n"
                        yield event_data
                        return event_data
                
                return None
            
            # Apply monkey patch
            from tools import formatting
            formatting.tool_report_print = patched_tool_report
            
            try:
                # Print some debug info
                print(f"Processing message: '{user_message}' using provider: {user_assistant.provider}")

                # Special handling for GitHub models to ensure API key is set
                if user_assistant.provider == 'litellm' and user_assistant.model.startswith('github/'):
                    # Check and set GitHub API key if needed
                    if not os.environ.get('GITHUB_API_KEY') and hasattr(conf, 'GITHUB_API_KEY') and conf.GITHUB_API_KEY:
                        os.environ['GITHUB_API_KEY'] = conf.GITHUB_API_KEY
                        print("Set GitHub API key from config")

                # Get initial API response based on provider
                try:
                    if user_assistant.provider == 'pollinations':
                        if not user_assistant.api_client:
                             raise ValueError("Pollinations provider selected but api_client is not initialized.")
                        response = user_assistant.api_client.get_completion(
                            messages=user_assistant.messages,
                            tools=user_assistant.tools
                            # Note: Pollinations client might not support stream=True directly here
                            # The streaming logic might need adjustment if Pollinations streaming is desired
                        )
                    elif user_assistant.provider == 'litellm':
                         # Prepare args for litellm completion
                        completion_args = {
                            "model": user_assistant.model,
                            "messages": user_assistant.messages,
                            "tools": user_assistant.tools,
                            "temperature": conf.TEMPERATURE,
                            "top_p": conf.TOP_P,
                            "max_tokens": conf.MAX_TOKENS,
                            "seed": conf.SEED,
                            "stream": True # Ensure streaming is enabled for litellm
                        }
                        safety_settings = getattr(conf, 'SAFETY_SETTINGS', None)
                        if safety_settings:
                            completion_args["safety_settings"] = safety_settings
                        completion_args = {k: v for k, v in completion_args.items() if v is not None}

                        # Call litellm directly for streaming
                        # The response here will be a generator/stream object
                        response_stream = litellm.completion(**completion_args)

                        # --- Handling LiteLLM Stream ---
                        # We need to process the stream differently than the Pollinations response
                        accumulated_content = ""
                        accumulated_tool_calls = []
                        final_chunk = None

                        for chunk in response_stream:
                            # Process each chunk from the litellm stream
                            chunk_content = chunk.choices[0].delta.content
                            chunk_tool_calls = chunk.choices[0].delta.tool_calls

                            if chunk_content:
                                accumulated_content += chunk_content
                                yield f"data: {json.dumps({'event': 'token', 'data': chunk_content})}\n\n"

                            if chunk_tool_calls:
                                # Process tool calls from the stream delta
                                for tool_call_delta in chunk_tool_calls:
                                    # Accumulate tool call info (LiteLLM streams tool calls incrementally)
                                    index = tool_call_delta.index
                                    if index >= len(accumulated_tool_calls):
                                        # New tool call started
                                        accumulated_tool_calls.append({
                                            "id": tool_call_delta.id or f"tool_{index}", # Assign ID if missing
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

                            final_chunk = chunk # Keep track of the last chunk for finish reason etc.

                        # --- After LiteLLM Stream Ends ---
                        # For LiteLLM streaming, we've already sent the content tokens
                        # We only need to construct a response for tool call processing
                        response = {
                            "choices": [{
                                "message": {
                                    "role": "assistant",
                                    # Don't include content since we've already streamed it
                                    "content": "",
                                    # Add accumulated tool calls if any
                                    **({"tool_calls": accumulated_tool_calls} if accumulated_tool_calls else {})
                                },
                                "finish_reason": final_chunk.choices[0].finish_reason if final_chunk else "stop"
                            }],
                            "model": user_assistant.model
                        }

                        # Send final event with accumulated content
                        if accumulated_content:
                            yield f"data: {json.dumps({'event': 'final', 'data': accumulated_content})}\n\n"
                    else:
                         raise ValueError(f"Unsupported provider: {user_assistant.provider}")
                    
                    # If we got here, the request succeeded - try switching back to primary provider
                    if use_integrated_model and user_assistant.provider == ProviderManager.LITELLM:
                        # On next message, try going back to Pollinations
                        ProviderManager.should_use_primary('gpt4o')
                    
                except Exception as e:
                    error_msg = str(e)
                    status_code = getattr(e, 'status_code', None)
                    
                    # Check for rate limiting errors and switch to fallback if needed
                    if use_integrated_model and (status_code == 429 or "rate" in error_msg.lower() and "limit" in error_msg.lower()):
                        print(f"Rate limited by {user_assistant.provider}. Switching to fallback provider...")
                        
                        if user_assistant.provider == ProviderManager.POLLINATIONS:
                            # Switch to litellm/github provider
                            fallback = ProviderManager.handle_rate_limit('gpt4o')
                            
                            if fallback:
                                # Update assistant
                                user_assistant.model = fallback['model_name']
                                user_assistant.update_provider(fallback['provider'])
                                
                                # Retry with new provider
                                yield f"data: {json.dumps({'event': 'info', 'data': 'Switching to backup provider due to rate limiting...'})}\n\n"
                                
                                # Recursively retry the request with new provider
                                if user_assistant.provider == 'litellm':
                                    # Use LiteLLM's completion
                                    completion_args = {
                                        "model": user_assistant.model,
                                        "messages": user_assistant.messages,
                                        "tools": user_assistant.tools,
                                        "temperature": conf.TEMPERATURE,
                                        "top_p": conf.TOP_P,
                                        "max_tokens": conf.MAX_TOKENS,
                                        "seed": conf.SEED,
                                        "stream": True
                                    }
                                    safety_settings = getattr(conf, 'SAFETY_SETTINGS', None)
                                    if safety_settings:
                                        completion_args["safety_settings"] = safety_settings
                                    completion_args = {k: v for k, v in completion_args.items() if v is not None}
                                    
                                    # Ensure GitHub API key is set
                                    if not os.environ.get('GITHUB_API_KEY') and hasattr(conf, 'GITHUB_API_KEY') and conf.GITHUB_API_KEY:
                                        os.environ['GITHUB_API_KEY'] = conf.GITHUB_API_KEY
                                        
                                    response_stream = litellm.completion(**completion_args)
                                    
                                    # Process stream same as before
                                    accumulated_content = ""
                                    accumulated_tool_calls = []
                                    final_chunk = None
                                    
                                    for chunk in response_stream:
                                        # Process each chunk from the litellm stream
                                        chunk_content = chunk.choices[0].delta.content
                                        chunk_tool_calls = chunk.choices[0].delta.tool_calls

                                        if chunk_content:
                                            accumulated_content += chunk_content
                                            yield f"data: {json.dumps({'event': 'token', 'data': chunk_content})}\n\n"

                                        if chunk_tool_calls:
                                            # Same tool call handling as before
                                            for tool_call_delta in chunk_tool_calls:
                                                # Accumulate tool call info
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

                                        final_chunk = chunk # Keep track of the last chunk
                                    
                                    # Construct response for tool call processing
                                    response = {
                                        "choices": [{
                                            "message": {
                                                "role": "assistant",
                                                "content": "",
                                                **({"tool_calls": accumulated_tool_calls} if accumulated_tool_calls else {})
                                            },
                                            "finish_reason": final_chunk.choices[0].finish_reason if final_chunk else "stop"
                                        }],
                                        "model": user_assistant.model
                                    }

                                    # Send final event with accumulated content
                                    if accumulated_content:
                                        yield f"data: {json.dumps({'event': 'final', 'data': accumulated_content})}\n\n"
                                    
                            else:
                                # No fallback available
                                yield f"data: {json.dumps({'event': 'error', 'data': f'Rate limited and no fallback available: {error_msg}'})}\n\n"
                                return
                        else:
                            # Already using fallback, report the error
                            yield f"data: {json.dumps({'event': 'error', 'data': f'Error with fallback provider: {error_msg}'})}\n\n"
                            return
                    else:
                        # Not a rate limit error or no fallback available
                        yield f"data: {json.dumps({'event': 'error', 'data': f'API error: {error_msg}'})}\n\n"
                        return
                
                # Check for direct tool calls in the response
                if "choices" in response and response["choices"] and "message" in response["choices"][0]:
                    message = response["choices"][0]["message"]
                    if "tool_calls" in message and message["tool_calls"]:
                        print(f"Found {len(message['tool_calls'])} direct tool calls in response")
                        
                        # Stream any tool calls immediately
                        for tool_call in message["tool_calls"]:
                            function_name = tool_call["function"]["name"]
                            args_str = tool_call["function"]["arguments"]
                            
                            # Create a signature to detect duplicates
                            tool_signature = f"{function_name}:{args_str}"
                            
                            # Only stream if we haven't seen this exact tool call before
                            if tool_signature not in seen_tool_calls:
                                # Add to seen tool calls to prevent duplicates
                                seen_tool_calls.add(tool_signature)
                                
                                tool_data = {
                                    "id": tool_call["id"],
                                    "name": function_name,
                                    "args": args_str,
                                    "status": "pending", 
                                    "result": None
                                }
                                # Stream tool call event
                                direct_event = f"data: {json.dumps({'event': 'tool_call', 'data': tool_data})}\n\n"
                                yield direct_event
                
                # Define a wrapper function to capture and immediately emit tool events
                def tool_event_handler(event_type, data, *args):
                    # Filter out certain info messages to prevent them from appearing in the UI
                    if event_type == "info" and data == "Getting next response after tool execution...":
                        # Skip sending this to the UI, but still log it
                        print(f"Tool execution info: {data}")
                        return []  # Return empty generator to avoid yielding anything
                    
                    # Accept additional args but ignore them - makes function compatible with all calling patterns
                    event = f"data: {json.dumps({'event': event_type, 'data': data})}\n\n"
                    yield event
                
                # Process the response with tool handler - now returns a generator, not a dict
                tool_events_generator = process_tool_calls(
                    user_assistant,
                    response,
                    print_response=False,
                    validation_retries=2,
                    recursion_depth=0,
                    tool_event_callback=tool_event_handler
                )
                
                # Yield all tool events from the generator
                final_text = None
                for event_data in tool_events_generator:
                    # Check if this is a special final text event
                    if isinstance(event_data, dict) and "final_text" in event_data:
                        final_text = event_data["final_text"]
                    else:
                        # Otherwise, it's an event to stream directly
                        yield event_data
                
                # Restore original function
                formatting.tool_report_print = original_print
                
                # Stream the final response if we have text (only for non-LiteLLM providers)
                if final_text and user_assistant.provider != 'litellm':
                    yield f"data: {json.dumps({'event': 'token', 'data': final_text})}\n\n"
                    yield f"data: {json.dumps({'event': 'final', 'data': final_text})}\n\n"
                
            except Exception as e:
                import traceback
                print(f"Error during streaming: {e}")
                traceback.print_exc()
                
                yield f"data: {json.dumps({'event': 'error', 'data': str(e)})}\n\n"
                
                # Restore original function in case of error
                formatting.tool_report_print = original_print
            
            # Send done event
            yield f"data: {json.dumps({'event': 'done'})}\n\n"
            
        return Response(generate(), mimetype='text/event-stream')
        
    except Exception as e:
        print(f"Error during chat processing: {e}")
        return jsonify({"error": "An internal error occurred"}), 500

@chat_bp.route('', methods=['POST'])
def chat():
    """Legacy non-streaming API endpoint for backward compatibility."""
    if not current_app.assistant:
        return jsonify({"error": "Assistant not initialized"}), 500

    try:
        user_message = request.json.get('message')
        image_data = request.json.get('imageData')
        
        if not user_message and not image_data:
            return jsonify({"error": "No message or image provided"}), 400

        # Get session ID (or client IP if no session available)
        session_id = session.get('user_id', request.remote_addr)
        
        # Create or get user-specific assistant instance
        if session_id not in current_app.assistants:
            current_app.assistants[session_id] = Assistant(
                model=conf.MODEL,
                system_instruction=conf.get_system_prompt().strip(),
                tools=TOOLS  # Use the imported TOOLS directly
            )
        
        user_assistant = current_app.assistants[session_id]
        
        # Prepare image data if provided
        images = None
        if image_data:
            # Create the content array format required by the API
            images = [{
                "type": "image_url",
                "image_url": {
                    "url": image_data
                }
            }]
        
        # Send message to the assistant and get the response
        assistant_response = user_assistant.send_message(user_message, images)
        
        # Format response for the client
        if isinstance(assistant_response, dict) and "text" in assistant_response:
            # New format with text and tool calls
            return jsonify({
                "response": assistant_response["text"],
                "tool_calls": assistant_response.get("tool_calls", [])
            })
        else:
            # Fallback for backward compatibility
            return jsonify({"response": assistant_response})
    except Exception as e:
        print(f"Error during chat processing: {e}")
        # Potentially log the full traceback here
        return jsonify({"error": "An internal error occurred"}), 500

@chat_bp.route('/reset', methods=['POST'])
def reset_chat():
    """Reset the chat session"""
    try:
        session_id = session.get('user_id', request.remote_addr)
        
        # Check if the assistant exists for this session
        if session_id not in current_app.assistants:
            print(f"Creating new assistant for session {session_id}")
            # Create a new assistant for this session with the system prompt
            assistant = Assistant(
                model=conf.MODEL,
                name=conf.NAME,
                tools=tools.TOOLS,
                system_instruction=conf.get_system_prompt()
            )
            current_app.assistants[session_id] = assistant
        else:
            print(f"Resetting existing assistant for session {session_id}")
            # Reset the existing assistant
            current_app.assistants[session_id].reset_session()
            
        print("Chat session reset successfully")
        return jsonify({"status": "success", "message": "Chat session reset successfully"})
    except Exception as e:
        print(f"Error resetting chat session: {e}")
        traceback.print_exc()
        return jsonify({"status": "error", "message": str(e)}), 500
