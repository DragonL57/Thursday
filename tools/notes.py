"""
Note-taking tools for the assistant to store, retrieve and refine information.

Notes are temporary and reset with each new user message, making them ideal for
planning and organizing your response to the current question.
"""

import os
import json
from datetime import datetime
from .formatting import tool_message_print, tool_report_print

# Global notes storage (in-memory for simplicity)
_notes_storage = []

# Track conversation message ID to enable auto-reset
_current_message_id = None

def _reset_notes_if_new_message(message_id=None):
    """Reset notes storage if this is a new message ID"""
    global _notes_storage, _current_message_id
    
    # If no message ID is provided, always reset
    if message_id is None:
        _notes_storage = []
        _current_message_id = None
        return True
    
    # If this is a different message than the one we're tracking, reset notes
    if _current_message_id != message_id:
        _notes_storage = []
        _current_message_id = message_id
        return True
    
    return False

def add_note(content: str, topic: str = None, section: str = None, append: bool = False, message_id: str = None) -> str:
    """
    Add or create a note with structured content.
    
    Notes are TEMPORARY and exist only while responding to the current user message.
    They reset automatically when a new user message arrives, so use them for organizing 
    your thoughts and structuring information for the current response.
    
    Strategic uses:
    - Create an outline before research
    - Document findings from web searches or tool calls
    - Organize complex information into sections
    - Track key information for your final response
    
    Args:
        content: The content to store in the note
        topic: Topic/category for the note (e.g., "Research Plan", "Code Analysis")
        section: Optional section name within the note (e.g., "Key Points", "Background")
        append: Whether to append to an existing note with the same topic (default: False)
        message_id: Internal parameter to track conversation state (don't use manually)
        
    Returns:
        Confirmation message with the stored note ID
    """
    global _notes_storage
    
    # Check if we need to reset notes for a new message
    if message_id is not None:
        reset_happened = _reset_notes_if_new_message(message_id)
        if reset_happened:
            tool_message_print("add_note", [
                ("action", "auto_reset"),
                ("reason", "new_user_message")
            ])
    
    timestamp = datetime.now().isoformat()
    
    # Check if we should append to an existing note
    if append and topic:
        existing_notes = [note for note in _notes_storage if note["topic"] == topic]
        if existing_notes:
            existing_note = existing_notes[0]  # Use the first matching note
            
            # Handle section-specific append if section is provided
            if section and "sections" in existing_note:
                if section in existing_note["sections"]:
                    existing_note["sections"][section] += f"\n\n{content}"
                else:
                    existing_note["sections"][section] = content
            else:
                # Append to main content
                existing_note["content"] += f"\n\n{content}"
                
            existing_note["updated_at"] = timestamp
            
            tool_message_print("add_note", [
                ("action", "append"),
                ("topic", existing_note["topic"]),
                ("section", section if section else "main"),
                ("content", content)
            ])
            
            tool_report_print(f"Note #{existing_note['id']} updated:", 
                             f"Topic: {existing_note['topic']}\n" +
                             (f"Section: {section}\n" if section else "") + 
                             f"Content: {content}")
            
            return f"Note #{existing_note['id']} successfully updated."
    
    # Create a new note
    note_id = len(_notes_storage) + 1
    
    note = {
        "id": note_id,
        "topic": topic if topic else "General",
        "content": content,
        "created_at": timestamp,
        "updated_at": timestamp
    }
    
    # Add sections if specified
    if section:
        note["sections"] = {section: content}
        # Clear main content if we're using sections
        note["content"] = ""
    
    _notes_storage.append(note)
    
    tool_message_print("add_note", [
        ("action", "create"),
        ("topic", note["topic"]),
        ("section", section if section else "main"),
        ("content", content)
    ])
    
    tool_report_print(f"Note #{note_id} added:", 
                     f"Topic: {note['topic']}\n" +
                     (f"Section: {section}\n" if section else "") + 
                     f"Content: {content}")
    
    return f"Note #{note_id} successfully added with topic '{note['topic']}'" + (f" and section '{section}'" if section else "") + "."

