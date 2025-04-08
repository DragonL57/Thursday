"""
Provider fallback management for handling rate limits
"""
import time
import os
from flask import g, has_app_context
import config as conf

class ProviderManager:
    """
    Manages provider selection for models with multiple provider options.
    """
    
    # Constants for provider names
    POLLINATIONS = 'pollinations'
    LITELLM = 'litellm'
    
    # Provider configurations for different models
    MODEL_PROVIDERS = {
        'pollinations-gpt4o': {
            'provider': POLLINATIONS,
            'model_name': 'openai-large',
        },
        'github-gpt4o': {
            'provider': LITELLM, 
            'model_name': 'github/gpt-4o',
            'env_var': 'GITHUB_API_KEY'  # Required environment variable
        }
        # Add more integrated models here as needed
    }
    
    # Class-level storage for non-Flask contexts
    _current_providers = {}
    
    @classmethod
    def initialize(cls):
        """Initialize provider manager with default settings"""
        # Check environment variables for required providers
        for model_key, config in cls.MODEL_PROVIDERS.items():
            if 'env_var' in config:
                env_var = config['env_var']
                if not os.environ.get(env_var) and hasattr(conf, env_var):
                    # Try to get it from config if it exists
                    os.environ[env_var] = getattr(conf, env_var)
        
        # No other initialization needed currently
        return True
    
    @classmethod
    def get_provider_and_model(cls, model_key):
        """Get the provider and model name for a given model key"""
        # Handle legacy integrated model name
        if model_key == 'gpt4o':
            # Default to pollinations for the legacy integration
            return cls.POLLINATIONS, 'openai-large'
        
        if model_key not in cls.MODEL_PROVIDERS:
            # Default to pollinations for unknown models
            return cls.POLLINATIONS, model_key
        
        model_config = cls.MODEL_PROVIDERS[model_key]
        return model_config['provider'], model_config['model_name']
