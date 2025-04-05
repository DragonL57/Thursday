from flask import Flask, render_template, request, jsonify, session, Response
import config as conf
from tools import TOOLS  # Import the tools
from assistant import Assistant  # Import from the new package
import os
import json
import time
import base64
import re
import random
import traceback  # Add this import for stack traces

app = Flask(__name__)
app.secret_key = os.urandom(24)  # Secure secret key for session management

# Create the necessary directories if they don't exist
os.makedirs(os.path.join(app.static_folder, 'css/components'), exist_ok=True)
os.makedirs(os.path.join(app.static_folder, 'js/components'), exist_ok=True)
os.makedirs(os.path.join(app.static_folder, 'js/utils'), exist_ok=True)

# Instantiate the Assistant
# Make sure config.py and tools are accessible
try:
    sys_instruct = conf.get_system_prompt().strip()
    assistant = Assistant(
        model=conf.MODEL,
        system_instruction=sys_instruct,
        tools=TOOLS
    )
except Exception as e:
    print(f"Error initializing Assistant: {e}")
    assistant = None  # Handle initialization failure gracefully

# Store assistants in session for multi-user support
assistants = {}

@app.route('/')
def index():
    # Serve the main HTML page
    return render_template('index.html')

@app.route('/chat/stream', methods=['POST'])
def chat_stream():
    """Stream chat responses using server-sent events."""
    if not assistant:
        return jsonify({"error": "Assistant not initialized"}), 500

    try:
        user_message = request.json.get('message', '')
        image_data = request.json.get('imageData')
        
        if not user_message and not image_data:
            return jsonify({"error": "No message or image provided"}), 400

        # Get session ID (or client IP if no session available)
        session_id = session.get('user_id', request.remote_addr)
        
        # Create or get user-specific assistant instance
        if session_id not in assistants:
            assistants[session_id] = Assistant(
                model=conf.MODEL,
                system_instruction=conf.get_system_prompt().strip(),
                tools=TOOLS,
                stream_handler=True  # Enable streaming mode
            )
        
        user_assistant = assistants[session_id]

        # NEW: Validate the message history before adding the new user message
        # Check if there are pending tool calls that need responses
        if hasattr(user_assistant, 'messages') and len(user_assistant.messages) > 0:
            # Check if the last message is from the assistant with tool calls
            last_message = user_assistant.messages[-1]
            if last_message.get('role') == 'assistant' and 'tool_calls' in last_message:
                # Get the tool call IDs from the last message
                pending_tool_calls = {tc['id'] for tc in last_message.get('tool_calls', [])}
                
                # Check which tool calls have responses
                responded_tool_calls = set()
                for msg in user_assistant.messages:
                    if msg.get('role') == 'tool':
                        responded_tool_calls.add(msg.get('tool_call_id'))
                
                # Find missing tool responses
                missing_tool_calls = pending_tool_calls - responded_tool_calls
                if missing_tool_calls:
                    # This is a serious issue - we need to add the missing tool responses
                    for tool_call_id in missing_tool_calls:
                        print(f"WARNING: Adding missing tool response for {tool_call_id}")
                        # Find the corresponding tool call to get the name
                        tool_name = "unknown_tool"
                        for tc in last_message.get('tool_calls', []):
                            if tc['id'] == tool_call_id:
                                tool_name = tc.get('function', {}).get('name', 'unknown_tool')
                                break
                                
                        # Add a placeholder response
                        user_assistant.add_toolcall_output(
                            tool_call_id,
                            tool_name,
                            "Error: Tool execution was not completed properly. Please try again."
                        )

        # Prepare image data if provided
        images = None
        if image_data:
            # Check if it's already in the right format (dataURL)
            if isinstance(image_data, str) and image_data.startswith('data:image/'):
                # Create the content array format required by the API
                images = [{
                    "type": "image_url",
                    "image_url": {
                        "url": image_data
                    }
                }]
            else:
                # Try to format it as base64 if it's not already
                match = re.match(r'^data:image/([a-zA-Z]+);base64,(.+)$', image_data) if isinstance(image_data, str) else None
                if not match:
                    # If no match, assume it's just a base64 string
                    image_format = 'jpeg'  # default format
                    base64_data = image_data
                    image_url = f"data:image/{image_format};base64,{base64_data}"
                    images = [{
                        "type": "image_url",
                        "image_url": {
                            "url": image_url
                        }
                    }]
                else:
                    # It's already a proper data URL
                    images = [{
                        "type": "image_url",
                        "image_url": {
                            "url": image_data
                        }
                    }]

        def generate():
            # Send an event indicating the start of processing
            yield f"data: {json.dumps({'event': 'start'})}\n\n".encode('utf-8')
            
            try:
                # Use a non-streaming approach for the initial response
                print(f"Initial call with message: {user_message}")
                
                # Add the user message to the assistant's history
                if images:
                    print(f"DEBUG: Adding user message with {len(images)} images")
                    content = [{"type": "text", "text": user_message}]
                    content.extend(images)
                    user_assistant.messages.append({"role": "user", "content": content})
                else:
                    print(f"DEBUG: Adding user message with text only")
                    user_assistant.messages.append({"role": "user", "content": user_message})
                
                # Make the initial API call without streaming to detect tool calls
                try:
                    print("DEBUG: Making initial API call to detect tool calls")
                    response = user_assistant.api_client._make_api_request(
                        messages=user_assistant.messages,
                        tools=user_assistant.tools,
                        stream=False
                    )
                    
                    if not response:
                        error_msg = "Failed to get a response from the API server"
                        print(f"ERROR: {error_msg}")
                        yield f"data: {json.dumps({'event': 'error', 'data': error_msg})}\n\n".encode('utf-8')
                        yield f"data: {json.dumps({'event': 'done'})}\n\n".encode('utf-8')
                        return
                    
                    # Extract the response content and any tool calls
                    if "choices" in response and response["choices"] and "message" in response["choices"][0]:
                        message = response["choices"][0]["message"]
                        
                        # Check if the message has content
                        text_content = message.get("content", "")
                        
                        # Check if there are tool calls
                        tool_calls = message.get("tool_calls", [])
                        
                        if tool_calls:
                            print(f"DEBUG: Found {len(tool_calls)} tool calls to execute")
                            
                            # Store the tool calls for processing
                            user_assistant.current_tool_calls = []
                            
                            # Add assistant message with tool calls to conversation history
                            user_assistant.messages.append(message)
                            
                            for tc in tool_calls:
                                # Process each tool call from the response
                                tool_id = tc.get("id", "")
                                function_data = tc.get("function", {})
                                function_name = function_data.get("name", "")
                                arguments_str = function_data.get("arguments", "{}")
                                
                                # Store the tool call in our standardized format
                                tool_call = {
                                    "id": tool_id,
                                    "name": function_name,
                                    "args": arguments_str,
                                    "status": "pending",
                                    "result": None
                                }
                                
                                # Add to current tool calls list
                                user_assistant.current_tool_calls.append(tool_call)
                                
                                # Send the tool call to the client
                                tool_call_data = {
                                    'id': tool_id,
                                    'name': function_name,
                                    'args': arguments_str,
                                    'status': 'pending'
                                }
                                
                                yield f"data: {json.dumps({'event': 'tool_call', 'data': tool_call_data})}\n\n".encode('utf-8')
                            
                            # Now execute all the tool calls
                            
                            for tool_call in user_assistant.current_tool_calls:
                                try:
                                    # Execute the tool
                                    function_name = tool_call['name']
                                    arguments_str = tool_call['args']
                                    function_args = json.loads(arguments_str) if arguments_str else {}
                                    
                                    function_to_call = user_assistant.available_functions.get(function_name)
                                    
                                    if function_to_call:
                                        # Execute the function
                                        print(f"DEBUG: Executing tool {function_name}")
                                        tool_result = function_to_call(**function_args)
                                        
                                        # Convert tool result to string if it's not already
                                        if not isinstance(tool_result, str):
                                            try:
                                                # If it's a list or dict, serialize it properly to valid JSON
                                                if isinstance(tool_result, (list, dict)):
                                                    tool_result = json.dumps(tool_result, ensure_ascii=False)
                                                else:
                                                    tool_result = str(tool_result)
                                            except:
                                                tool_result = str(tool_result)
                                        else:
                                            # If it's already a string but looks like a Python repr, try to convert to valid JSON
                                            if tool_result.startswith('[') and ("'" in tool_result or "False" in tool_result or "True" in tool_result):
                                                try:
                                                    # Try to safely evaluate and convert to proper JSON
                                                    import ast
                                                    parsed_result = ast.literal_eval(tool_result)
                                                    tool_result = json.dumps(parsed_result, ensure_ascii=False)
                                                except:
                                                    # Keep as is if conversion fails
                                                    pass
                                        
                                        # Update tool call status
                                        tool_call['status'] = 'completed'
                                        tool_call['result'] = tool_result
                                        
                                        # Send tool update to client
                                        yield f"data: {json.dumps({'event': 'tool_update', 'data': tool_call})}\n\n".encode('utf-8')
                                        
                                        # Add tool result to message history
                                        user_assistant.add_toolcall_output(
                                            tool_call['id'],
                                            function_name,
                                            tool_result
                                        )
                                    else:
                                        raise ValueError(f"Function {function_name} not found in available tools")
                                except Exception as e:
                                    # Handle errors in tool execution
                                    error_message = f"Error executing tool {function_name}: {str(e)}"
                                    print(f"ERROR: Tool execution error: {error_message}")
                                    traceback.print_exc()  # Print the full stack trace for debugging
                                    
                                    tool_call['status'] = 'error'
                                    tool_call['result'] = error_message
                                    
                                    # Send error update to client
                                    yield f"data: {json.dumps({'event': 'tool_update', 'data': tool_call})}\n\n".encode('utf-8')
                                    
                                    # Add error to message history
                                    user_assistant.add_toolcall_output(
                                        tool_call['id'],
                                        function_name,
                                        error_message
                                    )
                            
                            # Now that all tools are executed, make a final API call to get the final response
                            # Send info event with a special flag to indicate it should be removed when response arrives
                            yield f"data: {json.dumps({'event': 'info', 'data': 'Getting AI response based on tool results...', 'temp': True})}\n\n".encode('utf-8')
                            
                            try:
                                # Make a second API call to get the final response
                                final_response = user_assistant.api_client._make_api_request(
                                    messages=user_assistant.messages,
                                    tools=user_assistant.tools,
                                    stream=False
                                )
                                
                                if final_response and "choices" in final_response and final_response["choices"] and "message" in final_response["choices"][0]:
                                    final_message = final_response["choices"][0]["message"]
                                    final_content = final_message.get("content", "")
                                    
                                    # Add the final response to conversation history
                                    user_assistant.messages.append(final_message)
                                    
                                    # Stream the final response to the client in chunks
                                    if final_content:
                                        # First, send a clear_temp_info event to remove the temporary message
                                        yield f"data: {json.dumps({'event': 'clear_temp_info'})}\n\n".encode('utf-8')
                                        
                                        chunks = chunk_text(final_content, avg_chunk_size=5)
                                        for chunk in chunks:
                                            yield f"data: {json.dumps({'event': 'token', 'data': chunk})}\n\n".encode('utf-8')
                                            time.sleep(0.01)  # Small delay between chunks
                                    else:
                                        # Handle the case where there is no content in the final response
                                        # First, send a clear_temp_info event to remove the temporary message
                                        yield f"data: {json.dumps({'event': 'clear_temp_info'})}\n\n".encode('utf-8')
                                        
                                        fallback_response = "I've processed the information, but I don't have anything additional to add."
                                        yield f"data: {json.dumps({'event': 'token', 'data': fallback_response})}\n\n".encode('utf-8')
                                else:
                                    # First, send a clear_temp_info event to remove the temporary message
                                    yield f"data: {json.dumps({'event': 'clear_temp_info'})}\n\n".encode('utf-8')
                                    
                                    error_msg = "Failed to get a final response from the API"
                                    print(f"ERROR: {error_msg}")
                                    fallback_response = "I've executed the requested tools, but couldn't generate a proper response."
                                    yield f"data: {json.dumps({'event': 'token', 'data': fallback_response})}\n\n".encode('utf-8')
                            except Exception as e:
                                # First, send a clear_temp_info event to remove the temporary message
                                yield f"data: {json.dumps({'event': 'clear_temp_info'})}\n\n".encode('utf-8')
                                
                                error_msg = f"Error getting final response: {str(e)}"
                                print(f"ERROR: {error_msg}")
                                traceback.print_exc()
                                fallback_response = "I've executed the tools but encountered an error preparing the response."
                                yield f"data: {json.dumps({'event': 'token', 'data': fallback_response})}\n\n".encode('utf-8')
                        
                        elif text_content:
                            # No tool calls, just stream the text content
                            print(f"DEBUG: No tool calls, just returning text content")
                            user_assistant.messages.append({
                                "role": "assistant",
                                "content": text_content
                            })
                            
                            # Stream the response to the client in chunks
                            chunks = chunk_text(text_content, avg_chunk_size=5)
                            for chunk in chunks:
                                yield f"data: {json.dumps({'event': 'token', 'data': chunk})}\n\n".encode('utf-8')
                                time.sleep(0.01)  # Small delay between chunks
                        else:
                            # No content at all
                            error_msg = "The API response didn't contain any content"
                            print(f"ERROR: {error_msg}")
                            yield f"data: {json.dumps({'event': 'error', 'data': error_msg})}\n\n".encode('utf-8')
                    else:
                        # No valid response from API
                        error_msg = "Received an invalid response format from the API"
                        print(f"ERROR: {error_msg}")
                        yield f"data: {json.dumps({'event': 'error', 'data': error_msg})}\n\n".encode('utf-8')
                
                except Exception as api_error:
                    # Handle API request errors
                    error_msg = f"Error making API request: {str(api_error)}"
                    print(f"ERROR: {error_msg}")
                    traceback.print_exc()
                    yield f"data: {json.dumps({'event': 'error', 'data': error_msg})}\n\n".encode('utf-8')
                
            except Exception as e:
                # Handle any other errors in the processing
                error_message = str(e)
                print(f"CRITICAL: Exception in chat stream: {error_message}")
                traceback.print_exc()
                
                if "429" in error_message or "rate limit" in error_message.lower():
                    user_friendly_error = "Rate limit exceeded. Please try again in a few minutes or use a smaller image."
                    yield f"data: {json.dumps({'event': 'error', 'data': user_friendly_error})}\n\n".encode('utf-8')
                else:
                    yield f"data: {json.dumps({'event': 'error', 'data': str(e)})}\n\n".encode('utf-8')
            
            # Always send done event at the end
            yield f"data: {json.dumps({'event': 'done'})}\n\n".encode('utf-8')
            
        return Response(generate(), mimetype='text/event-stream')
    except Exception as e:
        print(f"Error during chat streaming: {e}")
        # Return error as a stream event
        error_message = str(e)
        if "429" in error_message or "rate limit" in error_message.lower():
            user_friendly_error = "Rate limit exceeded. Please try again in a few minutes or use a smaller image."
            return Response(
                f"data: {json.dumps({'event': 'error', 'data': user_friendly_error})}\n\n".encode('utf-8'),
                mimetype='text/event-stream'
            )
        else:
            return Response(
                f"data: {json.dumps({'event': 'error', 'data': str(e)})}\n\n".encode('utf-8'),
                mimetype='text/event-stream'
            )

