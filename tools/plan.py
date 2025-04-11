"""Plan tool for the Gem Assistant.

This tool allows the AI to create and manage checklists for planning purposes.
It can be used to create a plan checklist, append context when researching,
mark items as complete, and modify the checklist based on new information.
"""

import os
import json
from datetime import datetime
from .formatting import tool_message_print, tool_report_print

# Global storage for session-wide and message-specific plans
_session_plans = []
_message_plans = []

# Track conversation message ID to enable auto-reset for message-specific plans
_current_message_id = None

def _reset_message_plans_if_new_message(message_id=None):
    """Reset message-specific plans if this is a new message ID"""
    global _message_plans, _current_message_id

    if message_id is None or _current_message_id != message_id:
        _message_plans = []
        _current_message_id = message_id
        return True

    return False

def create_plan(title: str, steps: list[str], message_id: str = None, session_wide: bool = False) -> str:
    """
    Create a new plan with a list of steps (checklist items).

    Args:
        title: Title of the plan.
        steps: List of steps/tasks to include in the plan.
        message_id: Internal parameter to track conversation state.
        session_wide: Whether the plan is session-wide (True) or message-specific (False).

    Returns:
        Confirmation message with the stored plan ID.
    """
    global _session_plans, _message_plans

    # Determine the storage type
    storage = _session_plans if session_wide else _message_plans

    # Reset message-specific plans if needed
    if not session_wide and message_id is not None:
        _reset_message_plans_if_new_message(message_id)

    timestamp = datetime.now().isoformat()

    # Check if a plan with this title already exists
    existing_plans = [plan for plan in storage if plan["title"] == title]
    if existing_plans:
        # Return the existing plan ID
        return f"Plan #{existing_plans[0]['id']} with title '{title}' already exists. Use update_plan to modify it."

    # Create a new plan with checklist items
    plan_id = len(storage) + 1
    plan = {
        "id": plan_id,
        "title": title,
        "steps": [],
        "created_at": timestamp,
        "updated_at": timestamp
    }

    # Add steps with completion status
    for step in steps:
        plan["steps"].append({
            "description": step,
            "completed": False,
            "context": "",
            "updated_at": timestamp
        })

    storage.append(plan)

    # Format the plan for display in the tool report
    formatted_plan = f"Plan: {title}\n\n"
    for i, step in enumerate(plan["steps"]):
        formatted_plan += f"[ ] {i+1}. {step['description']}\n"

    tool_message_print("create_plan", [
        ("title", title),
        ("steps_count", len(steps))
    ])

    tool_report_print(f"Plan #{plan_id} created:", formatted_plan)

    return f"Plan #{plan_id} successfully created with {len(steps)} steps."

def update_plan(plan_id: int, step_index: int, action: str = "update", new_description: str = None, 
               context: str = None, completed: bool = None, session_wide: bool = False) -> str:
    """
    Update a step in an existing plan.

    Args:
        plan_id: The ID of the plan to update.
        step_index: The index of the step to update (1-based).
        action: Action to perform - "update", "complete", "add_context".
        new_description: New description for the step if action is "update".
        context: Additional context to append to the step.
        completed: Set the completion status of the step.
        session_wide: Whether the plan is session-wide (True) or message-specific (False).

    Returns:
        Confirmation message.
    """
    global _session_plans, _message_plans

    storage = _session_plans if session_wide else _message_plans

    try:
        # Convert to 0-based index for the plan
        plan_idx = plan_id - 1
        if plan_idx < 0 or plan_idx >= len(storage):
            error_msg = f"Plan #{plan_id} not found."
            tool_report_print("Error:", error_msg)
            return error_msg

        plan = storage[plan_idx]
        title = plan["title"]
        
        # Convert to 0-based index for the step
        step_idx = step_index - 1
        if step_idx < 0 or step_idx >= len(plan["steps"]):
            error_msg = f"Step {step_index} not found in plan #{plan_id}."
            tool_report_print("Error:", error_msg)
            return error_msg

        step = plan["steps"][step_idx]
        timestamp = datetime.now().isoformat()
        
        # Update the step based on the action
        if action == "update" and new_description:
            step["description"] = new_description
        
        if context:  # Add/append context
            if step["context"]:
                step["context"] += f"\n\n{context}"
            else:
                step["context"] = context
        
        if completed is not None:  # Update completion status
            step["completed"] = completed
        
        # Update timestamps
        step["updated_at"] = timestamp
        plan["updated_at"] = timestamp

        # Format the updated plan for display
        formatted_plan = f"Updated Plan: {title}\n\n"
        for i, s in enumerate(plan["steps"]):
            status = "[x]" if s["completed"] else "[ ]"
            formatted_plan += f"{status} {i+1}. {s['description']}\n"
            if s["context"]:
                formatted_plan += f"   Context: {s['context'][:50]}...\n" if len(s["context"]) > 50 else f"   Context: {s['context']}\n"

        tool_message_print("update_plan", [
            ("plan_id", plan_id),
            ("step", step_index),
            ("action", action)
        ])

        tool_report_print(f"Plan #{plan_id} updated:", formatted_plan)

        return f"Step {step_index} in Plan #{plan_id} successfully updated."
    except Exception as e:
        error_msg = f"Error updating plan: {str(e)}"
        tool_report_print("Error:", error_msg)
        return error_msg

