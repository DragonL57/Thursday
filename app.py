from flask import Flask, render_template, request, jsonify, session, Response
import config as conf
from tools import TOOLS  # Import the tools
from assistant import Assistant  # Import the Assistant class
import os
import json
import time
import base64
import re

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
            yield f"data: {json.dumps({'event': 'start'})}\n\n"
            
            try:
                # Start processing and track tool calls
                user_assistant.prepare_message(user_message, images)
                
                # Stream tool calls as they are executed
                tool_calls_seen = set()
                max_wait_time = 60  # Maximum wait time in seconds
                start_time = time.time()
                
                while user_assistant.is_processing and (time.time() - start_time < max_wait_time):
                    try:
                        current_tools = user_assistant.get_current_tool_calls()
                        for tool_call in current_tools:
                            tool_id = tool_call.get('id')
                            if tool_id and tool_id not in tool_calls_seen:
                                # New tool call
                                yield f"data: {json.dumps({'event': 'tool_call', 'data': tool_call})}\n\n"
                                tool_calls_seen.add(tool_id)
                            elif tool_id in tool_calls_seen:
                                # Tool call was updated
                                yield f"data: {json.dumps({'event': 'tool_update', 'data': tool_call})}\n\n"
                    except Exception as tool_err:
                        print(f"Error processing tool calls: {tool_err}")
                    
                    time.sleep(0.1)  # Short sleep to avoid CPU thrashing
                
                # Get the final response after all tools have been executed
                try:
                    final_response = user_assistant.get_final_response()
                except AttributeError:
                    # Handle the case where get_final_response isn't defined
                    final_response = "Sorry, there was a problem retrieving the final response."
                    if hasattr(user_assistant, 'messages') and user_assistant.messages:
                        # Try to get the last assistant message as fallback
                        for msg in reversed(user_assistant.messages):
                            if isinstance(msg, dict) and msg.get("role") == "assistant" and "content" in msg:
                                final_response = msg["content"]
                                break
                
                # Check if we timed out
                if time.time() - start_time >= max_wait_time:
                    timeout_msg = "Request processing took too long. Please try again with a simpler request or smaller image."
                    yield f"data: {json.dumps({'event': 'error', 'data': timeout_msg})}\n\n"
                # Check if the response contains an error message about rate limits
                elif isinstance(final_response, str) and "rate limit" in final_response.lower():
                    # Send a more user-friendly rate limit error
                    error_msg = "The image processing request was rate limited. Please try again in a few minutes or use a smaller image."
                    yield f"data: {json.dumps({'event': 'error', 'data': error_msg})}\n\n"
                else:
                    # Send the final response
                    yield f"data: {json.dumps({'event': 'final', 'data': final_response})}\n\n"
                
            except Exception as e:
                error_message = str(e)
                if "429" in error_message or "rate limit" in error_message.lower():
                    user_friendly_error = "Rate limit exceeded. Please try again in a few minutes or use a smaller image."
                    yield f"data: {json.dumps({'event': 'error', 'data': user_friendly_error})}\n\n"
                else:
                    yield f"data: {json.dumps({'event': 'error', 'data': str(e)})}\n\n"
            
            # Make sure user_assistant.is_processing is set to False in case of exceptions
            if hasattr(user_assistant, 'is_processing'):
                user_assistant.is_processing = False
            
            # Send end of stream
            yield f"data: {json.dumps({'event': 'done'})}\n\n"
        
        return Response(generate(), mimetype='text/event-stream')

    except Exception as e:
        print(f"Error during chat streaming: {e}")
        # Return error as a stream event
        error_message = str(e)
        if "429" in error_message or "rate limit" in error_message.lower():
            user_friendly_error = "Rate limit exceeded. Please try again in a few minutes or use a smaller image."
            return Response(
                f"data: {json.dumps({'event': 'error', 'data': user_friendly_error})}\n\n",
                mimetype='text/event-stream'
            )
        else:
            return Response(
                f"data: {json.dumps({'event': 'error', 'data': str(e)})}\n\n",
                mimetype='text/event-stream'
            )

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
        
        if settings.get('model'):
            # Update model if provided and different from current
            new_model = settings['model']
            if session_id in assistants:
                assistants[session_id].model = new_model
        
        if 'temperature' in settings:
            # Update temperature in config (would need proper implementation)
            temp = float(settings['temperature'])
            conf.TEMPERATURE = temp
        
        # Other settings could be handled here
        
        return jsonify({"status": "Settings updated successfully"})
    except Exception as e:
        return jsonify({"error": f"Failed to update settings: {str(e)}"}), 500

if __name__ == '__main__':
    # Generate a proper secret key for production
    if app.secret_key == b'change-me':
        app.secret_key = os.urandom(24)
    
    app.run(debug=True, host='0.0.0.0', port=5000)  # Expose on network for potential access