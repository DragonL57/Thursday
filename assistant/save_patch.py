"""
Patch to ensure the Assistant class has a save_session method.
Import this in app.py to apply the patch.
"""

from assistant import Assistant

# Helper function to sanitize filenames
def sanitize_filename(filename):
    """Sanitize a filename by replacing problematic characters."""
    # Replace slashes, colons, and other forbidden characters
    forbidden_chars = ['/', '\\', ':', '*', '?', '"', '<', '>', '|']
    sanitized = filename
    for char in forbidden_chars:
        sanitized = sanitized.replace(char, '-')
    return sanitized

# Check if the save_session method exists
if not hasattr(Assistant, 'save_session') or not callable(getattr(Assistant, 'save_session', None)):
    # Add the method if it doesn't exist
    def save_session(self, name, filepath="chats"):
        """Saves the current chat session to a pickle file."""
        import os
        import pickle
        
        # Create the directory if it doesn't exist
        if not os.path.exists(filepath):
            os.makedirs(filepath)
        
        # Sanitize the filename to handle special characters
        safe_name = sanitize_filename(name)
        
        # Create the full path
        full_path = os.path.join(filepath, f"{safe_name}.pkl")
        
        # Make a copy of messages to avoid modifying the original
        messages_to_save = list(self.messages)
        
        # Check if we have any user/assistant messages (actual conversation content)
        has_user_message = any(msg.get('role') == 'user' for msg in messages_to_save)
        has_assistant_message = any(msg.get('role') == 'assistant' for msg in messages_to_save)
        
        # If there's no actual conversation content, add placeholder messages
        if not (has_user_message and has_assistant_message):
            print(f"Adding placeholder messages to conversation '{name}' before saving")
            # Look at the content in the first message if any
            first_message_content = "New conversation"
            if len(messages_to_save) > 0 and 'content' in messages_to_save[0]:
                first_message_content = messages_to_save[0].get('content')
                if isinstance(first_message_content, list):
                    # Handle multimodal content
                    text_parts = [part for part in first_message_content if part.get('type') == 'text']
                    if text_parts:
                        first_message_content = text_parts[0].get('text', 'New conversation')
                    else:
                        first_message_content = "New conversation"
            
            # Add actual content from the conversation as the message
            messages_to_save.append({"role": "user", "content": first_message_content})
            messages_to_save.append({"role": "assistant", "content": "How can I help you today?"})
        
        # Print message count for debugging
        user_assistant_count = sum(1 for msg in messages_to_save if msg.get('role') in ['user', 'assistant'])
        print(f"Saving {len(messages_to_save)} messages ({user_assistant_count} user/assistant messages)")
        
        # Save the session data
        with open(full_path, 'wb') as f:
            pickle.dump({
                'messages': messages_to_save,  # Save the modified messages
                'model': self.model,
                'system_instruction': self.system_instruction
            }, f)
        
        print(f"Chat session saved to {full_path}")
        return full_path
    
    # Add the method to the Assistant class
    Assistant.save_session = save_session
    
    print("Added save_session method to Assistant class")
    
# Check if the load_session method exists
if not hasattr(Assistant, 'load_session') or not callable(getattr(Assistant, 'load_session', None)):
    def load_session(self, name, filepath="chats"):
        """Loads a chat session from a pickle file."""
        import os
        import pickle
        
        # Sanitize the filename
        safe_name = sanitize_filename(name)
        full_path = os.path.join(filepath, f"{safe_name}.pkl")
        
        if not os.path.exists(full_path):
            raise FileNotFoundError(f"Session file not found: {full_path}")
        
        with open(full_path, 'rb') as f:
            data = pickle.load(f)
            
        # Update attributes
        self.messages = data.get('messages', [])
        if 'model' in data:
            self.model = data['model']
        if 'system_instruction' in data:
            self.system_instruction = data['system_instruction']
            
        return True
    
    # Add the method to the Assistant class
    Assistant.load_session = load_session
    print("Added load_session method to Assistant class")
