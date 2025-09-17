"""Tests for debug client mock interactions."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from debug.debug import stream_response_http, stream_response_raw


class DummyProvider:
    """Minimal provider shim for event mapping."""

    @staticmethod
    def map_events(_):
        yield ("done", None)


@patch("debug.debug.requests.post")
def test_stream_response_http_posts_to_mock(mock_post):
    """Ensure mock mode uses POST with expected payload."""
    response = MagicMock()
    response.__enter__.return_value = response
    response.__exit__.return_value = None
    response.ok = True
    response.iter_lines.return_value = []
    response.status_code = 200
    response.text = ""
    mock_post.return_value = response

    status = stream_response_http(
        "http://localhost:8000/mock",
        DummyProvider,
        {},
        use_mock=True,
        mock_file="custom.dat",
        mock_delay=123,
    )

    assert status == 0
    mock_post.assert_called_once()
    args, kwargs = mock_post.call_args
    assert args[0] == "http://localhost:8000/mock"
    assert kwargs["json"] == {"file": "custom.dat", "delay_ms": 123}
    assert kwargs["stream"] is True


@patch("debug.debug.requests.post")
def test_stream_response_raw_posts_to_mock(mock_post):
    """Ensure raw streaming posts to /mock with payload."""
    response = MagicMock()
    response.__enter__.return_value = response
    response.__exit__.return_value = None
    response.ok = True
    response.iter_lines.return_value = []
    response.status_code = 200
    response.text = ""
    mock_post.return_value = response

    status = stream_response_raw(
        "http://localhost:8000/mock",
        DummyProvider,
        {},
        use_mock=True,
        mock_file=None,
        mock_delay=5,
    )

    assert status == 0
    mock_post.assert_called_once()
    args, kwargs = mock_post.call_args
    assert args[0] == "http://localhost:8000/mock"
    assert kwargs["json"] == {"delay_ms": 5}
    assert kwargs["stream"] is True
