"""
Initialize Flask application and its components
"""

from flask import Flask, current_app, g
from assistant import Assistant
import config as conf
from tools import TOOLS
from utils.provider_manager import ProviderManager

def init_app():
    """Initialize the Flask application."""
    app = Flask(__name__, static_folder='../static', template_folder='../templates')
    app.config.from_mapping(
        SECRET_KEY=conf.SECRET_KEY if hasattr(conf, 'SECRET_KEY') else 'dev',
    )
    
    # Create initial assistant instance
    # Check for integrated model option
    if conf.MODEL == "gpt4o-integrated":
        # Set up the integrated model using provider manager
        ProviderManager.initialize()
        provider, model_name = ProviderManager.get_provider_and_model('gpt4o')
        assistant = Assistant(
            model=model_name,
            name=conf.NAME,
            tools=TOOLS,
            system_instruction=conf.get_system_prompt() if hasattr(conf, 'get_system_prompt') else ""
        )
        # Set the provider explicitly
        assistant.provider = provider
    else:
        # Use standard configuration
        assistant = Assistant(
            model=conf.MODEL,
            name=conf.NAME,
            tools=TOOLS,
            system_instruction=conf.get_system_prompt() if hasattr(conf, 'get_system_prompt') else ""
        )
    
    # Store the assistant in the app
    app.assistant = assistant
    
    # Dictionary to store user-specific assistants
    app.assistants = {}
    
    # Register the chat blueprint
    from app.routes import chat_bp
    app.register_blueprint(chat_bp, url_prefix='/chat')
    
    # Register settings blueprint
    from app.routes import settings_bp
    app.register_blueprint(settings_bp, url_prefix='/settings')
    
    # Register index route
    from app.routes import index_bp
    app.register_blueprint(index_bp)
    
    return app
