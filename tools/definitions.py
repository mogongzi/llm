"""
Tool definitions for Claude function calling.

This module contains the schema definitions for all available tools
that Claude can call during conversations.
"""
from __future__ import annotations

from typing import Dict, List, Any

# Tool definitions following Anthropic's tool calling format
AVAILABLE_TOOLS: List[Dict[str, Any]] = [
    {
        "name": "get_current_time",
        "description": "Get the current date and time, optionally for a specific timezone",
        "input_schema": {
            "type": "object",
            "properties": {
                "timezone": {
                    "type": "string",
                    "description": "Timezone name (e.g., 'UTC', 'US/Eastern', 'Europe/Paris', 'Asia/Tokyo') - defaults to UTC if not specified"
                },
                "format": {
                    "type": "string",
                    "enum": ["iso", "human", "unix"],
                    "description": "Output format preference - defaults to human if not specified"
                }
            },
            "required": []
        }
    }
]


def get_tool_by_name(name: str) -> Dict[str, Any] | None:
    """
    Get a tool definition by name.

    Args:
        name: The tool name to look up

    Returns:
        Tool definition dictionary or None if not found
    """
    for tool in AVAILABLE_TOOLS:
        if tool["name"] == name:
            return tool
    return None


def get_tool_names() -> List[str]:
    """
    Get a list of all available tool names.

    Returns:
        List of tool names
    """
    return [tool["name"] for tool in AVAILABLE_TOOLS]
