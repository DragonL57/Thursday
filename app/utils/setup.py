"""
Setup utilities for initializing directories and patching methods
"""

import os
import shutil

def setup_directories(app):
    """Setup necessary directories for the application"""
    # Create required directories
    os.makedirs(os.path.join(app.static_folder, 'css/components'), exist_ok=True)
    os.makedirs(os.path.join(app.static_folder, 'js/components'), exist_ok=True)
    os.makedirs(os.path.join(app.static_folder, 'js/utils'), exist_ok=True)

    # Create chats directory if it doesn't exist
    chats_dir = os.path.join(os.getcwd(), 'chats')
    if not os.path.exists(chats_dir):
        os.makedirs(chats_dir)

def setup_fonts(app):
    """Setup fonts directory and check for required fonts"""
    # Create fonts directory and check for font files
    fonts_dir = os.path.join(app.static_folder, 'fonts')
    if not os.path.exists(fonts_dir):
        os.makedirs(fonts_dir)

    # Create fallback font files if they don't exist
    required_fonts = [
        'FS PFBeauSansPro-Regular.ttf',
        'FS PFBeauSansPro-Bold.ttf',
        'FS PFBeauSansPro-Italic.ttf',
        'FS PFBeauSansPro-SemiBold.ttf',
        'FS PFBeauSansPro-Regular.otf',
        'FS PFBeauSansPro-Bold.otf',
        'FS PFBeauSansPro-SemiBold.otf'
    ]
    
    missing_fonts = []
    for font in required_fonts:
        font_path = os.path.join(fonts_dir, font)
        if not os.path.exists(font_path):
            missing_fonts.append(font)
    
    if missing_fonts:
        print(f"WARNING: The following font files are missing: {', '.join(missing_fonts)}")
        print(f"Creating fallback font files in {fonts_dir} for proper rendering")
        
        # Use system fonts as fallbacks if available
        fallback_fonts = {
            "sans-serif": "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            "sans-serif-bold": "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            "sans-serif-italic": "/usr/share/fonts/truetype/dejavu/DejaVuSans-Italic.ttf",
            "sans-serif-semibold": "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
        }
        
        # Fallback to Arial if available
        if os.path.exists("/usr/share/fonts/truetype/msttcorefonts/Arial.ttf"):
            fallback_fonts = {
                "sans-serif": "/usr/share/fonts/truetype/msttcorefonts/Arial.ttf",
                "sans-serif-bold": "/usr/share/fonts/truetype/msttcorefonts/Arial_Bold.ttf",
                "sans-serif-italic": "/usr/share/fonts/truetype/msttcorefonts/Arial_Italic.ttf",
                "sans-serif-semibold": "/usr/share/fonts/truetype/msttcorefonts/Arial_Bold.ttf"
            }
        
        # Create empty placeholder files to avoid 404 errors
        for font in missing_fonts:
            target_path = os.path.join(fonts_dir, font)
            
            # Try to copy a system font if available
            fallback_key = "sans-serif"
            if "Bold" in font:
                fallback_key = "sans-serif-bold"
            elif "Italic" in font:
                fallback_key = "sans-serif-italic" 
            elif "SemiBold" in font:
                fallback_key = "sans-serif-semibold"
                
            fallback_font = fallback_fonts.get(fallback_key)
            
            if fallback_font and os.path.exists(fallback_font):
                # Copy the fallback font to our target location
                shutil.copy2(fallback_font, target_path)
                print(f"Created fallback font: {target_path} (using {fallback_font})")
            else:
                # Create an empty file as last resort to avoid 404 errors
                with open(target_path, 'wb') as f:
                    f.write(b'')
                print(f"Created empty placeholder font: {target_path}")

    # Check if font-info.css exists, create it if it doesn't
    font_info_css_path = os.path.join(app.static_folder, 'css', 'font-info.css')
    if not os.path.exists(font_info_css_path):
        print(f"Creating missing font-info.css file at {font_info_css_path}")
        with open(font_info_css_path, 'w') as f:
            f.write("""/* Font information - dynamically generated */
:root {
  /* Font family settings */
  --font-primary: 'PF Beau Sans Pro', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
  --font-mono: 'Fira Code', SFMono-Regular, Consolas, 'Liberation Mono', Menlo, monospace;
  
  /* Font weight constants */
  --font-weight-normal: 400;
  --font-weight-medium: 500;
  --font-weight-semibold: 600;
  --font-weight-bold: 700;
  
  /* Font sizes */
  --font-size-xs: 0.75rem;
  --font-size-sm: 0.875rem;
  --font-size-base: 1rem;
  --font-size-lg: 1.125rem;
  --font-size-xl: 1.25rem;
  --font-size-2xl: 1.5rem;
}
""")

def patch_assistant_methods(sanitize_filename):
    """Patch Assistant class with save/load functionality if needed"""
    from assistant import Assistant
    import pickle
    import os

    # Check if the save_session method exists in Assistant class and patch if needed
    if not hasattr(Assistant, 'save_session') or not callable(getattr(Assistant, 'save_session', None)):
        def save_session(self, name, filepath="chats"):
            """Saves the current chat session to a pickle file."""
            # Create the directory if it doesn't exist
            if not os.path.exists(filepath):
                os.makedirs(filepath)
            
            # Sanitize the filename to handle special characters
            safe_name = sanitize_filename(name)
            
            # Create the full path
            full_path = os.path.join(filepath, f"{safe_name}.pkl")
            
            # Save the session data
            with open(full_path, 'wb') as f:
                pickle.dump({
                    'messages': self.messages,
                    'model': self.model,
                    'system_instruction': self.system_instruction
                }, f)
            
            return full_path
            
        # Add the method to the Assistant class
        Assistant.save_session = save_session
        print("Added save_session method to Assistant class")

    # Add load_session method if it doesn't exist
    if not hasattr(Assistant, 'load_session') or not callable(getattr(Assistant, 'load_session', None)):
        def load_session(self, name, filepath="chats"):
            """Loads a chat session from a pickle file."""
            full_path = os.path.join(filepath, f"{name}.pkl")
            
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

    # Add reset_session method if it doesn't exist
    if not hasattr(Assistant, 'reset_session') or not callable(getattr(Assistant, 'reset_session', None)):
        def reset_session(self):
            """Resets the current session."""
            # Keep only the system message
            system_messages = [msg for msg in self.messages if msg.get('role') == 'system']
            if system_messages:
                self.messages = system_messages
            else:
                # If no system message, create a fresh conversation with system instruction
                self.messages = [{"role": "system", "content": self.system_instruction}]
                
            return True
            
        # Add the method to the Assistant class
        Assistant.reset_session = reset_session
        print("Added reset_session method to Assistant class")
