#!/usr/bin/env python3
"""
Test script for conversation management functionality.
"""

import sys
import os

try:
    import pytest
except ImportError:
    pytest = None

# Add parent directory to path to import our modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from chat.conversation import ConversationManager


def test_conversation_manager_initialization():
    """Test ConversationManager initialization."""
    manager = ConversationManager()
    assert manager.history == []
    assert isinstance(manager.history, list)


def test_add_user_message():
    """Test adding user messages to conversation."""
    manager = ConversationManager()
    
    manager.add_user_message("Hello, how are you?")
    assert len(manager.history) == 1
    assert manager.history[0]["role"] == "user"
    assert manager.history[0]["content"] == "Hello, how are you?"
    
    manager.add_user_message("What is 2+2?")
    assert len(manager.history) == 2
    assert manager.history[1]["role"] == "user"
    assert manager.history[1]["content"] == "What is 2+2?"


def test_add_assistant_message():
    """Test adding assistant messages to conversation."""
    manager = ConversationManager()
    
    manager.add_assistant_message("Hello! I'm doing well, thank you.")
    assert len(manager.history) == 1
    assert manager.history[0]["role"] == "assistant"
    assert manager.history[0]["content"] == "Hello! I'm doing well, thank you."


def test_add_assistant_message_empty():
    """Test that empty assistant messages are filtered out."""
    manager = ConversationManager()
    
    # These should be filtered out
    manager.add_assistant_message("")
    manager.add_assistant_message("   ")
    manager.add_assistant_message("\t\n  ")
    
    assert len(manager.history) == 0
    
    # This should be added
    manager.add_assistant_message("Valid response")
    assert len(manager.history) == 1
    assert manager.history[0]["content"] == "Valid response"


def test_add_tool_messages():
    """Test adding tool messages to conversation."""
    manager = ConversationManager()
    
    tool_messages = [
        {
            "role": "assistant",
            "content": [
                {
                    "type": "tool_use",
                    "id": "toolu_123",
                    "name": "calculate",
                    "input": {"expression": "2 + 2"}
                }
            ]
        },
        {
            "role": "user",
            "content": [
                {
                    "type": "tool_result",
                    "tool_use_id": "toolu_123",
                    "content": "4"
                }
            ]
        }
    ]
    
    manager.add_tool_messages(tool_messages)
    assert len(manager.history) == 2
    assert manager.history[0]["role"] == "assistant"
    assert manager.history[1]["role"] == "user"
    assert manager.history[1]["content"][0]["content"] == "4"


def test_clear_history():
    """Test clearing conversation history."""
    manager = ConversationManager()
    
    manager.add_user_message("Test message")
    manager.add_assistant_message("Test response")
    assert len(manager.history) == 2
    
    manager.clear_history()
    assert len(manager.history) == 0
    assert manager.history == []


def test_get_sanitized_history():
    """Test getting sanitized conversation history."""
    manager = ConversationManager()
    
    # Add valid messages
    manager.add_user_message("Hello")
    manager.add_assistant_message("Hi there!")
    
    # Add messages that should be filtered
    manager.history.append({"role": "assistant", "content": ""})
    manager.history.append({"role": "assistant", "content": "   "})
    manager.history.append({"role": "assistant", "content": []})
    
    # Add another valid message
    manager.add_user_message("How are you?")
    manager.add_assistant_message("I'm good!")
    
    sanitized = manager.get_sanitized_history()
    
    assert len(sanitized) == 4  # Only valid messages
    assert sanitized[0]["role"] == "user"
    assert sanitized[0]["content"] == "Hello"
    assert sanitized[1]["role"] == "assistant"
    assert sanitized[1]["content"] == "Hi there!"
    assert sanitized[2]["role"] == "user"
    assert sanitized[2]["content"] == "How are you?"
    assert sanitized[3]["role"] == "assistant"
    assert sanitized[3]["content"] == "I'm good!"


