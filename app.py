from flask import Flask, render_template, request, jsonify
import config as conf
from tools import TOOLS # Import the tools
from assistant import Assistant # Import the Assistant class

app = Flask(__name__)

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
    assistant = None # Handle initialization failure gracefully

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

        # Send message to the assistant and get the response
        # The modified send_message -> __process_response now returns the text content
        assistant_response = assistant.send_message(user_message)

        # Return the assistant's response
        return jsonify({"response": assistant_response})

    except Exception as e:
        print(f"Error during chat processing: {e}")
        # Potentially log the full traceback here
        return jsonify({"error": "An internal error occurred"}), 500

if __name__ == '__main__':
    # Note: Using debug=True might cause the Assistant to be initialized twice
    # in development mode due to Flask's reloader. Consider setting debug=False
    # or using a different approach for managing the assistant instance if needed.
    app.run(debug=True, host='0.0.0.0', port=5000) # Expose on network for potential access