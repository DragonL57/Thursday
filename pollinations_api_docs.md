# Pollinations.AI API - Comprehensive Guide

## Table of Contents
- [Introduction](#introduction)
- [API Overview](#api-overview)
- [Text Generation API](#text-generation-api)
  - [Simple GET Endpoints](#simple-get-endpoints)
  - [OpenAI-Compatible POST Endpoint](#openai-compatible-post-endpoint)
  - [Function/Tool Calling](#functiontool-calling)
  - [Available Text Models](#available-text-models)
- [Image Generation API](#image-generation-api)
  - [Text-to-Image GET Endpoint](#text-to-image-get-endpoint)
  - [Available Image Models](#available-image-models)
- [Audio Generation API](#audio-generation-api)
  - [Text-to-Speech (GET)](#text-to-speech-get)
  - [Text-to-Speech (POST)](#text-to-speech-post)
- [MCP Server for AI Assistants](#mcp-server-for-ai-assistants)
- [Real-time Feeds API](#real-time-feeds-api)
- [Working with Function Calling](#working-with-function-calling)
  - [Schema Definition](#schema-definition)
  - [Handling Function Calls](#handling-function-calls)
  - [Parameter Validation and Type Handling](#parameter-validation-and-type-handling)
  - [Error Handling](#error-handling)
- [Integration Best Practices](#integration-best-practices)
- [Security and Privacy](#security-and-privacy)
- [Rate Limits and Quotas](#rate-limits-and-quotas)
- [Troubleshooting Common Issues](#troubleshooting-common-issues)
- [Appendix: Code Examples](#appendix-code-examples)

## Introduction

Pollinations.AI is an accessible open GenAI platform providing APIs for text, image, and audio generation without requiring signup. The platform aims to make AI capabilities accessible through simple API endpoints while maintaining high-quality outputs.

Key features include:
- No signup required - direct integration via simple API calls
- Support for text generation, image generation, and audio synthesis
- OpenAI-compatible endpoints for easy migration from other services
- Function calling capabilities for tool use in AI assistants
- Streaming responses for real-time interaction
- Real-time feeds for community-generated content

## API Overview

Pollinations.AI offers three main API services:

1. **Text Generation API**: Create text content, answer questions, and process conversational inputs
2. **Image Generation API**: Generate images from text descriptions
3. **Audio Generation API**: Convert text to speech using various voices

All APIs are accessible through simple HTTP requests and don't require authentication tokens, making integration straightforward for developers of all levels.

## Text Generation API

### Simple GET Endpoints

The simplest way to generate text is through a GET request with your prompt encoded in the URL. This approach is best for quick, one-off queries that don't require complex context or conversation history.

```
GET https://text.pollinations.ai/{your_prompt}
```

Parameters can be added as query strings:
```
GET https://text.pollinations.ai/{your_prompt}?model=mistral&seed=123
```

### OpenAI-Compatible POST Endpoint

For more complex operations, including multi-turn conversations, function calling, and multimodal inputs, use the OpenAI-compatible endpoint:

```
POST https://text.pollinations.ai/openai
```

This endpoint follows the OpenAI Chat Completions API format, making it easy to migrate existing code.

### Function/Tool Calling

Function calling allows your AI assistant to use tools and external services. Pollinations.AI implements an OpenAI-compatible function calling interface, but with some important implementation details to be aware of.

Example tool definition:
```json
{
  "type": "function",
  "function": {
    "name": "get_weather",
    "description": "Get current weather data for a location",
    "parameters": {
      "type": "object",
      "properties": {
        "location": {
          "type": "string",
          "description": "City and country name"
        }
      },
      "required": ["location"],
      "additionalProperties": false
    }
  }
}
```

### Available Text Models

Pollinations.AI offers a variety of models, each with different capabilities and performance characteristics. You can retrieve the current list of available models using:

```
GET https://text.pollinations.ai/models
```

## Image Generation API

### Text-to-Image GET Endpoint

Generate images from text descriptions using a simple GET request:

```
GET https://image.pollinations.ai/prompt/{your_prompt}
```

Parameters like model, dimensions, and seed can be included as query parameters.

### Available Image Models

To retrieve the current list of available image generation models:

```
GET https://image.pollinations.ai/models
```

## Audio Generation API

### Text-to-Speech (GET)

For short TTS requests, use the GET endpoint:

```
GET https://text.pollinations.ai/{text}?model=openai-audio&voice=nova
```

### Text-to-Speech (POST)

For longer TTS requests, use the OpenAI-compatible POST endpoint:

```
POST https://text.pollinations.ai/openai
```

With a structure like:
```json
{
  "model": "openai-audio",
  "messages": [{"role": "user", "content": "Your text to convert to speech"}],
  "voice": "nova"
}
```

## MCP Server for AI Assistants

The Model Context Protocol server enables AI assistants (like Claude) to generate images and audio directly. This provides tool access within AI assistant conversations.

## Real-time Feeds API

Access real-time feeds of user-generated content:
- Image feed: `GET https://image.pollinations.ai/feed`
- Text feed: `GET https://text.pollinations.ai/feed`

Both endpoints return Server-Sent Events (SSE).

## Working with Function Calling

Function calling is a powerful feature that allows models to trigger your code or external services. Based on extensive testing, here are detailed guidelines for implementing robust function calling with Pollinations.AI.

### Schema Definition

The Pollinations.AI API expects function schemas in the OpenAI format. Here's a comprehensive breakdown of required elements:

1. **Proper Nesting Structure**: Tools must be defined with a nested structure:
   ```json
   {
     "type": "function",
     "function": {
       "name": "your_function_name",
       "description": "Description of what the function does",
       "parameters": { ... }
     }
   }
   ```

2. **Complete Parameter Definitions**: Each parameter should include:
   - Type information (`string`, `number`, `boolean`, etc.)
   - Description
   - Default values (when applicable)
   - Required status

3. **Parameter Schema Example**:
   ```json
   "parameters": {
     "type": "object",
     "properties": {
       "location": {
         "type": "string",
         "description": "City name and country"
       },
       "units": {
         "type": "string",
         "enum": ["celsius", "fahrenheit"],
         "description": "Temperature units"
       }
     },
     "required": ["location"],
     "additionalProperties": false
   }
   ```

4. **Strict Mode Considerations**: When using strict mode, ensure:
   - `additionalProperties` is set to `false`
   - All required fields are listed in the `required` array
   - Optional fields are properly typed (e.g., `["string", "null"]` for optional strings)

### Handling Function Calls

Based on our testing with the Pollinations.AI API, here's how to properly handle function calls:

1. **Response Structure**: The model's response contains tool calls in the `tool_calls` array of the first choice's message:
   ```json
   {
     "choices": [{
       "message": {
         "content": "",
         "tool_calls": [{
           "id": "call_abc123",
           "function": {
             "name": "get_weather",
             "arguments": "{\"location\":\"New York\"}"
           }
         }]
       }
     }]
   }
   ```

2. **Parsing Arguments**: Always use JSON parsing to extract arguments:
   ```python
   function_args = json.loads(tool_call["function"]["arguments"])
   ```

3. **Function Dispatch**: Create a clean routing system to map function names to implementations:
   ```python
   def dispatch_function_call(name, args):
       function_map = {
           "get_weather": get_weather,
           "search_web": search_web
       }
       if name in function_map:
           return function_map[name](**args)
       raise ValueError(f"Unknown function: {name}")
   ```

4. **Handling Multiple Tool Calls**: The model may call multiple functions in one response:
   ```python
   for tool_call in response_message.get("tool_calls", []):
       function_name = tool_call["function"]["name"]
       function_args = json.loads(tool_call["function"]["arguments"])
       result = dispatch_function_call(function_name, function_args)
       # Add result to conversation
   ```

5. **Return Format for Tool Results**: After executing functions, format the results as strings and attach them to the conversation using the proper structure:
   ```python
   {
     "tool_call_id": tool_call_id,
     "role": "tool",
     "name": function_name,
     "content": str(result)
   }
   ```

### Parameter Validation and Type Handling

Robust parameter validation is crucial for reliable function calling:

1. **Parameter Name Consistency**: Ensure parameter names match exactly between the schema and function implementation. Common issues we found in testing:
   - Parameter name mismatches (e.g., `max_results` vs `num_results`)
   - Case sensitivity issues
   - Different parameter ordering

2. **Parameter Mapping Implementation**: When adapting between APIs with different parameter names:
   ```python
   # Map common parameter name variations
   if "num_results" in args and "max_results" not in args:
       args["max_results"] = args.pop("num_results")
   elif "max_results" in args and "num_results" not in args:
       args["num_results"] = args["max_results"]
   ```

3. **Default Parameter Handling**: Fill in defaults for missing parameters:
   ```python
   # For required params without defaults, use sensible defaults
   if param_name not in function_args and param.default is param.empty:
       if function_name == "search_tool":
           if param_name == "max_results":
               function_args[param_name] = 5
   ```

4. **Type Conversion**: Convert parameters to expected types:
   ```python
   # Convert string numbers to integers when needed
   if isinstance(args["max_results"], str):
       args["max_results"] = int(args["max_results"])
   ```

5. **Parameter Validation Function**:
   ```python
   def validate_tool_call(func, args):
       """
       Validate function arguments and return (is_valid, validated_args, error_msg).
       """
       sig = inspect.signature(func)
       validated_args = {}
       errors = []
       
       # Check required parameters
       for param_name, param in sig.parameters.items():
           if param_name == 'self':  # Skip self for methods
               continue
           
           if param_name not in args and param.default is param.empty:
               errors.append(f"Missing required parameter: {param_name}")
           elif param_name in args:
               # Add parameter validation logic here
               validated_args[param_name] = args[param_name]
       
       is_valid = not errors
       error_msg = "; ".join(errors) if errors else None
       
       return is_valid, validated_args, error_msg
   ```

### Error Handling

Based on our testing with Pollinations.AI, robust error handling is essential:

1. **Function Execution Errors**: Catch and handle errors during function execution:
   ```python
   try:
       result = func(**validated_args)
   except Exception as e:
       print(f"Error executing function {function_name}: {str(e)}")
       return f"Error: {str(e)}"
   ```

2. **Parameter Validation Errors**: Handle validation failures gracefully:
   ```python
   validation_result = validate_tool_call(func, function_args)
   if isinstance(validation_result, tuple):
       if len(validation_result) == 3:
           is_valid, validated_args, error_msg = validation_result
       else:
           is_valid, validated_args = validation_result
           error_msg = "Invalid arguments"
   
   if not is_valid:
       print(f"Invalid tool call: {error_msg}")
       return f"Error: {error_msg}"
   ```

3. **Fallbacks for Validation Issues**: Implement fallback mechanisms:
   ```python
   try:
       # Try validation first
       is_valid, validated_args, error_msg = validate_tool_call(func, args)
       if not is_valid:
           # Try to fix common issues
           args = fix_common_parameter_issues(func, args)
           is_valid, validated_args, _ = validate_tool_call(func, args)
           if not is_valid:
               # Last resort: try with original args
               result = func(**args)
   except Exception:
       # Ultimate fallback: try with minimal required args
       try:
           result = func(args.get("query", ""))
       except Exception as e:
           return f"Error: {str(e)}"
   ```

4. **Response Handling**: Handle unexpected response formats:
   ```python
   try:
       if "choices" not in response:
           print("Invalid response format")
           return "Error: Invalid response from API"
           
       choices = response["choices"]
       if not choices:
           print("Empty choices list")
           return "Error: No response choices"
           
       message = choices[0].get("message", {})
       # Continue processing
   except Exception as e:
       print(f"Error parsing response: {str(e)}")
       return "Error: Failed to process response"
   ```

## Integration Best Practices

From our practical implementation, here are key integration best practices:

1. **Function Schema Generation**:
   - Use code to generate schemas rather than writing them manually
   - Ensure descriptions are clear and detailed
   - Include examples where helpful

2. **Parameter Consistency**:
   - Use consistent parameter names across your API
   - Document parameter naming patterns
   - Implement parameter mapping for known variations

3. **Defensive Programming**:
   - Assume the model might send unexpected arguments
   - Validate all inputs
   - Handle missing parameters gracefully
   - Catch and handle all exceptions

4. **Debugging Aids**:
   - Add verbose logging during development
   - Print complete arguments for failed function calls
   - Log raw API responses when errors occur

5. **Optimizing for Reliability**:
   - Test edge cases extensively
   - Implement retries for transient failures
   - Use parameter mapping to handle common variations

## Security and Privacy

When implementing function calling:

1. **Input Validation**: Thoroughly validate all function inputs to prevent injection attacks
2. **Parameter Sanitization**: Clean parameters before use, especially when used in file paths, commands, or database queries
3. **Access Control**: Restrict sensitive functions with proper authentication checks
4. **Output Filtering**: Avoid returning sensitive information in function results

## Rate Limits and Quotas

Pollinations.AI imposes rate limits to ensure fair usage:

1. **Text API**: 1 concurrent request / 3 second interval
2. **Image API**: 1 concurrent request / 5 second interval

Implement exponential backoff for retries when rate limits are hit.

## Troubleshooting Common Issues

Based on our testing, here are solutions to common issues:

1. **Parameter Naming Conflicts**:
   - **Issue**: Function expects `max_results` but model sends `num_results`
   - **Solution**: Implement parameter mapping in your code
   ```python
   if "num_results" in args and "max_results" not in args:
       args["max_results"] = args.pop("num_results")
   ```

2. **Schema Format Errors**:
   - **Issue**: Incorrect schema structure causing function calling to fail
   - **Solution**: Follow OpenAI's exact schema format with the `"type": "function"` nested structure

3. **Parameter Type Mismatches**:
   - **Issue**: Function expects integer but receives string
   - **Solution**: Add type conversion in your parameter handling

4. **Rate Limit Errors**:
   - **Issue**: Receiving HTTP 429 errors
   - **Solution**: Implement exponential backoff with jitter

5. **Function Definition Complexity**:
   - **Issue**: Complex function definitions causing validation issues
   - **Solution**: Simplify function interfaces, handle complexity in the implementation

## Appendix: Code Examples

### Complete Function Calling Implementation

```python
def process_response(response, print_response=True):
    try:
        # Extract message from response
        response_message = response["choices"][0]["message"]
        content = response_message.get("content", "")
        tool_calls = response_message.get("tool_calls", [])
        
        if tool_calls:
            # Process tool calls
            input_messages.append(response_message)
            
            for tool_call in tool_calls:
                # Extract function details
                function_name = tool_call["function"].get("name", "unknown")
                function_args_str = tool_call["function"].get("arguments", "{}")
                function_id = tool_call.get("id", "unknown_id")
                
                # Parse arguments
                try:
                    function_args = json.loads(function_args_str)
                except json.JSONDecodeError:
                    function_args = {}
                
                # Check function availability
                if function_name in available_functions:
                    func = available_functions[function_name]
                    
                    # Handle parameter variations
                    if function_name == "search_web":
                        if "num_results" in function_args and "max_results" not in function_args:
                            function_args["max_results"] = function_args.pop("num_results")
                    
                    # Validate and execute
                    try:
                        is_valid, validated_args, error_msg = validate_tool_call(func, function_args)
                        
                        if not is_valid:
                            tool_result = f"Error: {error_msg}"
                        else:
                            tool_result = func(**validated_args)
                            
                        # Add result to conversation
                        input_messages.append({
                            "tool_call_id": function_id,
                            "role": "tool",
                            "name": function_name,
                            "content": str(tool_result)
                        })
                    except Exception as e:
                        tool_result = f"Error: {str(e)}"
                        input_messages.append({
                            "tool_call_id": function_id,
                            "role": "tool",
                            "name": function_name,
                            "content": str(tool_result)
                        })
                else:
                    tool_result = f"Error: Function {function_name} not available"
                    input_messages.append({
                        "tool_call_id": function_id,
                        "role": "tool",
                        "name": function_name,
                        "content": str(tool_result)
                    })
            
            # Get final response with tool results
            follow_up_response = query_llm(input_messages, functions)
            return process_response(follow_up_response, print_response)
        else:
            # Handle text-only response
            if content:
                input_messages.append({"role": "assistant", "content": content})
                if print_response:
                    print_ai(content)
            return response_message
    except Exception as e:
        print(f"Error processing response: {str(e)}")
        if print_response:
            print_ai("I encountered an error while processing the response. Please try again.")
        return {"content": "Error processing response"}
```

This comprehensive guide should help you effectively integrate with the Pollinations.AI API, especially when implementing function calling functionality.