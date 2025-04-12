"""
Chat-related routes for the application
"""

from flask import Blueprint, jsonify, request, session, Response, current_app, g
import json
import traceback
import litellm # Add litellm import
import os
from assistant import Assistant
import config as conf
from tools import formatting, TOOLS
from assistant.tool_handler import process_tool_calls
from app.utils.helpers import chunk_text
from utils.provider_manager import ProviderManager
import time

chat_bp = Blueprint('chat', __name__)

@chat_bp.route('/stream', methods=['POST'])
def chat_stream():
    """Streaming endpoint for chat messages."""
    if not current_app.assistant:
        return jsonify({"error": "Assistant not initialized"}), 500

    try:
        # Initialize provider manager
        ProviderManager.initialize()
        
        user_message = request.json.get('message')
        image_data = request.json.get('imageData')
        is_retry = request.json.get('is_retry', False)
        
        if not user_message and not image_data:
            return jsonify({"error": "No message or image provided"}), 400

        # Get session ID (or client IP if no session available)
        session_id = session.get('user_id', request.remote_addr)
        
        # Determine whether to use integrated GPT-4o mode
        use_integrated_model = conf.MODEL == "gpt4o-integrated"
        
        # Get appropriate provider and model based on our fallback strategy
        if use_integrated_model:
            provider, model_name = ProviderManager.get_provider_and_model('gpt4o')
            print(f"Using provider {provider} with model {model_name}")
        else:
            # Use configured provider and model
            provider = getattr(conf, 'API_PROVIDER', 'pollinations')
            model_name = conf.MODEL
        
        # Create or get user-specific assistant instance
        if session_id not in current_app.assistants:
            current_app.assistants[session_id] = Assistant(
                model=model_name,
                system_instruction=conf.get_system_prompt().strip(),
                tools=TOOLS
            )
            if use_integrated_model:
                current_app.assistants[session_id].update_provider(provider)
        else:
            # Update existing assistant with current model and provider
            current_app.assistants[session_id].model = model_name
            if use_integrated_model:
                current_app.assistants[session_id].update_provider(provider)
        
        user_assistant = current_app.assistants[session_id]
        
        # Prepare image data if provided
        images = None
        if image_data:
            images = [{
                "type": "image_url",
                "image_url": {
                    "url": image_data
                }
            }]

        def generate():
            # Send start event
            yield f"data: {json.dumps({'event': 'start'})}\n\n"
            
            # If this is a retry, remove the last user message and all subsequent assistant/tool messages
            if is_retry and len(user_assistant.messages) > 0:
                print("Retry detected: Removing last user turn and subsequent messages from history.")
                last_user_message_index = -1
                for i in range(len(user_assistant.messages) - 1, -1, -1):
                    if user_assistant.messages[i].get("role") == "user":
                        last_user_message_index = i
                        break
                
                if last_user_message_index != -1:
                    print(f"Removing messages from index {last_user_message_index} onwards.")
                    del user_assistant.messages[last_user_message_index:]
            
            # Add user message to assistant's conversation history
            if user_message or images:
                user_assistant.messages.append({
                    "role": "user",
                    "content": user_message if not images else [
                        {"type": "text", "text": user_message},
                        *images
                    ]
                })
            
            # Initialize tracking variables for empty response detection
            content_received = False
            empty_retries = 0
            max_empty_retries = 3
            retry_delay = 2  # seconds between retries
            max_no_content_time = 30  # seconds to wait for first content
            start_time = time.time()
            
            # Create tool tracking list for this conversation
            user_assistant.current_tool_calls = []
            seen_tool_calls = set()
            
            from tools.formatting import tool_report_print as original_print
            
            def patched_tool_report(msg, value, is_error=False):
                # Handle tool execution start
                if msg.startswith("Running tool:"):
                    tool_info = value.strip()
                    if '(' in tool_info and ')' in tool_info:
                        tool_name = tool_info.split('(')[0].strip()
                        args_part = tool_info[tool_info.find('(')+1:tool_info.rfind(')')]
                        
                        # Create a signature to detect duplicates
                        tool_signature = f"{tool_name}:{args_part}"
                        
                        # Skip if we've already seen this exact tool call
                        if tool_signature in seen_tool_calls:
                            print(f"Skipping duplicate tool call: {tool_signature}")
                            return None
                            
                        seen_tool_calls.add(tool_signature)
                        
                        # Create unique tool ID
                        tool_id = f"tool_{len(user_assistant.current_tool_calls) + 1}"
                        
                        tool_data = {
                            "id": tool_id,
                            "name": tool_name,
                            "args": args_part,
                            "status": "pending",
                            "result": None
                        }
                        
                        # Store tool call data
                        user_assistant.current_tool_calls.append(tool_data)
                        
                        # Stream tool call event immediately
                        event_data = f"data: {json.dumps({'event': 'tool_call', 'data': tool_data})}\n\n"
                        yield event_data
                        return event_data
                
                # Process tool execution completion
                elif msg == "Result:":
                    if user_assistant.current_tool_calls:
                        # Get the most recent tool call
                        tool_call = user_assistant.current_tool_calls[-1]
                        tool_id = tool_call["id"]
                        tool_name = tool_call["name"]
                        
                        # Track if this result is empty
                        result_str = str(value)
                        is_empty_result = not result_str or result_str.strip() == '""'
                        
                        # Special handling for plan tools to show the actual plan content
                        if tool_name in ["create_plan", "update_plan", "add_plan_step", "get_plans"]:
                            # If we're calling a plan tool, extract the formatted plan content from the result
                            lines = result_str.strip().split('\n')
                            plan_content = ""
                            
                            # Find where the plan content begins (after the confirmation message)
                            for i, line in enumerate(lines):
                                if line.startswith("Plan #") or line.startswith("Step ") or line.startswith("New step ") or line.startswith("Plans:"):
                                    # Include the original success message
                                    plan_content = lines[i]
                                    
                                    # If this is a result from get_plans, we have a formatted plan to include
                                    if i+1 < len(lines) and tool_name == "get_plans":
                                        # Include the full formatted plan content
                                        plan_content = "\n".join(lines[i:])
                                        break
                                    # For create_plan/update_plan, we need to access the actual plan data
                                    # This depends on how the plan content is returned from the plan tool functions
                                    elif tool_name == "create_plan" or tool_name == "update_plan" or tool_name == "add_plan_step":
                                        # Extract the plan ID from the result message
                                        import re
                                        plan_id_match = re.search(r"Plan #(\d+)", lines[i])
                                        if plan_id_match:
                                            plan_id = int(plan_id_match.group(1))
                                            # Get the actual plan content
                                            from tools.plan import _message_plans, _session_plans
                                            plan_idx = plan_id - 1
                                            if 0 <= plan_idx < len(_message_plans):
                                                plan = _message_plans[plan_idx]
                                                plan_content += f"\n\nPlan: {plan['title']}\n"
                                                for j, step in enumerate(plan['steps']):
                                                    status = "[x]" if step["completed"] else "[ ]"
                                                    plan_content += f"{status} {j+1}. {step['description']}\n"
                                                    if step["context"]:
                                                        plan_content += f"   Context: {step['context'][:100]}...\n" if len(step["context"]) > 100 else f"   Context: {step['context']}\n"
                                    break
                            
                            # Update the tool call result with the formatted plan
                            tool_call["result"] = plan_content if plan_content else result_str
                        else:
                            # Standard handling for non-plan tools
                            if is_empty_result:
                                tool_call["result"] = "No meaningful content could be extracted from this website."
                            else:
                                tool_call["result"] = result_str
                            
                        tool_call["status"] = "completed" if "Error" not in str(value) else "error"
                        
                        # Stream tool update event immediately
                        event_data = f"data: {json.dumps({'event': 'tool_update', 'data': tool_call})}\n\n"
                        yield event_data
                        return event_data
                
                return None
            
            # Define tool event handler before it's used
            def tool_event_handler(event_type, data, is_temp=False):
                # Filter out processing and tool execution messages
                if event_type == "info" and (
                    data == "Getting next response after tool execution..." or
                    data == "Processing results and generating response..." or
                    data.startswith("Processing tool") or
                    "tool execution" in data.lower()
                ):
                    # Skip sending these to the UI, but still log them
                    print(f"Tool processing info: {data}")
                    return []  # Return empty generator to avoid yielding anything
                
                # Handle temporary info messages
                event_data = {
                    "event": event_type,
                    "data": data
                }
                if is_temp:
                    event_data["temp"] = True
                    
                # Construct the event data
                event = f"data: {json.dumps(event_data)}\n\n"
                yield event

            formatting.tool_report_print = patched_tool_report
            
            try:
                print(f"Processing message: '{user_message}' using provider: {user_assistant.provider}")

                # Import traceback here to ensure it's available in all nested scopes
                import traceback as tb

                if user_assistant.provider == 'litellm' and user_assistant.model.startswith('github/'):
                    if not os.environ.get('GITHUB_API_KEY') and hasattr(conf, 'GITHUB_API_KEY') and conf.GITHUB_API_KEY:
                        os.environ['GITHUB_API_KEY'] = conf.GITHUB_API_KEY
                        print("Set GitHub API key from config")

                try:
                    if user_assistant.provider == 'pollinations':
                        if not user_assistant.api_client:
                            raise ValueError("Pollinations provider selected but api_client is not initialized.")
                        response = user_assistant.api_client.get_completion(
                            messages=user_assistant.messages,
                            tools=user_assistant.tools
                        )
                    elif user_assistant.provider == 'litellm':
                        # Initialize response variable here to prevent UnboundLocalError
                        response = None
                        
                        while empty_retries < max_empty_retries:
                            if empty_retries > 0:
                                retry_msg = f"No response received, retrying... (attempt {empty_retries + 1}/{max_empty_retries})"
                                print(f"\033[33m{retry_msg}\033[0m")  # Yellow text
                                yield f"data: {json.dumps({'event': 'info', 'data': retry_msg, 'temp': True})}\n\n"
                                time.sleep(retry_delay)  # Wait before retry
                            
                            completion_args = {
                                "model": user_assistant.model,
                                "messages": user_assistant.messages,
                                "tools": user_assistant.tools,
                                "temperature": conf.TEMPERATURE + (0.1 * empty_retries),  # Slightly increase temperature on retries
                                "top_p": conf.TOP_P,
                                "max_tokens": conf.MAX_TOKENS,
                                "seed": conf.SEED,
                                "stream": True
                            }
                            
                            safety_settings = getattr(conf, 'SAFETY_SETTINGS', None)
                            if safety_settings:
                                completion_args["safety_settings"] = safety_settings
                            completion_args = {k: v for k, v in completion_args.items() if v is not None}
                            
                            response_stream = litellm.completion(**completion_args)
                            
                            accumulated_content = ""
                            accumulated_tool_calls = []
                            final_chunk = None
                            chunk_received = False
                            
                            for chunk in response_stream:
                                chunk_received = True
                                if time.time() - start_time > max_no_content_time and not content_received:
                                    raise Exception("Timeout waiting for initial content from API")
                                
                                chunk_content = chunk.choices[0].delta.content
                                chunk_tool_calls = chunk.choices[0].delta.tool_calls

                                if chunk_content:
                                    content_received = True
                                    accumulated_content += chunk_content
                                    yield f"data: {json.dumps({'event': 'token', 'data': chunk_content})}\n\n"

                                if chunk_tool_calls:
                                    content_received = True  # Tool calls also count as content
                                    for tool_call_delta in chunk_tool_calls:
                                        index = tool_call_delta.index
                                        if index >= len(accumulated_tool_calls):
                                            accumulated_tool_calls.append({
                                                "id": tool_call_delta.id or f"tool_{index}",
                                                "type": "function",
                                                "function": {
                                                    "name": tool_call_delta.function.name or "",
                                                    "arguments": tool_call_delta.function.arguments or ""
                                                }
                                            })
                                        else:
                                            if tool_call_delta.function.name:
                                                accumulated_tool_calls[index]["function"]["name"] += tool_call_delta.function.name
                                            if tool_call_delta.function.arguments:
                                                accumulated_tool_calls[index]["function"]["arguments"] += tool_call_delta.function.arguments

                                final_chunk = chunk

                            if content_received:
                                break
                            elif not chunk_received:
                                print("\033[31mNo response chunks received from API\033[0m")  # Red text
                                empty_retries += 1
                                if empty_retries >= max_empty_retries:
                                    raise Exception("Failed to get any response after multiple retries")
                                continue
                            else:
                                print(f"\033[33mGot chunks but no content\033[0m")  # Yellow text
                                empty_retries += 1
                                if empty_retries >= max_empty_retries:
                                    raise Exception("Received empty responses after multiple retries")
                                continue

                        response = {
                            "choices": [{
                                "message": {
                                    "role": "assistant",
                                    "content": accumulated_content,
                                    **({"tool_calls": accumulated_tool_calls} if accumulated_tool_calls else {})
                                },
                                "finish_reason": final_chunk.choices[0].finish_reason if final_chunk else "stop"
                            }],
                            "model": user_assistant.model
                        }

                        if accumulated_content:
                            yield f"data: {json.dumps({'event': 'final', 'data': accumulated_content})}\n\n"
                    else:
                        raise ValueError(f"Unsupported provider: {user_assistant.provider}")

                except Exception as e:
                    error_msg = str(e)
                    print(f"Error during streaming: {error_msg}")
                    tb.print_exc()  # Use the locally imported traceback
                    response = {
                        "choices": [{
                            "message": {
                                "role": "assistant",
                                "content": f"I apologize, but I encountered an error while processing your request: {error_msg}"
                            },
                            "finish_reason": "error"
                        }],
                        "model": user_assistant.model
                    }
                    yield f"data: {json.dumps({'event': 'error', 'data': error_msg})}\n\n"

                if response:  # Only process if response is properly set
                    tool_events_generator = process_tool_calls(
                        user_assistant,
                        response,
                        print_response=False,
                        validation_retries=2,
                        recursion_depth=0,
                        tool_event_callback=tool_event_handler
                    )
                    
                    final_text = None
                    for event_data in tool_events_generator:
                        if isinstance(event_data, dict) and "final_text" in event_data:
                            final_text = event_data["final_text"]
                        else:
                            yield event_data
                    
                    formatting.tool_report_print = original_print
                    
                    if final_text and user_assistant.provider != 'litellm' and not user_assistant._streamed_final_response:
                        user_assistant._final_response = final_text
                        if not any(msg.get("role") == "assistant" and msg.get("content") == final_text for msg in user_assistant.messages[-3:]):
                            user_assistant.messages.append({
                                "role": "assistant",
                                "content": final_text
                            })
                        
                        for token in chunk_text(final_text, 3):
                            yield f"data: {json.dumps({'event': 'token', 'data': token})}\n\n"
                        
                        yield f"data: {json.dumps({'event': 'final', 'data': final_text})}\n\n"
                else:
                    yield f"data: {json.dumps({'event': 'error', 'data': 'Failed to get a valid response from the model.'})}\n\n"
            
            except Exception as e:
                import traceback as tb
                print(f"Error during streaming: {e}")
                tb.print_exc()  # Use the locally imported traceback
                yield f"data: {json.dumps({'event': 'error', 'data': str(e)})}\n\n"
                formatting.tool_report_print = original_print
            
            yield f"data: {json.dumps({'event': 'done'})}\n\n"

        return Response(generate(), mimetype='text/event-stream')
        
    except Exception as e:
        print(f"Error during chat processing: {e}")
        return jsonify({"error": "An internal error occurred"}), 500

