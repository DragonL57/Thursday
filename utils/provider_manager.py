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
    
    # Model mappings for standardization - only keep mappings for the supported model
    MODEL_MAPPING = {
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
        if model_name in ['gemini/gemini-2.0-flash']:
            return model_name
            
        # Otherwise, try to map it
        return cls.MODEL_MAPPING.get(model_name, model_name)
    
    @classmethod
    def get_provider_and_model(cls, model_family):
        """
        Get the appropriate provider and model name for a model family
        
        Args:
            model_family: The model family (e.g., 'gemini') 
            
        Returns:
            Tuple of (provider, model_name)
        """
        # Initialize if needed
        if not cls._initialized:
            cls.initialize()
        
        # Map directly to our supported model
        if model_family in ['gemini', 'gemini-2.0-flash']:
            return cls.LITELLM, 'gemini/gemini-2.0-flash'
        
        # If the model already includes the provider format, use it directly
        if '/' in model_family and model_family.startswith('gemini/'):
            return cls.LITELLM, model_family
        
        # Default to Gemini
        return cls.LITELLM, 'gemini/gemini-2.0-flash'
    
    @classmethod
    def should_use_primary(cls, model_family):
        """Always returns False as we only use LiteLLM now"""
        return False
