"""
Main routes for the application
"""

from flask import Blueprint, render_template, send_from_directory, jsonify, request, session, current_app
import traceback
import os
import litellm # Add litellm import
import config as conf # Import config for litellm params

main_bp = Blueprint('main', __name__)

@main_bp.route('/')
def index():
    """Serve the main HTML page"""
    return render_template('index.html')

@main_bp.route('/static/fonts/<path:filename>')
def serve_font(filename):
    """Serve font files with proper MIME type"""
    mimetype = None
    if filename.endswith('.ttf'):
        mimetype = 'font/ttf'
    elif filename.endswith('.otf'):
        mimetype = 'font/otf'
    elif filename.endswith('.woff'):
        mimetype = 'font/woff'
    elif filename.endswith('.woff2'):
        mimetype = 'font/woff2'
    
    # Get the absolute path to the static/fonts directory
    fonts_dir = os.path.join(current_app.root_path, '../static/fonts')
    
    # Check if the file exists in the fonts directory
    font_path = os.path.join(fonts_dir, filename)
    if not os.path.exists(font_path):
        print(f"Font file not found: {font_path}")
        return f"Font file not found: {filename}", 404
    
    # Send the actual file from the directory
    return send_from_directory(fonts_dir, filename, mimetype=mimetype)

@main_bp.route('/reset', methods=['POST'])
def reset_conversation():
    """Route to handle conversation reset (for backward compatibility)"""
    try:
        session_id = session.get('user_id', request.remote_addr)
        if session_id in current_app.assistants:
            current_app.assistants[session_id].reset_session()
            return jsonify({"status": "Conversation reset successfully"})
        return jsonify({"status": "No active conversation to reset"})
    except Exception as e:
        return jsonify({"error": f"Failed to reset conversation: {str(e)}"}), 500

@main_bp.route('/generate_summary', methods=['POST'])
def generate_conversation_summary():
    """Generate a short 1-3 word summary for naming the conversation"""
    try:
        session_id = session.get('user_id', request.remote_addr)
        if session_id not in current_app.assistants:
            return jsonify({"error": "No active assistant session"}), 404
        
        # Get the current conversation messages
        user_assistant = current_app.assistants[session_id]
        
        # Extract just the user messages for context
        user_messages = [
            msg.get("content", "") 
            for msg in user_assistant.messages 
            if msg.get("role") == "user" and isinstance(msg.get("content"), str)
        ]
        
        # If we have multiple image messages or structured content, they may not have simple string content
        if not user_messages:
            return jsonify({"summary": "New Conversation"}), 200
        
        # Join user messages with a separator
        context = " | ".join(user_messages[-3:])  # Use last 3 messages for context
        
        # Create a special message list for the summary request
        summary_messages = [
            {"role": "system", "content": "You are a helpful AI that creates extremely short and concise conversation titles."},
            {"role": "user", "content": f"Based on this conversation: '{context}', generate a very short title (1-3 words maximum) that captures the essence of the topic. Respond with ONLY the title, no explanations, quotes or extra text."}
        ]
        
        # Make a direct completion request for the summary based on provider
        print(f"Generating conversation summary using provider: {user_assistant.provider}...")
        if user_assistant.provider == 'pollinations':
             if not user_assistant.api_client:
                 raise ValueError("Pollinations provider selected but api_client is not initialized.")
             response = user_assistant.api_client.get_completion(
                 messages=summary_messages
                 # Note: Pollinations doesn't need extra params here usually
             )
        elif user_assistant.provider == 'litellm':
             # Prepare args for litellm completion (non-streaming)
             completion_args = {
                 "model": user_assistant.model, # Use the assistant's current model
                 "messages": summary_messages,
                 "temperature": 0.5, # Use a lower temp for concise summary
                 "max_tokens": 20, # Limit tokens for summary
             }
             # Remove None values before passing to litellm
             completion_args = {k: v for k, v in completion_args.items() if v is not None}
             response = litellm.completion(**completion_args)
        else:
             raise ValueError(f"Unsupported provider for summary: {user_assistant.provider}")
        
        if "choices" in response and len(response["choices"]) > 0 and "message" in response["choices"][0]:
            # Extract the generated summary from the response
            summary = response["choices"][0]["message"].get("content", "").strip()
            
            # Remove any quotes if present
            summary = summary.strip('"\'')
            
            # Truncate if too long
            if len(summary.split()) > 3:
                summary = " ".join(summary.split()[:3])
            
            print(f"Generated summary: {summary}")
            
            return jsonify({"summary": summary})
        else:
            return jsonify({"summary": "New Conversation"})
    except Exception as e:
        print(f"Error generating conversation summary: {str(e)}")
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500
