#!/usr/bin/env python3
"""
Test script for usage tracker functionality.
"""

import sys
import os

try:
    import pytest
except ImportError:
    pytest = None

# Add parent directory to path to import our modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from chat.usage_tracker import UsageTracker


def test_usage_tracker_initialization():
    """Test UsageTracker initialization with default values."""
    tracker = UsageTracker()
    assert tracker.total_tokens_used == 0
    assert tracker.total_cost == 0.0
    assert tracker.max_tokens_limit == 200000


def test_usage_tracker_custom_limit():
    """Test UsageTracker initialization with custom limit."""
    tracker = UsageTracker(max_tokens_limit=100000)
    assert tracker.max_tokens_limit == 100000
    assert tracker.total_tokens_used == 0
    assert tracker.total_cost == 0.0


def test_update_tokens_and_cost():
    """Test updating tokens and cost."""
    tracker = UsageTracker()
    
    tracker.update(1000, 0.05)
    assert tracker.total_tokens_used == 1000
    assert tracker.total_cost == 0.05
    
    tracker.update(500, 0.025)
    assert tracker.total_tokens_used == 1500
    assert abs(tracker.total_cost - 0.075) < 0.0001  # Handle floating point precision


def test_update_zero_values():
    """Test updating with zero values."""
    tracker = UsageTracker()
    
    tracker.update(0, 0.0)
    assert tracker.total_tokens_used == 0
    assert tracker.total_cost == 0.0
    
    # Add some values first
    tracker.update(1000, 0.05)
    
    # Zero updates should not change values
    tracker.update(0, 0.0)
    assert tracker.total_tokens_used == 1000
    assert tracker.total_cost == 0.05


def test_update_negative_values():
    """Test updating with negative values (should be ignored)."""
    tracker = UsageTracker()
    
    tracker.update(1000, 0.05)
    assert tracker.total_tokens_used == 1000
    assert tracker.total_cost == 0.05
    
    # Negative values should not change totals
    tracker.update(-500, -0.02)
    assert tracker.total_tokens_used == 1000
    assert tracker.total_cost == 0.05


def test_get_display_string_no_usage():
    """Test display string when no tokens have been used."""
    tracker = UsageTracker()
    assert tracker.get_display_string() is None


def test_get_display_string_small_numbers():
    """Test display string formatting for small numbers."""
    tracker = UsageTracker(max_tokens_limit=10000)
    
    tracker.update(500, 0.0025)
    display = tracker.get_display_string()
    
    # Should show raw numbers for < 1000 tokens
    assert "500/10000 (5.0%)" in display
    # Cost formatting may vary slightly, check for reasonable precision
    assert "$0.0025" in display or "$0.002500" in display


def test_get_display_string_large_numbers():
    """Test display string formatting for large numbers."""
    tracker = UsageTracker(max_tokens_limit=200000)
    
    tracker.update(150000, 0.75)
    display = tracker.get_display_string()
    
    # Should show k notation for >= 1000 tokens
    assert "150.0k/200k (75.0%)" in display
    assert "$0.750" in display


def test_get_display_string_cost_precision():
    """Test display string cost precision based on magnitude."""
    tracker = UsageTracker()
    
    # High precision for very small costs
    tracker.update(1000, 0.000123)
    display = tracker.get_display_string()
    assert "$0.000123" in display
    
    # Medium precision for small costs
    tracker.total_cost = 0.0045
    display = tracker.get_display_string()
    assert "$0.0045" in display
    
    # Low precision for larger costs
    tracker.total_cost = 0.123456
    display = tracker.get_display_string()
    assert "$0.123" in display


def test_get_display_string_percentage_calculation():
    """Test percentage calculation in display string."""
    # Test various percentages
    test_cases = [
        (1000, 100000, 1.0),    # 1%
        (5000, 100000, 5.0),    # 5%
        (25000, 100000, 25.0),  # 25%
        (50000, 100000, 50.0),  # 50%
        (99999, 100000, 100.0), # ~100%
    ]
    
    for tokens, limit, expected_pct in test_cases:
        tracker = UsageTracker(max_tokens_limit=limit)
        tracker.update(tokens, 0.01)
        display = tracker.get_display_string()
        assert f"({expected_pct}%)" in display


def test_get_display_string_k_notation_threshold():
    """Test k notation threshold at 1000 tokens."""
    tracker = UsageTracker(max_tokens_limit=10000)
    
    # Just under 1000 - should show raw numbers
    tracker.update(999, 0.01)
    display = tracker.get_display_string()
    assert "999/10000" in display
    
    # Exactly 1000 - should show k notation
    tracker.total_tokens_used = 1000
    display = tracker.get_display_string()
    assert "1.0k/10k" in display


