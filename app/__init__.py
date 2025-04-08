"""
Application factory module for creating and configuring the Flask app
"""

from flask import Flask, jsonify
import os
import json
import traceback
import random
from datetime import datetime

from app.utils.setup import setup_directories, setup_fonts, patch_assistant_methods
from app.utils.helpers import sanitize_filename

# Import services and modules
from assistant import Assistant
from tools import TOOLS
import config as conf

def create_app():
    """Create and configure the Flask application"""
    app = Flask(__name__, template_folder='../templates', static_folder='../static')
    app.secret_key = os.urandom(24)  # Secure secret key for session management
    
    # Setup directories and fonts
    setup_directories(app)
    setup_fonts(app)
    
    # Patch Assistant methods for save/load functionality if needed
    patch_assistant_methods(sanitize_filename)
    
    # Initialize core services
    initialize_services(app)
    
    # Register all blueprints
    register_blueprints(app)
    
    # Make TOOLS directly available to the app
    app.config['TOOLS'] = TOOLS
    
    # Add a special route to list available fonts for debugging
    @app.route('/api/debug/fonts')
    def list_fonts():
        fonts_dir = os.path.join(app.static_folder, 'fonts')
        available_fonts = []
        if os.path.exists(fonts_dir):
            available_fonts = os.listdir(fonts_dir)
        return jsonify({
            'fonts_dir': fonts_dir,
            'available_fonts': available_fonts,
            'exists': os.path.exists(fonts_dir)
        })
    
    return app

def initialize_services(app):
    """Initialize application services"""
    # Instantiate the Assistant
    try:
        sys_instruct = conf.get_system_prompt().strip()
        app.assistant = Assistant(
            model=conf.MODEL,
            system_instruction=sys_instruct,
            tools=TOOLS
        )
    except Exception as e:
        print(f"Error initializing Assistant: {e}")
        traceback.print_exc()
        app.assistant = None  # Handle initialization failure gracefully

    # Store assistants in session for multi-user support
    app.assistants = {}

def register_blueprints(app):
    """Register all route blueprints"""
    # Import blueprints
    from app.routes.main_routes import main_bp
    from app.routes.chat_routes import chat_bp
    from app.routes.settings_routes import settings_bp
    
    # Register blueprints
    app.register_blueprint(main_bp)
    app.register_blueprint(chat_bp, url_prefix='/chat')
    
    # Register the settings blueprint directly at root
    # This allows direct access to /api/settings without a prefix
    app.register_blueprint(settings_bp)
