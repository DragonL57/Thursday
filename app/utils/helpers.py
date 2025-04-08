"""
Helper functions for the application
"""

import random

def sanitize_filename(filename):
    """Sanitize a filename by replacing problematic characters."""
    # Replace slashes, colons, and other forbidden characters
    forbidden_chars = ['/', '\\', ':', '*', '?', '"', '<', '>', '|']
    sanitized = filename
    for char in forbidden_chars:
        sanitized = sanitized.replace(char, '-')
    return sanitized

def chunk_text(text, avg_chunk_size=3):
    """Split text into smaller chunks for streaming."""
    if not text:
        return []
    
    # Split by spaces but preserve them
    parts = []
    current = ""
    
    for char in text:
        current += char
        if char == ' ':
            parts.append(current)
            current = ""
    
    if current:  # Add the last part if it exists
        parts.append(current)
    
    # Now group these parts into chunks
    chunks = []
    current_chunk = []
    current_length = 0
    
    for part in parts:
        current_chunk.append(part)
        current_length += 1
        
        # Use some randomization to make it feel more natural
        if current_length >= avg_chunk_size and random.random() > 0.5:
            # Check if we should split here
            last_part = current_chunk[-1].strip()
            if (last_part.endswith(('.', '!', '?', ':', ';', ',')) or 
                current_length >= avg_chunk_size * 2):
                chunks.append(''.join(current_chunk))
                current_chunk = []
                current_length = 0
    
    # Add any remaining content
    if current_chunk:
        chunks.append(''.join(current_chunk))
    
    return chunks
