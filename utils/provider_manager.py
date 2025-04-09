"""
Provider Manager utility to handle provider fallbacks and model naming
"""

import os
import random

class ProviderManager:
    """
    Manages providers and their models to ensure consistent naming and behavior
    """
    # Provider constants
    POLLINATIONS = 'pollinations'
    LITELLM = 'litellm'
    
    # Normalized model names - DON'T map openai-large to openai
    MODEL_MAPPING = {
        # Do NOT map 'openai-large' to 'openai' - use as-is for API calls
        'gpt-4o': 'openai-large',  # Map gpt-4o variants to openai-large
        'gpt4o': 'openai-large',   # Map gpt4o variants to openai-large
    }
    
    # Track providers and failover state
    _initialized = False
    _use_primary_prob = {}  # Probability of using primary provider per model family
    _failure_count = {}     # Track failures per provider/model
    
    @classmethod
    def initialize(cls):
        """Initialize the provider manager."""
        if not cls._initialized:
            cls._initialized = True
            cls._use_primary_prob = {
                'gpt4o': 0.9,  # 90% chance to use primary provider for GPT-4o
            }
            cls._failure_count = {}
    
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
        if provider == cls.POLLINATIONS:
            # For Pollinations, check if we need to normalize the name
            return cls.MODEL_MAPPING.get(model_name, model_name)
        
        # For other providers, return as is
        return model_name
    
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
            
        # Handle specific model families
        if model_family == 'gpt4o' or model_family == 'pollinations-gpt4o':
            # Decide whether to use Pollinations or fallback to GitHub
            use_pollinations = cls.should_use_primary('gpt4o')
            
            if use_pollinations:
                # Return openai-large as is, no normalization needed
                return cls.POLLINATIONS, 'openai-large'
            else:
                return cls.LITELLM, 'github/gpt-4o'
                
        elif model_family == 'github-gpt4o':
            # Force GitHub provider
            return cls.LITELLM, 'github/gpt-4o'
            
        # Default to Pollinations for unknown model families
        return cls.POLLINATIONS, model_family
    
    @classmethod
    def should_use_primary(cls, model_family):
        """
        Determine if we should use the primary provider for a model family
        
        Args:
            model_family: The model family name
            
        Returns:
            Boolean indicating whether to use primary provider
        """
        if model_family not in cls._use_primary_prob:
            return True
            
        # Get current probability
        prob = cls._use_primary_prob.get(model_family, 0.9)
        
        # Make the random decision
        return random.random() < prob
    
    @classmethod
    def handle_rate_limit(cls, model_family):
        """
        Handle a rate limit error from the primary provider
        
        Args:
            model_family: The model family that encountered the error
            
        Returns:
            Dict with fallback provider and model name or None if no fallback
        """
        if model_family == 'gpt4o':
            # Decrease probability of using primary for this model family
            cls._use_primary_prob[model_family] = max(0.1, cls._use_primary_prob.get(model_family, 0.9) - 0.3)
            print(f"Reduced primary provider probability to {cls._use_primary_prob[model_family]}")
            
            # Return fallback info
            return {
                'provider': cls.LITELLM,
                'model_name': 'github/gpt-4o'
            }
            
        # No fallback for other model families
        return None