def test_multiple_updates():
    """Test multiple sequential updates."""
    tracker = UsageTracker(max_tokens_limit=50000)
    
    # Simulate multiple API calls
    updates = [
        (1200, 0.006),
        (800, 0.004),
        (1500, 0.0075),
        (2000, 0.010),
        (500, 0.0025),
    ]
    
    expected_total_tokens = sum(tokens for tokens, _ in updates)
    expected_total_cost = sum(cost for _, cost in updates)
    
    for tokens, cost in updates:
        tracker.update(tokens, cost)
    
    assert tracker.total_tokens_used == expected_total_tokens  # 6000
    assert abs(tracker.total_cost - expected_total_cost) < 0.0001  # ~0.030
    
    display = tracker.get_display_string()
    assert "6.0k/50k" in display
    assert "(12.0%)" in display


def test_edge_case_zero_limit():
    """Test edge case with zero token limit."""
    tracker = UsageTracker(max_tokens_limit=0)
    
    tracker.update(100, 0.001)
    display = tracker.get_display_string()
    
    # Should handle division by zero gracefully (will show inf%)
    assert "100/0" in display
    assert "(inf%)" in display


def test_cost_formatting_edge_cases():
    """Test cost formatting for various edge cases."""
    tracker = UsageTracker()
    
    # Very small cost
    tracker.update(1000, 0.0000001)
    display = tracker.get_display_string()
    assert "$0.000000" in display
    
    # Exactly at threshold boundaries
    tracker.total_cost = 0.001  # Boundary for 4-digit precision
    display = tracker.get_display_string()
    assert "$0.0010" in display
    
    tracker.total_cost = 0.01   # Boundary for 3-digit precision
    display = tracker.get_display_string()
    assert "$0.010" in display


def test_realistic_usage_scenario():
    """Test realistic usage scenario with typical values."""
    tracker = UsageTracker(max_tokens_limit=200000)
    
    # Simulate a conversation with multiple exchanges
    conversation_updates = [
        (1250, 0.00625),   # Initial user message + response
        (890, 0.00445),    # Follow-up exchange
        (2100, 0.0105),    # Longer response with reasoning
        (750, 0.00375),    # Short clarification
        (1800, 0.009),     # Tool usage response
    ]
    
    for tokens, cost in conversation_updates:
        tracker.update(tokens, cost)
    
    display = tracker.get_display_string()
    
    # Should show k notation (6.79k total)
    assert "6.8k/200k" in display
    assert "(3.4%)" in display
    assert "$0.034" in display  # Should use 3-digit precision


def test_update_with_only_tokens():
    """Test updating with only tokens (zero cost)."""
    tracker = UsageTracker()
    
    tracker.update(5000, 0.0)
    
    assert tracker.total_tokens_used == 5000
    assert tracker.total_cost == 0.0
    
    display = tracker.get_display_string()
    assert "5.0k/200k" in display
    assert "$0.000000" in display


def test_update_with_only_cost():
    """Test updating with only cost (zero tokens)."""
    tracker = UsageTracker()

    tracker.update(0, 0.025)

    assert tracker.total_tokens_used == 0
    assert tracker.total_cost == 0.025

    # Should return None since no tokens used
    assert tracker.get_display_string() is None


def test_gpt5_pricing_calculations():
    """Test cost calculations using GPT-5 pricing."""
    tracker = UsageTracker()

    # GPT-5 pricing: $0.00091/1K input, $0.00677/1K output
    # Test case: 10 input tokens, 549 output tokens (from example)
    input_tokens = 10
    output_tokens = 549
    total_tokens = input_tokens + output_tokens

    expected_input_cost = (input_tokens / 1000) * 0.00091
    expected_output_cost = (output_tokens / 1000) * 0.00677
    expected_total_cost = expected_input_cost + expected_output_cost

    tracker.update(total_tokens, expected_total_cost)

    assert tracker.total_tokens_used == 559
    assert abs(tracker.total_cost - expected_total_cost) < 0.0001

    display = tracker.get_display_string()
    assert "559/200000" in display
    # Should use 4-digit precision for costs in the $0.001-$0.01 range
    assert "$0.0037" in display


def test_claude4_pricing_calculations():
    """Test cost calculations using Claude 4 Sonnet pricing."""
    tracker = UsageTracker()

    # Claude 4 Sonnet pricing: $0.00204/1K input, $0.00988/1K output
    # Test case: 15 input tokens, 25 output tokens
    input_tokens = 15
    output_tokens = 25
    total_tokens = input_tokens + output_tokens

    expected_input_cost = (input_tokens / 1000) * 0.00204
    expected_output_cost = (output_tokens / 1000) * 0.00988
    expected_total_cost = expected_input_cost + expected_output_cost

    tracker.update(total_tokens, expected_total_cost)

    assert tracker.total_tokens_used == 40
    assert abs(tracker.total_cost - expected_total_cost) < 0.0001

    display = tracker.get_display_string()
    assert "40/200000" in display


