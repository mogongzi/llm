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
        "name": "rails_callbacks",
        "description": "List Rails model lifecycle callbacks, touches, and dependent cascades for a save/create/update. If RAILS_ROOT env is set, omit rails_root.",
        "input_schema": {
            "type": "object",
            "properties": {
                "model": {
                    "type": "string",
                    "description": "ActiveRecord model class name (e.g., 'Post', 'Document')"
                },
                "rails_root": {
                    "type": "string",
                    "description": "Absolute path to the Rails application root containing bin/rails (optional if RAILS_ROOT env is set)"
                },
                "timeout": {
                    "type": "number",
                    "description": "Runner timeout in seconds (default 20)"
                },
                "force_runtime": {
                    "type": "boolean",
                    "description": "If true, skip static scan and use bin/rails runner (slow)."
                }
            },
            "required": ["model"]
        }
    },
    {
        "name": "code_search",
        "description": "Search code under a root directory using ripgrep-like semantics.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "root": {"type": "string", "description": "Search root (defaults to RAILS_ROOT env)"},
                "max_results": {"type": "number"},
                "context_lines": {"type": "number"}
            },
            "required": ["query"]
        }
    },
    {
        "name": "code_read",
        "description": "Read a file with optional line range.",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string"},
                "start": {"type": "number"},
                "end": {"type": "number"}
            },
            "required": ["path"]
        }
    },
    {
        "name": "rails_flow_after_persist",
        "description": "Heuristically summarize methods invoked after saving/creating a model (static scan only).",
        "input_schema": {
            "type": "object",
            "properties": {
                "model": {"type": "string"},
                "verb": {"type": "string", "enum": ["create", "save", "update", "destroy"], "description": "Persist verb (default create)"},
                "rails_root": {"type": "string", "description": "Rails app root (optional if RAILS_ROOT is set)"}
            },
            "required": ["model"]
        }
    },
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