def test_get_sanitized_history_tool_messages():
    """Test sanitized history with tool messages."""
    manager = ConversationManager()
    
    # Add normal message
    manager.add_user_message("Calculate 2+2")
    
    # Add tool messages
    manager.history.append({
        "role": "assistant",
        "content": [
            {
                "type": "tool_use",
                "id": "toolu_123",
                "name": "calculate",
                "input": {"expression": "2 + 2"}
            }
        ]
    })
    
    # Add empty tool message (should be filtered)
    manager.history.append({
        "role": "assistant",
        "content": []
    })
    
    # Add tool result
    manager.history.append({
        "role": "user",
        "content": [
            {
                "type": "tool_result",
                "tool_use_id": "toolu_123",
                "content": "4"
            }
        ]
    })
    
    sanitized = manager.get_sanitized_history()
    
    assert len(sanitized) == 3  # User message, tool use, tool result
    assert sanitized[0]["role"] == "user"
    assert sanitized[1]["role"] == "assistant"
    assert len(sanitized[1]["content"]) == 1
    assert sanitized[2]["role"] == "user"


def test_get_user_history():
    """Test extracting user message history."""
    manager = ConversationManager()
    
    manager.add_user_message("First message")
    manager.add_assistant_message("Response 1")
    manager.add_user_message("Second message")
    manager.add_assistant_message("Response 2")
    manager.add_user_message("Third message")
    
    # Add tool message (should not be included)
    manager.history.append({
        "role": "user",
        "content": [
            {
                "type": "tool_result",
                "tool_use_id": "toolu_123",
                "content": "tool result"
            }
        ]
    })
    
    user_history = manager.get_user_history()
    
    expected = ["First message", "Second message", "Third message"]
    assert user_history == expected


def test_complex_conversation_flow():
    """Test a complex conversation with mixed message types."""
    manager = ConversationManager()
    
    # User starts conversation
    manager.add_user_message("Hello, can you help me with math?")
    manager.add_assistant_message("Of course! What math problem do you need help with?")
    
    # User asks for calculation
    manager.add_user_message("What's the square root of 16?")
    
    # Tool calling flow
    tool_messages = [
        {
            "role": "assistant",
            "content": [
                {
                    "type": "tool_use",
                    "id": "toolu_456",
                    "name": "calculate",
                    "input": {"expression": "sqrt(16)"}
                }
            ]
        },
        {
            "role": "user",
            "content": [
                {
                    "type": "tool_result",
                    "tool_use_id": "toolu_456",
                    "content": "4"
                }
            ]
        }
    ]
    manager.add_tool_messages(tool_messages)
    
    # Assistant responds with result
    manager.add_assistant_message("The square root of 16 is 4.")
    
    # User thanks
    manager.add_user_message("Thank you!")
    manager.add_assistant_message("You're welcome!")
    
    # Test final state
    assert len(manager.history) == 8
    
    # Test sanitized history
    sanitized = manager.get_sanitized_history()
    assert len(sanitized) == 8
    
    # Test user history
    user_history = manager.get_user_history()
    expected_user_messages = [
        "Hello, can you help me with math?",
        "What's the square root of 16?",
        "Thank you!"
    ]
    assert user_history == expected_user_messages
    
    # Verify conversation alternation
    roles = [msg["role"] for msg in sanitized]
    expected_roles = ["user", "assistant", "user", "assistant", "user", "assistant", "user", "assistant"]
    assert roles == expected_roles


def test_empty_conversation():
    """Test operations on empty conversation."""
    manager = ConversationManager()
    
    assert manager.get_sanitized_history() == []
    assert manager.get_user_history() == []
    
    # Clear empty history should work
    manager.clear_history()
    assert manager.history == []


def test_conversation_with_only_empty_messages():
    """Test conversation that only contains messages that get filtered."""
    manager = ConversationManager()
    
    # Add only empty/whitespace assistant messages
    manager.history.append({"role": "assistant", "content": ""})
    manager.history.append({"role": "assistant", "content": "   "})
    manager.history.append({"role": "assistant", "content": []})
    
    sanitized = manager.get_sanitized_history()
    assert sanitized == []
    
    user_history = manager.get_user_history()
    assert user_history == []


if __name__ == "__main__":
    if pytest:
        pytest.main([__file__])
    else:
        # Run tests manually
        print("Running conversation management tests...")
        test_conversation_manager_initialization()
        test_add_user_message()
        test_add_assistant_message()
        test_add_assistant_message_empty()
        test_add_tool_messages()
        test_clear_history()
        test_get_sanitized_history()
        test_get_sanitized_history_tool_messages()
        test_get_user_history()
        test_complex_conversation_flow()
        test_empty_conversation()
        test_conversation_with_only_empty_messages()
        print("All conversation management tests passed!")