def chunk_text(text, avg_chunk_size=3):
    """Split text into smaller chunks for streaming."""
    if not text:
        return []
    
    # Split by spaces but preserve them
    parts = []
    current = ""
    
    for char in text:
        current += char
        if char == ' ':
            parts.append(current)
            current = ""
    
    if current:  # Add the last part if it exists
        parts.append(current)
    
    # Now group these parts into chunks
    chunks = []
    current_chunk = []
    current_length = 0
    
    for part in parts:
        current_chunk.append(part)
        current_length += 1
        
        # Use some randomization to make it feel more natural
        if current_length >= avg_chunk_size and random.random() > 0.5:
            # Check if we should split here
            last_part = current_chunk[-1].strip()
            if (last_part.endswith(('.', '!', '?', ':', ';', ',')) or 
                current_length >= avg_chunk_size * 2):
                chunks.append(''.join(current_chunk))
                current_chunk = []
                current_length = 0
    
    # Add any remaining content
    if current_chunk:
        chunks.append(''.join(current_chunk))
    
    return chunks

@app.route('/chat', methods=['POST'])
def chat():
    """Legacy non-streaming API endpoint for backward compatibility."""
    if not assistant:
        return jsonify({"error": "Assistant not initialized"}), 500

    try:
        user_message = request.json.get('message')
        image_data = request.json.get('imageData')
        
        if not user_message and not image_data:
            return jsonify({"error": "No message or image provided"}), 400

        # Get session ID (or client IP if no session available)
        session_id = session.get('user_id', request.remote_addr)
        
        # Create or get user-specific assistant instance
        if session_id not in assistants:
            assistants[session_id] = Assistant(
                model=conf.MODEL,
                system_instruction=conf.get_system_prompt().strip(),
                tools=TOOLS
            )
        
        user_assistant = assistants[session_id]
        
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

