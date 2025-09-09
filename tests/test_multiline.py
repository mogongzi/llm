#!/usr/bin/env python3
"""Test script for multiline input functionality."""

import sys
import os
import pytest
from rich.console import Console

# Add parent directory to path to import our modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from util.simple_pt_input import get_multiline_input


class MockMultilineInputResult:
    """Mock the return values from get_multiline_input for testing."""
    
    @staticmethod
    def normal_input():
        return "Hello world", False, False, False
    
    @staticmethod
    def thinking_command():
        return None, False, True, False  # Thinking mode toggled
    
    @staticmethod
    def tools_command():
        return None, False, False, True  # Tools mode toggled
    
    @staticmethod
    def exit_signal():
        return "__EXIT__", False, False, False
    
    @staticmethod
    def empty_input():
        return None, False, False, False


def test_multiline_input_processing():
    """Test that multiline input processing logic works correctly."""
    console = Console()
    
    # Test normal input
    result, use_thinking, thinking_mode, tools_enabled = MockMultilineInputResult.normal_input()
    assert result == "Hello world"
    assert use_thinking is False
    assert thinking_mode is False
    assert tools_enabled is False
    
    # Test thinking command
    result, use_thinking, thinking_mode, tools_enabled = MockMultilineInputResult.thinking_command()
    assert result is None
    assert thinking_mode is True
    
    # Test tools command
    result, use_thinking, thinking_mode, tools_enabled = MockMultilineInputResult.tools_command()
    assert result is None
    assert tools_enabled is True
    
    # Test exit signal
    result, use_thinking, thinking_mode, tools_enabled = MockMultilineInputResult.exit_signal()
    assert result == "__EXIT__"
    
    # Test empty input
    result, use_thinking, thinking_mode, tools_enabled = MockMultilineInputResult.empty_input()
    assert result is None


def test_input_command_parsing():
    """Test command parsing logic."""
    # Mock the command processing from simple_pt_input.py
    def process_command(cleaned_input, thinking_mode=False, tools_enabled=False):
        if cleaned_input == '/think':
            return None, False, not thinking_mode, tools_enabled
        elif cleaned_input == '/tools':
            return None, False, thinking_mode, not tools_enabled
        elif cleaned_input == '/clear':
            return "__CLEAR__", False, thinking_mode, tools_enabled
        elif cleaned_input.startswith('/think '):
            actual_message = cleaned_input[7:].strip()
            return actual_message, True, thinking_mode, tools_enabled
        else:
            return cleaned_input, thinking_mode, thinking_mode, tools_enabled
    
    # Test /think command
    result, use_thinking, new_thinking_mode, tools_enabled = process_command('/think', False, False)
    assert result is None
    assert new_thinking_mode is True
    
    # Test /tools command  
    result, use_thinking, thinking_mode, new_tools_enabled = process_command('/tools', False, False)
    assert result is None
    assert new_tools_enabled is True
    
    # Test /clear command
    result, use_thinking, thinking_mode, tools_enabled = process_command('/clear', False, False)
    assert result == "__CLEAR__"
    
    # Test /think with message
    result, use_thinking, thinking_mode, tools_enabled = process_command('/think What is 2+2?', False, False)
    assert result == "What is 2+2?"
    assert use_thinking is True


if __name__ == "__main__":
    pytest.main([__file__])