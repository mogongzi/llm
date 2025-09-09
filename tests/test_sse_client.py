#!/usr/bin/env python3
"""
Test script for SSE client functionality.
"""

import sys
import os
from unittest.mock import Mock, patch, MagicMock
from io import StringIO

try:
    import pytest
except ImportError:
    pytest = None

# Add parent directory to path to import our modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from util.sse_client import iter_sse_lines


def test_sse_lines_basic():
    """Test basic SSE line parsing."""
    # Mock response with SSE lines
    mock_response = Mock()
    mock_response.iter_lines.return_value = [
        "data: Hello world",
        "data: Second line",
        "",
        "data: Third line"
    ]
    mock_response.raise_for_status.return_value = None
    
    # Mock session
    mock_session = Mock()
    mock_session.post.return_value.__enter__ = Mock(return_value=mock_response)
    mock_session.post.return_value.__exit__ = Mock(return_value=None)
    
    lines = list(iter_sse_lines("http://test.com", json={"test": "data"}, session=mock_session))
    
    expected = ["Hello world", "Second line", "Third line"]
    assert lines == expected


def test_sse_lines_data_prefix_stripping():
    """Test that 'data:' prefix is properly stripped."""
    mock_response = Mock()
    mock_response.iter_lines.return_value = [
        "data: Content with spaces",
        "data:No space after colon",
        "data:   Multiple spaces",
        "event: some-event",  # Non-data line
        "data: Final line"
    ]
    mock_response.raise_for_status.return_value = None
    
    mock_session = Mock()
    mock_session.post.return_value.__enter__ = Mock(return_value=mock_response)
    mock_session.post.return_value.__exit__ = Mock(return_value=None)
    
    lines = list(iter_sse_lines("http://test.com", session=mock_session))
    
    expected = ["Content with spaces", "No space after colon", "Multiple spaces", "event: some-event", "Final line"]
    assert lines == expected


def test_sse_lines_empty_line_filtering():
    """Test that empty lines are filtered out."""
    mock_response = Mock()
    mock_response.iter_lines.return_value = [
        "data: Line 1",
        "",
        None,
        "data: Line 2",
        "",
        "data: Line 3"
    ]
    mock_response.raise_for_status.return_value = None
    
    mock_session = Mock()
    mock_session.post.return_value.__enter__ = Mock(return_value=mock_response)
    mock_session.post.return_value.__exit__ = Mock(return_value=None)
    
    lines = list(iter_sse_lines("http://test.com", session=mock_session))
    
    expected = ["Line 1", "Line 2", "Line 3"]
    assert lines == expected


def test_sse_lines_get_method():
    """Test SSE client with GET method."""
    mock_response = Mock()
    mock_response.iter_lines.return_value = ["data: GET response"]
    mock_response.raise_for_status.return_value = None
    
    mock_session = Mock()
    mock_session.get.return_value.__enter__ = Mock(return_value=mock_response)
    mock_session.get.return_value.__exit__ = Mock(return_value=None)
    
    lines = list(iter_sse_lines("http://test.com", method="GET", session=mock_session))
    
    assert lines == ["GET response"]
    mock_session.get.assert_called_once()


def test_sse_lines_custom_timeout():
    """Test SSE client with custom timeout."""
    mock_response = Mock()
    mock_response.iter_lines.return_value = ["data: Test"]
    mock_response.raise_for_status.return_value = None
    
    mock_session = Mock()
    mock_session.post.return_value.__enter__ = Mock(return_value=mock_response)
    mock_session.post.return_value.__exit__ = Mock(return_value=None)
    
    list(iter_sse_lines("http://test.com", timeout=120.0, session=mock_session))
    
    mock_session.post.assert_called_once_with(
        "http://test.com", 
        json=None, 
        params=None, 
        stream=True, 
        timeout=120.0
    )


