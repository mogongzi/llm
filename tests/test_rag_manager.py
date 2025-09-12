from rag.manager import RAGManager


def test_rag_manager_index_search_and_format(tmp_path, monkeypatch):
    # Use a temp index path
    idx_path = tmp_path / ".rag_index.json"
    rm = RAGManager(index_path=str(idx_path))

    # Create a simple doc
    doc = tmp_path / "doc.txt"
    doc.write_text("cloud azure bedrock cloud\n")

    # Index
    idx = rm.index([str(tmp_path)], index_type="naive")
    st = rm.status()
    assert st["indexed"] is True
    assert st["type"] == "naive"
    assert st["files"] >= 1 and st["chunks"] >= 1

    # Search
    res = rm.search("cloud", k=3)
    assert res and any(r["path"].endswith("doc.txt") for r in res)

    # Format context
    ctx = rm.format_context(res[:1])
    assert ctx.startswith("<context>") and ctx.endswith("</context>")
    assert "<chunk src=\"" in ctx
    assert "cloud" in ctx

    # Clear and verify
    rm.clear()
    st2 = rm.status()
    assert st2["indexed"] is False

