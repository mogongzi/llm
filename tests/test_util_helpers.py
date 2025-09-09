#!/usr/bin/env python3
"""
Test script for utility helper functionality.
"""

import sys
import os
from unittest.mock import Mock

try:
    import pytest
except ImportError:
    pytest = None

# Add parent directory to path to import our modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from util.url_helpers import to_mock_url
from util.command_helpers import show_help_message, handle_special_commands


class TestUrlHelpers:
    """Test URL manipulation utilities."""

    def test_to_mock_url_invoke_replacement(self):
        """Test replacing /invoke with /mock."""
        assert to_mock_url("http://host:8000/invoke") == "http://host:8000/mock"
        assert to_mock_url("https://api.example.com/v1/invoke") == "https://api.example.com/v1/mock"
    
    def test_to_mock_url_root_path(self):
        """Test appending /mock to root path."""
        assert to_mock_url("http://host:8000") == "http://host:8000/mock"
        assert to_mock_url("https://api.example.com/") == "https://api.example.com/mock"
    
    def test_to_mock_url_existing_path(self):
        """Test appending /mock to existing paths."""
        assert to_mock_url("http://host:8000/api") == "http://host:8000/api/mock"
        assert to_mock_url("https://example.com/v1/chat") == "https://example.com/v1/chat/mock"
    
    def test_to_mock_url_already_mock(self):
        """Test handling URLs that already end with /mock."""
        assert to_mock_url("http://host:8000/mock") == "http://host:8000/mock"
        assert to_mock_url("https://api.example.com/v1/mock") == "https://api.example.com/v1/mock"
    
    def test_to_mock_url_trailing_slash(self):
        """Test handling URLs with trailing slashes."""
        assert to_mock_url("http://host:8000/api/") == "http://host:8000/api/mock"
        assert to_mock_url("https://example.com/") == "https://example.com/mock"
    
    def test_to_mock_url_query_removal(self):
        """Test that query parameters are removed."""
        assert to_mock_url("http://host:8000/invoke?param=value") == "http://host:8000/mock"
        assert to_mock_url("https://api.example.com/v1?key=123&test=true") == "https://api.example.com/v1/mock"
    
    def test_to_mock_url_complex_paths(self):
        """Test with complex paths and edge cases."""
        assert to_mock_url("http://localhost:3000/api/v2/llm/invoke") == "http://localhost:3000/api/v2/llm/mock"
        assert to_mock_url("https://subdomain.example.com:9000/service") == "https://subdomain.example.com:9000/service/mock"
    
    def test_to_mock_url_different_schemes(self):
        """Test with different URL schemes."""
        assert to_mock_url("http://host/invoke") == "http://host/mock"
        assert to_mock_url("https://host/invoke") == "https://host/mock"
        # Edge case: other schemes
        assert to_mock_url("ftp://host/invoke") == "ftp://host/mock"


