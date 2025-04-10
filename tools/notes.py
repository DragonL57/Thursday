"""
Redesign of the note tool to support session-wide and message-specific notes, along with enhanced prompting for plans and comprehensive responses.
"""

import os
import json
from datetime import datetime
from .formatting import tool_message_print, tool_report_print

# Global storage for session-wide and message-specific notes
_session_notes = []
_message_notes = []

# Track conversation message ID to enable auto-reset for message-specific notes
_current_message_id = None

def _reset_message_notes_if_new_message(message_id=None):
    """Reset message-specific notes if this is a new message ID"""
    global _message_notes, _current_message_id

    if message_id is None or _current_message_id != message_id:
        _message_notes = []
        _current_message_id = message_id
        return True

    return False

def add_note(content: str, topic: str = None, section: str = None, append: bool = True, message_id: str = None, session_wide: bool = False) -> str:
    """
    Add a note to either session-wide or message-specific storage.

    Args:
        content: The content to store in the note.
        topic: Topic/category for the note.
        section: Optional section name within the note.
        append: Whether to append to an existing note with the same topic.
        message_id: Internal parameter to track conversation state.
        session_wide: Whether the note is session-wide (True) or message-specific (False).

    Returns:
        Confirmation message with the stored note ID.
    """
    global _session_notes, _message_notes

    # Determine the storage type
    storage = _session_notes if session_wide else _message_notes

    # Reset message-specific notes if needed
    if not session_wide and message_id is not None:
        _reset_message_notes_if_new_message(message_id)

    timestamp = datetime.now().isoformat()

    # Check if we should append to an existing note
    if topic:
        existing_notes = [note for note in storage if note["topic"] == topic]
        if existing_notes:
            existing_note = existing_notes[0]

            if section and "sections" in existing_note:
                if section in existing_note["sections"]:
                    existing_note["sections"][section] += f"\n\n{content}"
                else:
                    existing_note["sections"][section] = content
            elif section:
                if "sections" not in existing_note:
                    existing_note["sections"] = {}
                existing_note["sections"][section] = content
            else:
                existing_note["content"] += f"\n\n{content}"

            existing_note["updated_at"] = timestamp
            return f"Note #{existing_note['id']} successfully updated."

    # Create a new note
    note_id = len(storage) + 1
    note = {
        "id": note_id,
        "topic": topic if topic else "General",
        "content": content,
        "created_at": timestamp,
        "updated_at": timestamp
    }

    if section:
        note["sections"] = {section: content}
        note["content"] = ""

    storage.append(note)
    return f"Note #{note_id} successfully added to {'session-wide' if session_wide else 'message-specific'} notes."

def update_note(note_id: int, new_content: str, section: str = None, operation: str = "replace", session_wide: bool = False) -> str:
    """
    Update an existing note with new content for more comprehensive responses.

    Args:
        note_id: The ID of the note to update
        new_content: The new content to update the note with (be extremely detailed)
        section: Optional section name to update (if note has sections)
        operation: How to update the content - "replace" (default), "append", or "prepend"
        session_wide: Whether the note is session-wide (True) or message-specific (False)

    Returns:
        Confirmation message
    """
    global _session_notes, _message_notes

    storage = _session_notes if session_wide else _message_notes

    try:
        # Convert to 0-based index
        idx = note_id - 1
        if idx < 0 or idx >= len(storage):
            error_msg = f"Note #{note_id} not found."
            tool_report_print("Error:", error_msg)
            return error_msg

        note = storage[idx]
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

def get_notes(session_wide: bool = False, topic: str = None, format: str = "default") -> str:
    """
    Retrieve notes from either session-wide or message-specific storage.

    Args:
        session_wide: Whether to retrieve session-wide notes (True) or message-specific notes (False).
        topic: Optional topic filter.
        format: Output format ("default", "markdown", "compact", or "structured").

    Returns:
        A formatted string containing all matching notes.
    """
    storage = _session_notes if session_wide else _message_notes

    if not storage:
        return "No notes available."

    if topic:
        filtered_notes = [note for note in storage if note["topic"].lower() == topic.lower()]
    else:
        filtered_notes = storage

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

def clear_notes(session_wide: bool = False) -> str:
    """
    Clear all notes from either session-wide or message-specific storage.

    Args:
        session_wide: Whether to clear session-wide notes (True) or message-specific notes (False).

    Returns:
        Confirmation message.
    """
    global _session_notes, _message_notes

    storage = _session_notes if session_wide else _message_notes
    count = len(storage)
    storage.clear()

    return f"Successfully cleared all {count} {'session-wide' if session_wide else 'message-specific'} notes."

# Function to force a reset (for use by the framework)
def reset_notes():
    """Reset all notes - called automatically at the start of processing each new user message"""
    global _message_notes
    _message_notes = []
    return True
