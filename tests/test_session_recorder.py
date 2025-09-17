from chat.recorder import SessionRecorder


class DummyResult:
    def __init__(self, text: str, tokens: int, cost: float, model: str | None = None):
        self.text = text
        self.tokens = tokens
        self.cost = cost
        self.model_name = model


def test_session_recorder_json_and_markdown(tmp_path):
    rec = SessionRecorder(base_dir=tmp_path)
    rec.start(provider_name="bedrock", url="http://127.0.0.1:8000/invoke", max_tokens=4096, default_thinking=False, default_tools=False)

    # Turn 1: no tools
    t1 = rec.start_turn("Hello", {"base_context_status": "0 files", "rag_enabled": False})
    r1 = DummyResult("Hi there!\n\n", 30, 0.00123, model="anthropic--claude-4-sonnet")
    rec.record_first_result(t1, model=r1.model_name, tokens=r1.tokens, cost=r1.cost, text=r1.text)

    # Turn 2: with tools and follow-up
    t2 = rec.start_turn("Calculate 2+2", {"base_context_status": "0 files", "rag_enabled": False})
    rf = DummyResult("Using tool...\n", 10, 0.0005, model="gpt-5")
    rec.record_first_result(t2, model=rf.model_name, tokens=rf.tokens, cost=rf.cost, text=rf.text)
    tool_calls = [{
        "tool_call": {"id": "toolu_1", "name": "calculate", "input": {"expression": "2+2"}},
        "result": "4"
    }]
    rec.record_tool_calls(t2, tool_calls)
    r2 = DummyResult("Answer: 4\n", 8, 0.0003, model="gpt-5")
    rec.record_followup_result(t2, model=r2.model_name, tokens=r2.tokens, cost=r2.cost, text=r2.text)

    # Save and export
    json_path = rec.save_json()
    md_path = rec.export_markdown()

    # Verify files exist
    from pathlib import Path
    assert Path(json_path).exists()
    assert Path(md_path).exists()

    # Load JSON and verify structure
    import json
    obj = json.loads(Path(json_path).read_text(encoding="utf-8"))
    assert obj["version"] == 1
    assert obj["provider"]["name"] == "bedrock"
    assert obj["totals"]["turns"] == 2
    assert len(obj["turns"]) == 2
    # Totals should sum tokens/costs from both requests
    assert obj["totals"]["tokens"] == 30 + 10 + 8

    # Markdown contains key sections
    md = Path(md_path).read_text(encoding="utf-8")
    assert "# Chat Session" in md
    assert "## Turn 1" in md and "## Turn 2" in md
    assert "### Tools" in md  # For turn 2
    assert "calculate" in md and "4" in md

