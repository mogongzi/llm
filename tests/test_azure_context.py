from providers.azure import build_payload


def test_azure_context_injection_with_user_prefix():
    msgs = [{"role": "user", "content": "Hello"}]
    ctx = "<context>RAG</context>"
    body = build_payload(msgs, model="gpt-4o", context_content=ctx)

    assert body["stream"] is True
    assert body["model"] == "gpt-4o"
    # Expect system + user (with context prefixed)
    assert len(body["messages"]) == 2
    assert body["messages"][0]["role"] == "system"
    assert body["messages"][1]["role"] == "user"
    content = body["messages"][1]["content"]
    assert content.startswith(ctx)
    assert "Hello" in content


def test_azure_context_injection_without_user_inserts_new_message():
    msgs = [{"role": "system", "content": "Sys"}]
    ctx = "<context>A</context>"
    body = build_payload(msgs, model="gpt-4o", context_content=ctx)

    assert body["stream"] is True
    # Expect system then injected user context message
    assert len(body["messages"]) == 2
    assert body["messages"][0]["role"] == "system"
    assert body["messages"][1]["role"] == "user"
    assert body["messages"][1]["content"] == ctx

