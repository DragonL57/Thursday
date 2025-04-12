"""
This package provides functionality to convert Python functions into JSON schemas,
primarily for use with Large Language Models (LLMs) that support function calling.

It leverages type hints, docstrings, and function signatures to automatically
generate a JSON schema representing the function's parameters, descriptions, and
other relevant information. This allows LLMs to understand the function's
purpose and how to call it correctly.
"""

import inspect
from types import UnionType
from typing import Any, Dict, get_type_hints, get_origin, get_args, Literal, Callable, Optional, Union, List
import docstring_parser
from pydantic import BaseModel
import warnings
import re

def function_to_json_schema(func: Callable) -> Dict[str, Any]:
    """
    Converts a Python function to a JSON schema for LLM function calling.

    Args:
        func: The Python function to convert.

    Returns:
        A dictionary representing the JSON schema.
    """
    signature = inspect.signature(func)
    docstring = docstring_parser.parse(func.__doc__ or "") 
    parameters = {}
    required_params = []

    type_hints = get_type_hints(func)

    for param_name, param in signature.parameters.items():
        param_info = {}
        if param_name in type_hints:
            param_info.update(type_hint_to_json_schema(type_hints[param_name]))

        docstring_param = next((p for p in docstring.params if p.arg_name == param_name), None)
        if docstring_param and docstring_param.description:
            param_info["description"] = docstring_param.description

        if param.default == inspect.Parameter.empty:
            required_params.append(param_name)

        # Ensure param_info has a type field for Gemini compatibility
        if "type" not in param_info:
            param_info["type"] = "string"  # Default to string type for Gemini compatibility

        parameters[param_name] = param_info

    doc_str_desc = docstring.description
    if doc_str_desc:
        doc_str_desc = re.sub(r'\s+', ' ', doc_str_desc).strip()

    json_schema = {
        "type": "function",
        "function": {
            "name": func.__name__,
            "description": doc_str_desc or "",
        }
    }

    if parameters:
        json_schema["function"]["parameters"] = {}
        json_schema["function"]["parameters"]["type"] = "object"
        json_schema["function"]["parameters"]["properties"] = parameters
        json_schema["function"]["parameters"]["required"] = required_params if required_params else None
    
    if docstring.returns and docstring.returns.description:
        json_schema["function"]["returns"] = {
            "description": docstring.returns.description
        }
    
    return json_schema