def add_plan_step(plan_id: int, description: str, position: int = None, session_wide: bool = False) -> str:
    """
    Add a new step to an existing plan.

    Args:
        plan_id: The ID of the plan to update.
        description: Description of the new step.
        position: Position to insert the step (1-based). If None, adds to the end.
        session_wide: Whether the plan is session-wide (True) or message-specific (False).

    Returns:
        Confirmation message.
    """
    global _session_plans, _message_plans

    storage = _session_plans if session_wide else _message_plans

    try:
        # Convert to 0-based index
        plan_idx = plan_id - 1
        if plan_idx < 0 or plan_idx >= len(storage):
            error_msg = f"Plan #{plan_id} not found."
            tool_report_print("Error:", error_msg)
            return error_msg

        plan = storage[plan_idx]
        timestamp = datetime.now().isoformat()
        
        # Create new step
        new_step = {
            "description": description,
            "completed": False,
            "context": "",
            "updated_at": timestamp
        }
        
        # Insert at specified position or append to the end
        if position is not None:
            pos_idx = position - 1  # Convert to 0-based
            if pos_idx < 0:
                pos_idx = 0
            elif pos_idx > len(plan["steps"]):
                pos_idx = len(plan["steps"])
            plan["steps"].insert(pos_idx, new_step)
            step_number = position
        else:
            plan["steps"].append(new_step)
            step_number = len(plan["steps"])
        
        plan["updated_at"] = timestamp
        
        # Format the updated plan for display
        formatted_plan = f"Updated Plan: {plan['title']}\n\n"
        for i, step in enumerate(plan["steps"]):
            status = "[x]" if step["completed"] else "[ ]"
            formatted_plan += f"{status} {i+1}. {step['description']}\n"

        tool_message_print("add_plan_step", [
            ("plan_id", plan_id),
            ("position", position if position else "end"),
            ("description", description)
        ])

        tool_report_print(f"Step added to Plan #{plan_id}:", formatted_plan)

        return f"New step added to Plan #{plan_id} at position {step_number}."
    except Exception as e:
        error_msg = f"Error adding step to plan: {str(e)}"
        tool_report_print("Error:", error_msg)
        return error_msg

def get_plans(session_wide: bool = False, title: str = None, format: str = "default") -> str:
    """
    Retrieve plans from either session-wide or message-specific storage.

    Args:
        session_wide: Whether to retrieve session-wide plans (True) or message-specific plans (False).
        title: Optional title filter.
        format: Output format ("default", "markdown", or "detailed").

    Returns:
        A formatted string containing all matching plans with their checklist items.
    """
    storage = _session_plans if session_wide else _message_plans

    if not storage:
        return "No plans available."

    if title:
        filtered_plans = [plan for plan in storage if plan["title"].lower() == title.lower()]
    else:
        filtered_plans = storage

    if not filtered_plans:
        return f"No plans found with title: {title}"

    # Format the plans according to the specified format
    if format == "markdown":
        result = "# Plans\n\n"
        for plan in filtered_plans:
            result += f"## Plan {plan['id']}: {plan['title']}\n\n"
            
            for i, step in enumerate(plan["steps"]):
                checkbox = "- [x]" if step["completed"] else "- [ ]"
                result += f"{checkbox} {step['description']}\n"
                if step["context"]:
                    result += f"  - *Context:* {step['context']}\n"
            
            result += "\n"

    elif format == "detailed":
        result = "DETAILED PLANS:\n\n"
        for plan in filtered_plans:
            result += f"PLAN {plan['id']} - {plan['title'].upper()}\n"
            result += f"Created: {plan['created_at'][:10]} | Updated: {plan['updated_at'][:10]}\n"
            result += "=" * 40 + "\n\n"

            for i, step in enumerate(plan["steps"]):
                status = "[COMPLETED]" if step["completed"] else "[PENDING]"
                result += f"STEP {i+1} {status}\n{step['description']}\n\n"
                
                if step["context"]:
                    result += f"CONTEXT:\n{step['context']}\n\n"
                    
                result += "-" * 20 + "\n"
            
            result += "\n"

    else:  # default format
        result = "Plans:\n\n"
        for plan in filtered_plans:
            result += f"Plan #{plan['id']} - {plan['title']}:\n"
            
            for i, step in enumerate(plan["steps"]):
                status = "[x]" if step["completed"] else "[ ]"
                result += f"{status} {i+1}. {step['description']}\n"
                if step["context"]:
                    result += f"   Context: {step['context']}\n"
            
            result += "\n"

    # Add reminder about ephemeral nature of plans
    result += "\n(Note: These plans are temporary and will be reset with the next user message.)\n"

    tool_message_print("get_plans", [
        ("title", title if title else "All"),
        ("format", format),
        ("count", len(filtered_plans))
    ])

    tool_report_print("Retrieved plans:", result)

    return result

def clear_plans(session_wide: bool = False) -> str:
    """
    Clear all plans from either session-wide or message-specific storage.

    Args:
        session_wide: Whether to clear session-wide plans (True) or message-specific plans (False).

    Returns:
        Confirmation message.
    """
    global _session_plans, _message_plans

    storage = _session_plans if session_wide else _message_plans
    count = len(storage)
    storage.clear()

    return f"Successfully cleared all {count} {'session-wide' if session_wide else 'message-specific'} plans."

# Function to force a reset (for use by the framework)
def reset_plans():
    """Reset all message-specific plans - called automatically at the start of processing each new user message"""
    global _message_plans
    _message_plans = []
    return True