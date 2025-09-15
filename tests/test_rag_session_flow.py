from chat.session import ChatSession


class DummyProvider:
    def __init__(self):
        self.calls = []
        self.last_kwargs = None

    def build_payload(self, messages, **kwargs):
        # capture kwargs including context_content
        self.last_kwargs = kwargs
        self.calls.append((messages, kwargs))
        # return any dict; session only forwards this to stream func
        return {"messages": messages, "probe": kwargs.get("context_content")}

    def map_events(self, lines):
        return lines


from streaming_client import StreamResult

def _stream_stub(url, payload, **kwargs):
    # emulate streaming return signature for new API
    return StreamResult(text="ok", tokens=0, cost=0.0, tool_calls=[])


def test_session_passes_rag_context_to_provider(monkeypatch):
    provider = DummyProvider()
    session = ChatSession(
        url="http://localhost/invoke",
        provider=provider,
        max_tokens=128,
        timeout=1.0,
        tool_executor=None,
        context_manager=None,
        rag_manager=None,
        provider_name="bedrock",
    )

    # Enable rag with mocked manager
    class RM:
        enabled = True
        default_k = 3

        def search_and_format(self, query, k):
            # assert query is last user content
            assert query == "hello world"
            assert k == 3
            return "<context>R</context>"

    session.rag_manager = RM()

    # Mock the streaming client to avoid actual network calls
    class MockStreamingClient:
        def send_message(self, url, payload, **kwargs):
            return _stream_stub(url, payload, **kwargs)
    
    session.streaming_client = MockStreamingClient()
    
    history = [{"role": "user", "content": "hello world"}]
    session.send_message(history, use_thinking=False, tools_enabled=False, available_tools=None)

    # Provider must have received context_content
    assert provider.last_kwargs is not None
    assert provider.last_kwargs.get("context_content") == "<context>R</context>"


def test_session_without_rag_has_no_context_content():
    provider = DummyProvider()
    session = ChatSession(
        url="http://localhost/invoke",
        provider=provider,
        max_tokens=128,
        timeout=1.0,
        tool_executor=None,
        context_manager=None,
        rag_manager=None,
        provider_name="bedrock",
    )

    # Mock the streaming client to avoid actual network calls
    class MockStreamingClient:
        def send_message(self, url, payload, **kwargs):
            return _stream_stub(url, payload, **kwargs)
    
    session.streaming_client = MockStreamingClient()

    history = [{"role": "user", "content": "hello"}]
    session.send_message(history, use_thinking=False, tools_enabled=False, available_tools=None)
    assert provider.last_kwargs is not None
    assert provider.last_kwargs.get("context_content") is None