def type_hint_to_json_schema(type_hint) -> Dict[str, Any]:
    """
    Converts a Python type hint to a JSON schema type.  Handles:
        - Basic types (str, int, float, bool)
        - typing.Optional[T]  ->  T with nullable=True
        - typing.Union[T1, T2] ->  Use most specific common type
        - typing.List[T]      ->  array of T
        - Pydantic BaseModel   ->  Use schema() method
        - typing.Dict        -> object
        - typing.Any         -> {}

    Args:
        type_hint: The Python type hint.

    Returns:
        A dictionary representing the JSON schema type.  Returns an empty
        dictionary if the type is not supported.
    """
    # Check for Any first
    if type_hint is Any:
        return {"type": "string"}  # Default to string for Any type
    
    # Basic types
    if type_hint == str:
        return {"type": "string"}
    elif type_hint == int:
        return {"type": "integer"}
    elif type_hint == float:
        return {"type": "number"}  
    elif type_hint == bool:
        return {"type": "boolean"}
    elif type_hint == type(None): 
        return {"type": "null"}
    
    # Get origin of complex types
    origin = get_origin(type_hint)
    
    # Handle Literal
    if origin is Literal:
        args = get_args(type_hint)
        if args:
            # Determine the type from the first literal value
            first_arg_type = type_hint_to_json_schema(type(args[0]))["type"]
            return {"type": first_arg_type, "enum": list(args)}
        return {"type": "string"}  # Default if no args
    
    # Handle List and list-like types
    elif origin is list or origin is List:
        args = get_args(type_hint)
        if args:
            items_schema = type_hint_to_json_schema(args[0])
            return {"type": "array", "items": items_schema}
        else:
            return {"type": "array", "items": {"type": "string"}}  # Default item type
    
    # Handle Dict and dict-like types
    elif origin is dict:
        # For Gemini compatibility, specify a simple object schema
        return {"type": "object", "additionalProperties": {"type": "string"}}
    
    # Handle Union types (including Optional)
    elif origin is Union or origin is UnionType:
        args = get_args(type_hint)
        
        # Check for Optional (Union with None)
        if type(None) in args:
            # Find non-None types
            non_none_args = [arg for arg in args if arg is not type(None)]  # noqa: E721
            if len(non_none_args) == 1:
                # Optional[T] case
                return type_hint_to_json_schema(non_none_args[0])
            else:
                # Union with multiple types and None - use a common type
                # For Gemini compatibility, choose a common type rather than an array of types
                if all(arg in [str, int, float] for arg in non_none_args):
                    return {"type": "string"}  # String can represent all these
                elif all(arg in [int, float] for arg in non_none_args):
                    return {"type": "number"}  # Number can represent ints and floats
                else:
                    # Default to string which can represent most things
                    return {"type": "string"}
        else:
            # Regular Union - choose the most compatible single type for Gemini
            # Gemini doesn't handle multiple types well, so we choose one type
            if all(arg in [str, int, float] for arg in args):
                return {"type": "string"}
            elif all(arg in [int, float] for arg in args):
                return {"type": "number"}
            else:
                # Default to string for maximum compatibility
                return {"type": "string"}
    
    # Handle Optional directly
    elif origin is Optional:
        args = get_args(type_hint)
        if args:
            # For Gemini compatibility, don't include nullable
            return type_hint_to_json_schema(args[0])
        return {"type": "string"}  # Default to string
    
    # Handle Pydantic models
    elif isinstance(type_hint, type) and issubclass(type_hint, BaseModel):
        try:
            schema = type_hint.model_json_schema()
            # Clean up the schema for Gemini compatibility
            if 'title' in schema:
                del schema['title']
            
            # Convert schema properties to be Gemini-compatible
            if "properties" in schema:
                for prop_name, prop_schema in schema["properties"].items():
                    if "title" in prop_schema:
                        del prop_schema["title"]
                    # Remove default values that cause issues with Gemini
                    if "default" in prop_schema:
                        del prop_schema["default"]
                    
                    # Make sure each property has a type field for Gemini compatibility
                    if "type" not in prop_schema:
                        prop_schema["type"] = "string"  # Default to string

                    # If a property is an object, ensure its nested properties have types too
                    if prop_schema.get("type") == "object" and "properties" in prop_schema:
                        for nested_prop_name, nested_prop_schema in prop_schema["properties"].items():
                            if "type" not in nested_prop_schema:
                                nested_prop_schema["type"] = "string"  # Default to string
            
            # Make sure the schema has a type field - critical for Gemini
            if "type" not in schema:
                schema["type"] = "object"
            
            return schema
        except Exception as e:
            warnings.warn(f"Error processing Pydantic model schema: {str(e)}. Using simple object schema.", UserWarning)
            return {"type": "object", "additionalProperties": {"type": "string"}}
    
    # Fallback for unsupported types, with better handling
    try:
        # Try to get a string representation for logging
        type_str = str(type_hint)
        if hasattr(type_hint, "__name__"):
            type_str = type_hint.__name__
        elif hasattr(type_hint, "_name"):
            type_str = type_hint._name
        
        warnings.warn(f"Unsupported type hint: {type_str}. Using string type for compatibility.", UserWarning)
    except Exception:
        warnings.warn(f"Unsupported type hint (cannot display). Using string type for compatibility.", UserWarning)
    
    # Default to string type for maximum compatibility
    return {"type": "string"}