def test_sse_lines_with_params():
    """Test SSE client with query parameters."""
    mock_response = Mock()
    mock_response.iter_lines.return_value = ["data: Params test"]
    mock_response.raise_for_status.return_value = None
    
    mock_session = Mock()
    mock_session.post.return_value.__enter__ = Mock(return_value=mock_response)
    mock_session.post.return_value.__exit__ = Mock(return_value=None)
    
    params = {"key": "value", "test": "123"}
    list(iter_sse_lines("http://test.com", params=params, session=mock_session))
    
    mock_session.post.assert_called_once_with(
        "http://test.com", 
        json=None, 
        params=params, 
        stream=True, 
        timeout=60.0
    )


@patch('util.sse_client.requests.Session')
def test_sse_lines_default_session(mock_session_class):
    """Test SSE client creates default session when none provided."""
    mock_session = Mock()
    mock_session_class.return_value = mock_session
    
    mock_response = Mock()
    mock_response.iter_lines.return_value = ["data: Default session"]
    mock_response.raise_for_status.return_value = None
    
    mock_session.post.return_value.__enter__ = Mock(return_value=mock_response)
    mock_session.post.return_value.__exit__ = Mock(return_value=None)
    
    lines = list(iter_sse_lines("http://test.com", json={"test": True}))
    
    mock_session_class.assert_called_once()
    assert lines == ["Default session"]


def test_sse_lines_http_error():
    """Test SSE client handles HTTP errors."""
    mock_response = Mock()
    mock_response.raise_for_status.side_effect = Exception("HTTP 500 Error")
    
    mock_session = Mock()
    mock_session.post.return_value.__enter__ = Mock(return_value=mock_response)
    mock_session.post.return_value.__exit__ = Mock(return_value=None)
    
    try:
        list(iter_sse_lines("http://test.com", session=mock_session))
        assert False, "Expected exception to be raised"
    except Exception as e:
        assert "HTTP 500 Error" in str(e)


def test_sse_lines_json_payload():
    """Test SSE client with JSON payload."""
    mock_response = Mock()
    mock_response.iter_lines.return_value = ["data: JSON test"]
    mock_response.raise_for_status.return_value = None
    
    mock_session = Mock()
    mock_session.post.return_value.__enter__ = Mock(return_value=mock_response)
    mock_session.post.return_value.__exit__ = Mock(return_value=None)
    
    json_data = {"message": "Hello", "items": [1, 2, 3]}
    list(iter_sse_lines("http://test.com", json=json_data, session=mock_session))
    
    mock_session.post.assert_called_once_with(
        "http://test.com", 
        json=json_data, 
        params=None, 
        stream=True, 
        timeout=60.0
    )


def test_sse_lines_mixed_content():
    """Test SSE client with mixed SSE content types."""
    mock_response = Mock()
    mock_response.iter_lines.return_value = [
        "event: message",
        "data: Event message",
        "id: 123",
        "data: Another message", 
        ": this is a comment",
        "data: Final message",
        ""
    ]
    mock_response.raise_for_status.return_value = None
    
    mock_session = Mock()
    mock_session.post.return_value.__enter__ = Mock(return_value=mock_response)
    mock_session.post.return_value.__exit__ = Mock(return_value=None)
    
    lines = list(iter_sse_lines("http://test.com", session=mock_session))
    
    expected = [
        "event: message",
        "Event message", 
        "id: 123",
        "Another message",
        ": this is a comment",
        "Final message"
    ]
    assert lines == expected


if __name__ == "__main__":
    if pytest:
        pytest.main([__file__])
    else:
        # Run tests manually
        print("Running SSE client tests...")
        test_sse_lines_basic()
        test_sse_lines_data_prefix_stripping()
        test_sse_lines_empty_line_filtering()
        test_sse_lines_get_method()
        test_sse_lines_custom_timeout()
        test_sse_lines_with_params()
        test_sse_lines_http_error()
        test_sse_lines_json_payload()
        test_sse_lines_mixed_content()
        print("All SSE client tests passed!")