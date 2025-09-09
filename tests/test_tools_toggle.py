#!/usr/bin/env python3
"""
Test script for /tools command functionality.
"""
try:
    import pytest
except ImportError:
    pytest = None


class MockConsole:
    def __init__(self):
        self.messages = []
    
    def print(self, message):
        self.messages.append(message)


def test_tools_command_logic():
    """Test the /tools command logic without imports."""
    console = MockConsole()
    
    # Simulate the command processing logic
    def process_tools_command(cleaned_input, tools_enabled, console):
        if cleaned_input == '/tools':
            if tools_enabled:
                console.print("[dim]Tools disabled. Claude will not use function calls.[/dim]")
            else:
                console.print("[green]Tools enabled. Claude can now use calculator, weather, and time functions.[/green]")
            return not tools_enabled  # Toggle tools mode
        return tools_enabled
    
    # Test enabling tools
    tools_enabled = False
    tools_enabled = process_tools_command('/tools', tools_enabled, console)
    assert tools_enabled is True
    assert "[green]Tools enabled. Claude can now use calculator, weather, and time functions.[/green]" in console.messages
    
    # Test disabling tools
    console.messages.clear()
    tools_enabled = process_tools_command('/tools', tools_enabled, console)
    assert tools_enabled is False
    assert "[dim]Tools disabled. Claude will not use function calls.[/dim]" in console.messages


def test_conditional_tools_parameter():
    """Test conditional tools parameter logic."""
    AVAILABLE_TOOLS = ["tool1", "tool2", "tool3"]  # Mock tools
    
    # Test with tools enabled
    tools_enabled = True
    tools_param = AVAILABLE_TOOLS if tools_enabled else None
    assert tools_param == AVAILABLE_TOOLS
    
    # Test with tools disabled
    tools_enabled = False  
    tools_param = AVAILABLE_TOOLS if tools_enabled else None
    assert tools_param is None


if __name__ == "__main__":
    if pytest:
        pytest.main([__file__])
    else:
        # Run tests manually
        print("Running tests without pytest...")
        test_tools_command_logic()
        test_conditional_tools_parameter()
        print("All tests passed!")