@chat_bp.route('', methods=['POST'])
def chat():
    """Legacy non-streaming API endpoint that now uses streaming internally for consistency."""
    if not current_app.assistant:
        return jsonify({"error": "Assistant not initialized"}), 500

    try:
        user_message = request.json.get('message')
        image_data = request.json.get('imageData')
        
        if not user_message and not image_data:
            return jsonify({"error": "No message or image provided"}), 400

        # Get session ID (or client IP if no session available)
        session_id = session.get('user_id', request.remote_addr)
        
        # Create or get user-specific assistant instance
        if session_id not in current_app.assistants:
            current_app.assistants[session_id] = Assistant(
                model=conf.MODEL,
                system_instruction=conf.get_system_prompt().strip(),
                tools=TOOLS  # Use the imported TOOLS directly
            )
        
        user_assistant = current_app.assistants[session_id]
        
        # Send message using the streaming method internally
        assistant_response = user_assistant.send_message(user_message, image_data)
        
        # Format response for the client - the send_message method now returns a structured response
        return jsonify({
            "response": assistant_response["text"],
            "tool_calls": assistant_response.get("tool_calls", [])
        })
    except Exception as e:
        print(f"Error during chat processing: {e}")
        traceback.print_exc()
        return jsonify({"error": "An internal error occurred"}), 500

@chat_bp.route('/reset', methods=['POST'])
def reset_chat():
    """Reset the chat session"""
    try:
        session_id = session.get('user_id', request.remote_addr)
        
        # Check if the assistant exists for this session
        if session_id not in current_app.assistants:
            print(f"Creating new assistant for session {session_id}")
            # Create a new assistant for this session with the system prompt
            assistant = Assistant(
                model=conf.MODEL,
                name=conf.NAME,
                tools=tools.TOOLS,
                system_instruction=conf.get_system_prompt()
            )
            current_app.assistants[session_id] = assistant
        else:
            print(f"Resetting existing assistant for session {session_id}")
            # Reset the existing assistant
            current_app.assistants[session_id].reset_session()
            
        print("Chat session reset successfully")
        return jsonify({"status": "success", "message": "Chat session reset successfully"})
    except Exception as e:
        print(f"Error resetting chat session: {e}")
        traceback.print_exc()
        return jsonify({"status": "error", "message": str(e)}), 500
