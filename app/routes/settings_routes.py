"""
Settings-related routes
"""

from flask import Blueprint, jsonify, request, session, current_app
import config as conf

settings_bp = Blueprint('settings', __name__)

@settings_bp.route('/settings', methods=['POST'])
def update_settings():
    try:
        settings = request.json
        session_id = session.get('user_id', request.remote_addr)
        
        # Update the config.py values
        updated_settings = conf.update_config(settings)
        
        # Update active assistant instances
        if session_id in current_app.assistants:
            assistant = current_app.assistants[session_id]
            if settings.get('provider'):
                conf.API_PROVIDER = settings.get('provider')
                assistant.update_provider(settings.get('provider'))
                
            if settings.get('model'):
                assistant.model = settings['model']
            
            # Some models might allow temperature updates
            if 'temperature' in settings and hasattr(current_app.assistants[session_id], 'set_temperature'):
                try:
                    current_app.assistants[session_id].set_temperature(float(settings['temperature']))
                except (AttributeError, ValueError):
                    pass
        
        return jsonify({"status": "Settings updated successfully", "settings": updated_settings})
    except Exception as e:
        return jsonify({"error": f"Failed to update settings: {str(e)}"}), 500

# Path must be /api/settings, not settings/api
@settings_bp.route('/api/settings', methods=['GET', 'POST'])
def handle_api_settings():
    if request.method == 'POST':
        data = request.json
        
        # Update the global assistant with new settings
        if current_app.assistant:
            if data.get('provider'):
                conf.API_PROVIDER = data.get('provider')
                current_app.assistant.update_provider(data.get('provider'))
            if data.get('model'):
                current_app.assistant.model = data.get('model')
            
        # Store settings in session
        session['settings'] = {
            'provider': data.get('provider', conf.API_PROVIDER),
            'model': data.get('model', conf.MODEL),
            'temperature': data.get('temperature', conf.TEMPERATURE),
            'max_tokens': data.get('max_tokens', conf.MAX_TOKENS),
            'save_history': data.get('save_history', getattr(conf, 'SAVE_HISTORY', False))
        }
        
        return jsonify({"status": "success", "message": "Settings updated"})
    
    # GET request - return current settings
    settings = session.get('settings', {
        'provider': conf.API_PROVIDER,
        'model': conf.MODEL,
        'temperature': conf.TEMPERATURE,
        'max_tokens': conf.MAX_TOKENS,
        'save_history': getattr(conf, 'SAVE_HISTORY', False)
    })
    
    return jsonify(settings)
