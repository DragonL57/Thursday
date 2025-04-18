"""
All project configuration will be saved here

Needs restart if anything is changed here.
"""
import os  # Add os import for getenv
import platform  # Add platform import for system() function
import datetime  # Add datetime import for timestamp functions
import requests  # Add requests import for HTTP requests

# Import prompts from the prompts module
from prompts import (
    get_system_prompt,
    get_persona_prompt,
    get_core_system_prompt,
    NAME,
    PERSONA_ROLE,
    RESPONSE_STYLE,
    INCLUDE_USER_CONTEXT
)

# --- Provider Configuration ---
API_PROVIDER = 'litellm'  # Set default API provider to litellm
DEFAULT_MODEL = 'gemini/gemini-2.5-flash-preview-04-17'
AVAILABLE_MODELS = [
    'gemini/gemini-2.0-flash',
    'gemini/gemini-2.5-flash-preview-04-17'
]

# --- Model Configuration ---
# For LiteLLM provider, use provider/model format
MODEL = "gemini/gemini-2.5-flash-preview-04-17"  # Default model

# --- Provider-specific Documentation ---
# LiteLLM models (always in provider/model format):
#   - 'gemini/gemini-2.0-flash' - Google's Gemini 2.0 Flash

# --- API Keys (Loaded from .env) ---
# LiteLLM automatically reads these from environment variables if set
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY") # For gemini/... models via Google AI Studio

# --- Model Parameters ---
TEMPERATURE = 1
TOP_P = None
MAX_TOKENS = 65000
SEED = None

# --- Script parameters ---
# Whether to clear the console before starting
CLEAR_BEFORE_START = True

# --- Provider fallback settings ---
# No fallback needed with only one provider
ENABLE_PROVIDER_FALLBACK = False

# --- API Request Settings ---
WEB_REQUEST_TIMEOUT = 60  # API request timeout (seconds)
API_RETRY_COUNT = 3      # Number of retries for failed requests
API_BASE_DELAY = 1.0     # Base delay between retries (seconds)
API_MAX_DELAY = 10.0     # Maximum delay between retries (seconds)

# --- Search Settings ---
# The max amount of results duckduckgo search tool can return
MAX_DUCKDUCKGO_SEARCH_RESULTS: int = 4

# Default region for DuckDuckGo searches (None = automatic)
DEFAULT_SEARCH_REGION: str = None 

# Default timeout for web requests in seconds
WEB_REQUEST_TIMEOUT: int = 30

# Timeout for DuckDuckGo searches
DUCKDUCKGO_TIMEOUT: int = 5

# Add a method to update the configuration
def update_config(settings):
    """Update configuration values."""
    global MODEL, TEMPERATURE, MAX_TOKENS, SAVE_HISTORY, API_PROVIDER
    
    if 'provider' in settings:
        API_PROVIDER = settings['provider']
        print(f"Updated provider to: {API_PROVIDER}")
    
    if 'model' in settings:
        MODEL = settings['model']
        print(f"Updated model to: {MODEL}")
    
    if 'temperature' in settings:
        TEMPERATURE = float(settings['temperature'])
        print(f"Updated temperature to: {TEMPERATURE}")
    
    if 'max_tokens' in settings:
        MAX_TOKENS = int(settings['max_tokens'])
        print(f"Updated max_tokens to: {MAX_TOKENS}")
    
    if 'save_history' in settings:
        SAVE_HISTORY = settings['save_history']
    
    return {
        'provider': API_PROVIDER,
        'model': MODEL,
        'temperature': TEMPERATURE,
        'max_tokens': MAX_TOKENS,
        'save_history': SAVE_HISTORY if 'SAVE_HISTORY' in globals() else True
    }

# Debug - print current settings on startup
print(f"Initial config: PROVIDER={API_PROVIDER}, MODEL={MODEL}, TEMPERATURE={TEMPERATURE}, MAX_TOKENS={MAX_TOKENS}")