class TestCommandHelpers:
    """Test command handling utilities."""

    def test_show_help_message(self):
        """Test help message display."""
        mock_console = Mock()
        show_help_message(mock_console)
        
        # Verify console.print was called multiple times
        assert mock_console.print.call_count > 10
        
        # Check some key help content was displayed
        calls = [str(call) for call in mock_console.print.call_args_list]
        help_content = " ".join(calls)
        
        assert "/help" in help_content
        assert "/clear" in help_content 
        assert "/exit" in help_content
        assert "Ctrl+J" in help_content
        assert "Enter" in help_content
        assert "Markdown" in help_content
    
    def test_handle_special_commands_clear_signal(self):
        """Test handling __CLEAR__ signal."""
        mock_conversation = Mock()
        
        result = handle_special_commands("__CLEAR__", mock_conversation)
        
        assert result is True
        mock_conversation.clear_history.assert_called_once()
    
    def test_handle_special_commands_clear_command(self):
        """Test handling /clear command."""
        mock_conversation = Mock()
        
        # Test exact match
        result = handle_special_commands("/clear", mock_conversation)
        assert result is True
        mock_conversation.clear_history.assert_called_once()
        
        # Test with whitespace
        mock_conversation.reset_mock()
        result = handle_special_commands("  /clear  ", mock_conversation)
        assert result is True
        mock_conversation.clear_history.assert_called_once()
        
        # Test case insensitive
        mock_conversation.reset_mock()
        result = handle_special_commands("/CLEAR", mock_conversation)
        assert result is True
        mock_conversation.clear_history.assert_called_once()
    
    def test_handle_special_commands_help_command(self):
        """Test handling /help command."""
        mock_conversation = Mock()
        mock_console = Mock()
        
        # Test with console
        result = handle_special_commands("/help", mock_conversation, console=mock_console)
        assert result is True
        mock_console.print.assert_called()
        
        # Test without console
        result = handle_special_commands("/help", mock_conversation)
        assert result is True
        
        # Test case insensitive with whitespace
        mock_console.reset_mock()
        result = handle_special_commands("  /HELP  ", mock_conversation, console=mock_console)
        assert result is True
        mock_console.print.assert_called()
    
    def test_handle_special_commands_none_input(self):
        """Test handling None input."""
        mock_conversation = Mock()
        
        result = handle_special_commands(None, mock_conversation)
        assert result is True
        mock_conversation.clear_history.assert_not_called()
    
    def test_handle_special_commands_empty_input(self):
        """Test handling empty input."""
        mock_conversation = Mock()
        
        result = handle_special_commands("", mock_conversation)
        assert result is False
        mock_conversation.clear_history.assert_not_called()
    
    def test_handle_special_commands_regular_input(self):
        """Test handling regular (non-command) input."""
        mock_conversation = Mock()
        
        test_inputs = [
            "Hello, how are you?",
            "What is 2+2?",
            "clear the table",  # Contains "clear" but not command
            "help me with this", # Contains "help" but not command
            "/unknown_command",
            "some/clear/path"
        ]
        
        for input_text in test_inputs:
            result = handle_special_commands(input_text, mock_conversation)
            assert result is False, f"Input '{input_text}' should not be handled as command"
            mock_conversation.clear_history.assert_not_called()
    
    def test_handle_special_commands_whitespace_only(self):
        """Test handling whitespace-only input."""
        mock_conversation = Mock()
        
        whitespace_inputs = ["   ", "\t", "\n", "  \t\n  "]
        
        for input_text in whitespace_inputs:
            result = handle_special_commands(input_text, mock_conversation)
            assert result is False
            mock_conversation.clear_history.assert_not_called()
    
    def test_handle_special_commands_partial_matches(self):
        """Test that partial command matches are not handled."""
        mock_conversation = Mock()
        
        partial_matches = [
            "clear",      # Missing /
            "help",       # Missing /
            "/clearall",  # Extra characters
            "/helping",   # Extra characters  
            "please /clear this",  # Not at start
            "can you /help me"     # Not at start
        ]
        
        for input_text in partial_matches:
            result = handle_special_commands(input_text, mock_conversation)
            assert result is False, f"Partial match '{input_text}' should not be handled"
            mock_conversation.clear_history.assert_not_called()


# Standalone test functions for non-pytest execution
def test_url_helpers():
    """Run all URL helper tests."""
    helper = TestUrlHelpers()
    helper.test_to_mock_url_invoke_replacement()
    helper.test_to_mock_url_root_path()
    helper.test_to_mock_url_existing_path()
    helper.test_to_mock_url_already_mock()
    helper.test_to_mock_url_trailing_slash()
    helper.test_to_mock_url_query_removal()
    helper.test_to_mock_url_complex_paths()
    helper.test_to_mock_url_different_schemes()


def test_command_helpers():
    """Run all command helper tests."""
    helper = TestCommandHelpers()
    helper.test_show_help_message()
    helper.test_handle_special_commands_clear_signal()
    helper.test_handle_special_commands_clear_command()
    helper.test_handle_special_commands_help_command()
    helper.test_handle_special_commands_none_input()
    helper.test_handle_special_commands_empty_input()
    helper.test_handle_special_commands_regular_input()
    helper.test_handle_special_commands_whitespace_only()
    helper.test_handle_special_commands_partial_matches()


if __name__ == "__main__":
    if pytest:
        pytest.main([__file__])
    else:
        # Run tests manually
        print("Running utility helper tests...")
        test_url_helpers()
        test_command_helpers() 
        print("All utility helper tests passed!")