@app.route('/reset', methods=['POST'])
def reset_conversation():
    try:
        session_id = session.get('user_id', request.remote_addr)
        if session_id in assistants:
            assistants[session_id].reset_session()
            return jsonify({"status": "Conversation reset successfully"})
        return jsonify({"status": "No active conversation to reset"})
    except Exception as e:
        return jsonify({"error": f"Failed to reset conversation: {str(e)}"}), 500

@app.route('/settings', methods=['POST'])
def update_settings():
    try:
        settings = request.json
        session_id = session.get('user_id', request.remote_addr)
        
        # Update the config.py values
        updated_settings = conf.update_config(settings)
        
        # Update active assistant instances
        if session_id in assistants:
            if settings.get('model'):
                assistants[session_id].model = settings['model']
            
            # Some models might allow temperature updates
            if 'temperature' in settings and hasattr(assistants[session_id], 'set_temperature'):
                try:
                    assistants[session_id].set_temperature(float(settings['temperature']))
                except (AttributeError, ValueError):
                    pass
        
        return jsonify({"status": "Settings updated successfully", "settings": updated_settings})
    except Exception as e:
        return jsonify({"error": f"Failed to update settings: {str(e)}"}), 500

@app.route('/api/settings', methods=['GET', 'POST'])
def handle_settings():
    if request.method == 'POST':
        data = request.json
        
        # Update the global assistant with new settings
        if data.get('model') and assistant:
            assistant.model = data.get('model')
            
        # Store settings in session
        session['settings'] = {
            'model': data.get('model', conf.MODEL),
            'temperature': data.get('temperature', conf.TEMPERATURE),
            'max_tokens': data.get('max_tokens', conf.MAX_TOKENS),
            'save_history': data.get('save_history', getattr(conf, 'SAVE_HISTORY', False))
        }
        
        return jsonify({"status": "success", "message": "Settings updated"})
    
    # GET request - return current settings
    settings = session.get('settings', {
        'model': conf.MODEL,
        'temperature': conf.TEMPERATURE,
        'max_tokens': conf.MAX_TOKENS,
        'save_history': getattr(conf, 'SAVE_HISTORY', False)
    })
    
    return jsonify(settings)

if __name__ == '__main__':
    # Generate a proper secret key for production
    if app.secret_key == b'change-me':
        app.secret_key = os.urandom(24)
    
    app.run(debug=True, host='0.0.0.0', port=5000)  # Expose on network for potential access