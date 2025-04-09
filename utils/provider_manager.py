"""
Provider Manager utility to handle provider fallbacks and model naming
"""

import os

class ProviderManager:
    """
    Manages providers and their models to ensure consistent naming and behavior
    """
    # Provider constants
    LITELLM = 'litellm'
    
    # Model mappings for standardization - only keep mappings for the two supported models
    MODEL_MAPPING = {
        'gpt-4o': 'github/gpt-4o',
        'gemini': 'gemini/gemini-2.0-flash'
    }
    
    # Track initialization
    _initialized = False
    
    @classmethod
    def initialize(cls):
        """Initialize the provider manager."""
        if not cls._initialized:
            cls._initialized = True
    
    @classmethod
    def normalize_model_name(cls, provider, model_name):
        """
        Normalize model name for a specific provider
        
        Args:
            provider: Provider name 
            model_name: Original model name
            
        Returns:
            Normalized model name for the provider
        """
        # If model is already in the proper format, return it
        if model_name in ['github/gpt-4o', 'gemini/gemini-2.0-flash']:
            return model_name
            
        # Otherwise, try to map it
        return cls.MODEL_MAPPING.get(model_name, model_name)
    
    @classmethod
    def get_provider_and_model(cls, model_family):
        """
        Get the appropriate provider and model name for a model family
        
        Args:
            model_family: The model family (e.g., 'gpt4o') 
            
        Returns:
            Tuple of (provider, model_name)
        """
        # Initialize if needed
        if not cls._initialized:
            cls.initialize()
        
        # Map directly to one of our two supported models
        if model_family in ['gpt4o', 'pollinations-gpt4o', 'openai-large', 'github-gpt4o', 'gpt-4o']:
            return cls.LITELLM, 'github/gpt-4o'
        elif model_family in ['gemini', 'gemini-2.0-flash']:
            return cls.LITELLM, 'gemini/gemini-2.0-flash'
        
        # If the model already includes the provider format, use it directly
        if '/' in model_family:
            return cls.LITELLM, model_family
        
        # Default to GPT-4o if unknown
        return cls.LITELLM, 'github/gpt-4o'
    
    @classmethod
    def should_use_primary(cls, model_family):
        """Always returns False as we only use LiteLLM now"""
        return False
