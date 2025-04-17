"""
Settings-related routes for the application
"""

from flask import Blueprint, jsonify, request, current_app
from flask.views import MethodView
import config as conf
import json
import os

# Import the provider manager
from utils.provider_manager import ProviderManager

settings_bp = Blueprint('settings', __name__, url_prefix='/api')

class SettingsAPI(MethodView):
    """API for getting and updating settings"""
    
    def get(self):
        """Get current settings"""
        # Initialize provider manager if needed
        ProviderManager.initialize()
        
        # Build available models list with proper names
        models = [
            {
                'id': 'openai-large',
                'name': 'GPT-4o',
                'provider': 'pollinations',
                'display_name': 'Pollinations: OpenAI (openai)',
                'api_name': 'openai'  # Don't modify, send as openai
            },
            {
                'id': 'github/gpt-4o',
                'name': 'GPT-4o',
                'provider': 'github',
                'display_name': 'GitHub: GPT-4o (github/gpt-4o)',
                'api_name': 'github/gpt-4o'  # LiteLLM model name
            },
            {
                'id': 'gemini/gemini-2.0-flash',
                'name': 'Gemini 2.0 Flash',
                'provider': 'litellm',
                'display_name': 'LiteLLM: Gemini 2.0 Flash (gemini/gemini-2.0-flash)',
                'api_name': 'gemini/gemini-2.0-flash'
            }
        ]
        
        # Return settings
        return jsonify({
            'provider': getattr(conf, 'API_PROVIDER', 'pollinations'),
            'model': getattr(conf, 'MODEL', 'openai'),
            'temperature': getattr(conf, 'TEMPERATURE', 1.0),
            'max_tokens': getattr(conf, 'MAX_TOKENS', 8192),
            'save_history': getattr(conf, 'SAVE_HISTORY', True),
            'available_models': models
        })
    
    def post(self):
        """Update settings"""
        settings = request.json
        
        # Update config
        updated_settings = conf.update_config(settings)
        
        return jsonify({
            'status': 'success',
            'message': 'Settings updated successfully',
            'settings': updated_settings
        })

# Register routes
settings_view = SettingsAPI.as_view('settings')
settings_bp.add_url_rule('/settings', view_func=settings_view, methods=['GET', 'POST'])