def update_note(note_id: int, new_content: str, section: str = None, operation: str = "replace") -> str:
    """
    Update an existing note with new content.
    
    Remember that notes are TEMPORARY and reset with each new user message.
    Use them for organizing your thinking process while responding to the current query.
    
    Args:
        note_id: The ID of the note to update
        new_content: The new content to update the note with
        section: Optional section name to update (if note has sections)
        operation: How to update the content - "replace" (default), "append", or "prepend"
        
    Returns:
        Confirmation message
    """
    global _notes_storage
    
    try:
        # Convert to 0-based index
        idx = note_id - 1
        if idx < 0 or idx >= len(_notes_storage):
            error_msg = f"Note #{note_id} not found."
            tool_report_print("Error:", error_msg)
            return error_msg
            
        note = _notes_storage[idx]
        topic = note["topic"]
        
        # Update the specified section
        if section and "sections" in note:
            if section in note["sections"]:
                current_content = note["sections"][section]
                if operation == "replace":
                    note["sections"][section] = new_content
                elif operation == "append":
                    note["sections"][section] = current_content + "\n\n" + new_content
                elif operation == "prepend":
                    note["sections"][section] = new_content + "\n\n" + current_content
            else:
                # Create new section
                note["sections"][section] = new_content
        else:
            # Update main content
            current_content = note["content"]
            if operation == "replace":
                note["content"] = new_content
            elif operation == "append":
                note["content"] = current_content + "\n\n" + new_content
            elif operation == "prepend":
                note["content"] = new_content + "\n\n" + current_content
        
        note["updated_at"] = datetime.now().isoformat()
        
        tool_message_print("update_note", [
            ("note_id", note_id),
            ("topic", topic),
            ("section", section if section else "main"),
            ("operation", operation),
            ("content", new_content)
        ])
        
        tool_report_print(f"Note #{note_id} updated:", 
                         f"Topic: {topic}\n" +
                         (f"Section: {section}\n" if section else "") + 
                         f"Operation: {operation}\n" +
                         f"Content: {new_content}")
        
        return f"Note #{note_id} successfully updated."
    except Exception as e:
        error_msg = f"Error updating note: {str(e)}"
        tool_report_print("Error:", error_msg)
        return error_msg

def get_notes(topic: str = None, format: str = "default") -> str:
    """
    Retrieve notes, optionally filtered by topic.
    
    Notes are temporary planning tools that only exist during the current response.
    They will be reset when the next user message arrives.
    
    Args:
        topic: Optional topic filter
        format: Output format ("default", "markdown", "compact", or "structured")
        
    Returns:
        A formatted string containing all matching notes
    """
    global _notes_storage
    
    if not _notes_storage:
        return "No notes available. Notes are temporary and reset with each new user message."
        
    # Filter by topic if provided
    if topic:
        filtered_notes = [note for note in _notes_storage if note["topic"].lower() == topic.lower()]
    else:
        filtered_notes = _notes_storage
    
    if not filtered_notes:
        return f"No notes found for topic: {topic}"
    
    # Format the notes according to the specified format
    if format == "markdown":
        result = "# Collected Notes\n\n"
        for note in filtered_notes:
            result += f"## Note {note['id']}: {note['topic']}\n\n"
            
            if "sections" in note and note["sections"]:
                for section_name, section_content in note["sections"].items():
                    result += f"### {section_name}\n\n{section_content}\n\n"
            
            if note["content"]:
                result += note["content"] + "\n\n"
    
    elif format == "compact":
        result = "Notes Summary:\n\n"
        for note in filtered_notes:
            result += f"• Note {note['id']} - {note['topic']}\n"
            
            if "sections" in note and note["sections"]:
                section_names = list(note["sections"].keys())
                result += f"  Sections: {', '.join(section_names)}\n"
            
            # Add a brief excerpt from content
            content = note["content"]
            if content:
                excerpt = (content[:60] + '...') if len(content) > 60 else content
                result += f"  Excerpt: {excerpt}\n"
                
            result += "\n"
    
    elif format == "structured":
        result = "STRUCTURED NOTES:\n\n"
        for note in filtered_notes:
            result += f"NOTE {note['id']} - {note['topic'].upper()}\n"
            result += f"Created: {note['created_at'][:10]} | Updated: {note['updated_at'][:10]}\n"
            result += "=" * 40 + "\n\n"
            
            if "sections" in note and note["sections"]:
                for section_name, section_content in note["sections"].items():
                    result += f"*** {section_name.upper()} ***\n{section_content}\n\n"
            
            if note["content"]:
                if "sections" in note and note["sections"]:
                    result += "*** MAIN CONTENT ***\n"
                result += note["content"] + "\n\n"
                
            result += "-" * 40 + "\n\n"
    
    else:  # default format
        result = "Collected Notes:\n\n"
        for note in filtered_notes:
            result += f"Note #{note['id']} - {note['topic']}:\n"
            
            if "sections" in note and note["sections"]:
                for section_name, section_content in note["sections"].items():
                    result += f"--- {section_name} ---\n{section_content}\n\n"
            
            if note["content"]:
                result += note["content"] + "\n\n"
    
    # Add reminder about ephemeral nature of notes
    result += "\n(Note: These notes are temporary and will be reset with the next user message.)\n"
    
    tool_message_print("get_notes", [
        ("topic", topic if topic else "All"),
        ("format", format),
        ("count", len(filtered_notes))
    ])
    
    tool_report_print("Retrieved notes:", result)
    
    return result

def clear_notes() -> str:
    """
    Clear all stored notes.
    
    This happens automatically between user messages, so this is mainly useful
    if you want to start fresh in the middle of responding to a message.
    
    Returns:
        Confirmation message
    """
    global _notes_storage
    
    count = len(_notes_storage)
    _notes_storage = []
    
    tool_message_print("clear_notes", [
        ("count", count)
    ])
    
    tool_report_print(f"Cleared all {count} notes.")
    
    return f"Successfully cleared all {count} notes. Note that notes are automatically cleared when a new user message arrives."

# Function to force a reset (for use by the framework)
def reset_notes():
    """Reset all notes - called automatically at the start of processing each new user message"""
    global _notes_storage
    _notes_storage = []
    return True
