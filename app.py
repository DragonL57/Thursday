from flask import Flask, render_template, request, jsonify, session
import config as conf
from tools import TOOLS  # Import the tools
from assistant import Assistant  # Import the Assistant class
import os

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

@app.route('/chat', methods=['POST'])
def chat():
    if not assistant:
        return jsonify({"error": "Assistant not initialized"}), 500

    try:
        user_message = request.json.get('message')
        if not user_message:
            return jsonify({"error": "No message provided"}), 400

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

        # Send message to the assistant and get the response
        assistant_response = user_assistant.send_message(user_message)
        
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