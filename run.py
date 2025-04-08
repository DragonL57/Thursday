from flask import Flask
from app import create_app
# Remove: from app.services.conversation_service import ConversationManager 

app = create_app()

# Initialize assistants dictionary to store assistant instances
app.assistants = {}

# Remove: Initialize conversation manager
# app.conversation_manager = ConversationManager()

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
