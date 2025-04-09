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
    Add or create a note with structured content to build comprehensive responses.
    
    Notes are TEMPORARY and exist only while responding to the current user message.
    They reset automatically when a new user message arrives, so use them for organizing 
    your thoughts and structuring information for the current response.
    
    <comprehensive_note_taking>
        <primary_directive>
            The user ALWAYS wants COMPREHENSIVE answers. Your notes should contain
            significantly MORE information than what will appear in your final response,
            giving you a rich knowledge base to draw from when crafting your answer.
        </primary_directive>
        
        <strategy name="exhaustive_documentation">
            <title>CREATE EXHAUSTIVE NOTES</title>
            <instruction>Capture ALL relevant information from your research</instruction>
            <instruction>Include FULL context, details, examples, and supporting evidence</instruction>
            <instruction>Store complete data rather than summaries when possible</instruction>
            <instruction>Don't filter information at the note-taking stage; keep everything that could be useful</instruction>
            <instruction>Document contradictions, uncertainties, and limitations in the information</instruction>
            <instruction>Record technical details, specifications, parameters, and metrics with precision</instruction>
            <instruction>Preserve original wording for important definitions and concepts</instruction>
        </strategy>
        
        <strategy name="structured_organization">
            <title>STRUCTURED INFORMATION ORGANIZATION</title>
            <instruction>Use descriptive topics for easy reference (e.g., "Research Plan", "API Documentation", "Technical Analysis")</instruction>
            <instruction>Create logical sections within each topic (e.g., "Key Findings", "Limitations", "Examples")</instruction>
            <instruction>Maintain hierarchical organization for complex topics</instruction>
            <instruction>Use consistent naming conventions for easier retrieval</instruction>
            <instruction>Group related information under common topics</instruction>
            <instruction>Create dedicated sections for different aspects of the subject</instruction>
            <instruction>Separate factual information from analysis and interpretation</instruction>
        </strategy>
        
        <strategy name="source_documentation">
            <title>SOURCE DOCUMENTATION</title>
            <instruction>ALWAYS include complete source information (URLs, titles, authors, publication dates)</instruction>
            <instruction>Note the credibility and relevance of each source</instruction>
            <instruction>Track which tool was used to retrieve the information</instruction>
            <instruction>Tag information with timestamp if time-sensitive</instruction>
            <instruction>Document the reliability assessment of each source</instruction>
            <instruction>Note any potential biases or limitations in source material</instruction>
            <instruction>Preserve citation information for academic or technical sources</instruction>
            <instruction>Track version numbers or last-updated dates for technical documentation</instruction>
        </strategy>
        
        <strategy name="content_detailing">
            <title>DETAILED CONTENT STRATEGIES</title>
            <content_type type="code">
                <instruction>Include full implementation details, not just snippets</instruction>
                <instruction>Document function signatures, parameters, and return values</instruction>
                <instruction>Note language versions, dependencies, and compatibility information</instruction>
                <instruction>Record usage examples and expected outputs</instruction>
                <instruction>Include initialization or setup requirements</instruction>
            </content_type>
            <content_type type="concepts">
                <instruction>Record definitions, examples, edge cases, and alternatives</instruction>
                <instruction>Document historical context and evolution of ideas</instruction>
                <instruction>Note relationships between related concepts</instruction>
                <instruction>Include different interpretations or schools of thought</instruction>
            </content_type>
            <content_type type="research">
                <instruction>Note methodology, key findings, limitations, and implications</instruction>
                <instruction>Record sample sizes, confidence intervals, and statistical significance</instruction>
                <instruction>Document experimental conditions and controls</instruction>
                <instruction>Include critiques and alternative interpretations</instruction>
            </content_type>
            <content_type type="factual_data">
                <instruction>Include statistics, dates, specific numbers, and contextual details</instruction>
                <instruction>Document units of measurement and data collection methods</instruction>
                <instruction>Note margins of error or data quality issues</instruction>
                <instruction>Record trends, patterns, and anomalies</instruction>
            </content_type>
            <content_type type="arguments">
                <instruction>Document multiple perspectives with supporting evidence</instruction>
                <instruction>Record the strongest arguments for each position</instruction>
                <instruction>Note common objections and responses</instruction>
                <instruction>Include expert consensus and dissenting opinions</instruction>
            </content_type>
        </strategy>
        
        <strategy name="optimal_workflow">
            <title>OPTIMAL USE PATTERNS</title>
            <workflow_step>Create a planning note FIRST to outline your approach</workflow_step>
            <workflow_step>Take detailed notes for EACH distinct source or concept</workflow_step>
            <workflow_step>Create summary notes that synthesize information across sources</workflow_step>
            <workflow_step>Use the append=True parameter to build notes incrementally</workflow_step>
            <workflow_step>Review notes with get_notes() before formulating your final response</workflow_step>
            <workflow_step>Create comparison notes to highlight agreements and contradictions</workflow_step>
            <workflow_step>Update your research plan based on what you discover</workflow_step>
            <workflow_step>Organize final insights in a dedicated "Synthesis" note</workflow_step>
        </strategy>
    </comprehensive_note_taking>
    
    Args:
        content: The content to store in the note (be extremely detailed and comprehensive)
        topic: Topic/category for the note (e.g., "Research Plan", "Source: Website Title", "Technical Analysis")
        section: Optional section name within the note (e.g., "Key Findings", "Methodology", "Examples") 
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
    Update an existing note with new content for more comprehensive responses.
    
    Remember that notes are TEMPORARY and reset with each new user message.
    Use them for organizing your thinking process while responding to the current query.
    
    <comprehensive_update_strategies>
        <primary_directive>
            Comprehensive notes lead to comprehensive responses. Your updates should enrich your 
            knowledge base to ensure you can provide the most detailed, accurate, and valuable 
            response to the user.
        </primary_directive>
        
        <strategy name="expand_information">
            <title>EXPAND EXISTING INFORMATION</title>
            <instruction>Add more details, examples, and supporting evidence to existing notes</instruction>
            <instruction>Include counterarguments or alternative perspectives for balanced coverage</instruction>
            <instruction>Provide additional context that clarifies or strengthens your initial points</instruction>
            <instruction>Add technical specifications, parameters, or implementation details</instruction>
            <instruction>Incorporate historical background and future implications</instruction>
            <instruction>Add visual descriptions, analogies, and metaphors to enhance understanding</instruction>
            <instruction>Include step-by-step procedures and workflows where applicable</instruction>
        </strategy>
        
        <strategy name="refine_findings">
            <title>REFINE WITH NEW FINDINGS</title>
            <instruction>Update notes when you discover more accurate or current information</instruction>
            <instruction>Correct inaccuracies or outdated information as you learn more</instruction>
            <instruction>Add nuance to oversimplified initial assessments</instruction>
            <instruction>Link related concepts across different notes through cross-references</instruction>
            <instruction>Clarify ambiguities and resolve contradictions</instruction>
            <instruction>Update statistical data and numerical information with latest values</instruction>
            <instruction>Add expert opinions and authoritative perspectives</instruction>
            <instruction>Document evolving understanding as research progresses</instruction>
        </strategy>
        
        <strategy name="operation_selection">
            <title>OPERATION SELECTION STRATEGY</title>
            <instruction>Use "append" to add new information while preserving existing content</instruction>
            <instruction>Use "prepend" to prioritize new information before existing content</instruction>
            <instruction>Use "replace" only when information needs complete revision</instruction>
            <instruction>Consider creating new sections instead of replacing entire notes</instruction>
            <instruction>For critical updates, use "prepend" to ensure visibility</instruction>
            <instruction>For supplementary details, use "append" to maintain narrative flow</instruction>
            <instruction>When information becomes obsolete, use "replace" for accuracy</instruction>
        </strategy>
        
        <strategy name="section_organization">
            <title>SECTION-BASED ORGANIZATION</title>
            <instruction>Update specific sections to maintain clear information boundaries</instruction>
            <instruction>Create new sections for newly discovered categories of information</instruction>
            <instruction>Use consistent section naming across related notes</instruction>
            <instruction>Consider how sections will support your final response structure</instruction>
            <instruction>Group related information under common section headings</instruction>
            <instruction>Create specialized sections for technical details, examples, and analysis</instruction>
            <instruction>Maintain a "Key Insights" section for critical findings</instruction>
            <instruction>Add "Limitations" and "Open Questions" sections for intellectual honesty</instruction>
        </strategy>
        
        <strategy name="synthesis_management">
            <title>SYNTHESIS UPDATES</title>
            <instruction>Periodically update summary notes to incorporate new findings</instruction>
            <instruction>Create connections between disparate pieces of information</instruction>
            <instruction>Highlight contradictions or agreements between different sources</instruction>
            <instruction>Update your research plan based on what you've learned so far</instruction>
            <instruction>Identify emerging patterns and trends across multiple sources</instruction>
            <instruction>Construct comprehensive timelines for historical or sequential topics</instruction>
            <instruction>Develop comparative analyses when multiple approaches exist</instruction>
            <instruction>Build evidence hierarchies showing stronger and weaker support for conclusions</instruction>
        </strategy>
    </comprehensive_update_strategies>
    
    Args:
        note_id: The ID of the note to update
        new_content: The new content to update the note with (be extremely detailed)
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
    
    <comprehensive_note_retrieval>
        <primary_directive>
            Always review your notes thoroughly before formulating your final response.
            The detailed information you've collected is essential for delivering the 
            comprehensive answers the user expects.
        </primary_directive>
        
        <format_selection_guide>
            <format type="default">
                <description>Standard readable format with all content</description>
                <best_for>Quick reference during response preparation</best_for>
                <features>Shows all note content with clear topic and section labeling</features>
            </format>
            
            <format type="markdown">
                <description>Well-structured markdown with proper headings</description>
                <best_for>Creating organized content that can be directly incorporated into responses</best_for>
                <features>Uses markdown heading levels to reflect the hierarchical structure of notes</features>
            </format>
            
            <format type="compact">
                <description>Condensed overview of available notes</description>
                <best_for>Getting a quick overview of what information has been collected</best_for>
                <features>Shows topics, section names, and brief content excerpts</features>
            </format>
            
            <format type="structured">
                <description>Highly detailed format with clear visual separators</description>
                <best_for>Detailed analysis when preparing complex, multi-faceted responses</best_for>
                <features>Includes creation dates, clear section boundaries, and comprehensive content organization</features>
            </format>
        </format_selection_guide>
        
        <effective_note_review>
            <strategy name="comparative_analysis">
                <instruction>Compare information across multiple notes to identify patterns and inconsistencies</instruction>
                <instruction>Look for complementary information that builds a more complete picture</instruction>
                <instruction>Identify conflicts or contradictions that need reconciliation</instruction>
                <instruction>Note where sources agree to strengthen confidence in those points</instruction>
            </strategy>
            
            <strategy name="completeness_check">
                <instruction>Review all relevant notes to ensure no important information is missed</instruction>
                <instruction>Check that all aspects of the user's question are addressed in your notes</instruction>
                <instruction>Identify any remaining information gaps that might need attention</instruction>
                <instruction>Verify that you have both factual details and analytical insights</instruction>
            </strategy>
            
            <strategy name="synthesis_preparation">
                <instruction>Identify the most significant findings across all notes</instruction>
                <instruction>Prioritize information based on relevance to the user's query</instruction>
                <instruction>Plan how different pieces of information will connect in your response</instruction>
                <instruction>Note which sources to cite for key claims in your answer</instruction>
            </strategy>
            
            <strategy name="response_structuring">
                <instruction>Use note categories and sections to inform your response structure</instruction>
                <instruction>Identify natural groupings of information for logical presentation</instruction>
                <instruction>Plan a narrative flow that builds from fundamental to advanced concepts</instruction>
                <instruction>Ensure critical insights from notes are prominently featured</instruction>
            </strategy>
        </effective_note_review>
    </comprehensive_note_retrieval>
    
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