def test_provider_pricing_comparison():
    """Test cost difference between providers for same token usage."""
    gpt5_tracker = UsageTracker()
    claude4_tracker = UsageTracker()

    # Same usage: 1000 input, 2000 output tokens
    input_tokens = 1000
    output_tokens = 2000
    total_tokens = input_tokens + output_tokens

    # GPT-5 cost calculation
    gpt5_input_cost = (input_tokens / 1000) * 0.00091
    gpt5_output_cost = (output_tokens / 1000) * 0.00677
    gpt5_total_cost = gpt5_input_cost + gpt5_output_cost

    # Claude 4 cost calculation
    claude4_input_cost = (input_tokens / 1000) * 0.00204
    claude4_output_cost = (output_tokens / 1000) * 0.00988
    claude4_total_cost = claude4_input_cost + claude4_output_cost

    gpt5_tracker.update(total_tokens, gpt5_total_cost)
    claude4_tracker.update(total_tokens, claude4_total_cost)

    # Both should have same token count
    assert gpt5_tracker.total_tokens_used == claude4_tracker.total_tokens_used == 3000

    # But different costs (Claude 4 should be more expensive)
    assert claude4_tracker.total_cost > gpt5_tracker.total_cost

    # Verify specific costs
    expected_gpt5_cost = 0.00091 + 0.01354  # $0.014450
    expected_claude4_cost = 0.00204 + 0.01976  # $0.021800

    assert abs(gpt5_tracker.total_cost - expected_gpt5_cost) < 0.0001
    assert abs(claude4_tracker.total_cost - expected_claude4_cost) < 0.0001


def test_high_volume_usage_tracking():
    """Test usage tracking with high token volumes and costs."""
    tracker = UsageTracker(max_tokens_limit=1000000)  # 1M limit

    # Simulate multiple large conversations
    conversations = [
        (50000, 0.25),    # Large document analysis
        (75000, 0.38),    # Code review session
        (30000, 0.15),    # Q&A session
        (120000, 0.60),   # Long reasoning task
        (25000, 0.12),    # Summary generation
    ]

    total_expected_tokens = sum(tokens for tokens, _ in conversations)
    total_expected_cost = sum(cost for _, cost in conversations)

    for tokens, cost in conversations:
        tracker.update(tokens, cost)

    assert tracker.total_tokens_used == total_expected_tokens  # 300,000
    assert abs(tracker.total_cost - total_expected_cost) < 0.0001  # $1.50

    display = tracker.get_display_string()
    assert "300.0k/1000k" in display
    assert "(30.0%)" in display
    assert "$1.500" in display  # Should use 3-digit precision


def test_cost_accumulation_precision():
    """Test that repeated small cost additions maintain precision."""
    tracker = UsageTracker()

    # Add many small costs that could cause floating point drift
    small_cost = 0.000123
    small_tokens = 100
    iterations = 1000

    for _ in range(iterations):
        tracker.update(small_tokens, small_cost)

    expected_total_tokens = small_tokens * iterations  # 100,000
    expected_total_cost = small_cost * iterations      # 0.123

    assert tracker.total_tokens_used == expected_total_tokens
    # Allow for small floating point precision differences
    assert abs(tracker.total_cost - expected_total_cost) < 0.0001

    display = tracker.get_display_string()
    assert "100.0k/200k" in display
    assert "(50.0%)" in display


def test_token_parsing_format_validation():
    """Test that the tracker works with the token format from providers."""
    tracker = UsageTracker()

    # Simulate parsing token info from provider: "total|input|output|cost"
    token_info_azure = "559|10|549|0.003726"  # GPT-5 example
    token_info_bedrock = "40|15|25|0.000277"   # Claude 4 example

    # Parse Azure format
    parts = token_info_azure.split("|")
    azure_tokens = int(parts[0])
    azure_cost = float(parts[3])
    tracker.update(azure_tokens, azure_cost)

    # Parse Bedrock format
    parts = token_info_bedrock.split("|")
    bedrock_tokens = int(parts[0])
    bedrock_cost = float(parts[3])
    tracker.update(bedrock_tokens, bedrock_cost)

    # Verify totals
    assert tracker.total_tokens_used == 599  # 559 + 40
    expected_total_cost = 0.003726 + 0.000277
    assert abs(tracker.total_cost - expected_total_cost) < 0.0001

    display = tracker.get_display_string()
    assert "599/200000" in display


if __name__ == "__main__":
    if pytest:
        pytest.main([__file__])
    else:
        # Run tests manually
        print("Running usage tracker tests...")
        test_usage_tracker_initialization()
        test_usage_tracker_custom_limit()
        test_update_tokens_and_cost()
        test_update_zero_values()
        test_update_negative_values()
        test_get_display_string_no_usage()
        test_get_display_string_small_numbers()
        test_get_display_string_large_numbers()
        test_get_display_string_cost_precision()
        test_get_display_string_percentage_calculation()
        test_get_display_string_k_notation_threshold()
        test_multiple_updates()
        test_edge_case_zero_limit()
        test_cost_formatting_edge_cases()
        test_realistic_usage_scenario()
        test_update_with_only_tokens()
        test_update_with_only_cost()
        test_gpt5_pricing_calculations()
        test_claude4_pricing_calculations()
        test_provider_pricing_comparison()
        test_high_volume_usage_tracking()
        test_cost_accumulation_precision()
        test_token_parsing_format_validation()
        print("All usage tracker tests passed!")