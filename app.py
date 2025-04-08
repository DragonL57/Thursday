#!/usr/bin/env python3
"""
Thursday - Your AI Assistant
Main application entry point
"""

import os
from app import create_app

# Create and configure the Flask application
app = create_app()

if __name__ == '__main__':
    # Generate a proper secret key for production
    if getattr(app, 'secret_key', None) == b'change-me':
        app.secret_key = os.urandom(24)
    
    # Run the application
    app.run(debug=True, host='0.0.0.0', port=5000)
