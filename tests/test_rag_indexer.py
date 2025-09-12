from rag.indexer import NaiveIndexer


def test_build_index_and_search_basic(tmp_path):
    f1 = tmp_path / "a.txt"
    # Make f1 clearly dominant for both 'apple' and 'banana'
    f1.write_text("apple banana apple banana banana\n")
    f2 = tmp_path / "b.txt"
    f2.write_text("banana\n")

    idxr = NaiveIndexer()
    idx = idxr.build_index([str(tmp_path)])

    # Two files -> two chunks (given default large chunk size)
    assert idx["meta"]["total_chunks"] == 2
    assert idx["meta"]["vocab_size"] >= 2

    # 'apple' should match only a.txt
    res = idxr.search(idx, "apple", k=5)
    assert len(res) >= 1
    assert res[0]["path"].endswith("a.txt")
    assert res[0]["score"] > 0

    # 'banana' appears in both; ensure both files are returned
    res2 = idxr.search(idx, "banana", k=5)
    assert len(res2) >= 2
    paths2 = [r["path"] for r in res2]
    assert any(p.endswith("a.txt") for p in paths2)
    assert any(p.endswith("b.txt") for p in paths2)

    # Results have expected keys
    for r in res2[:2]:
        assert isinstance(r["start"], int) and isinstance(r["end"], int)
        assert isinstance(r["text"], str) and r["text"]


def test_chunking_respects_size_and_overlap(tmp_path):
    p = tmp_path / "long.txt"
    # ~132 chars text
    p.write_text(("lorem ipsum " * 11).strip())

    idxr = NaiveIndexer(chunk_size=50, overlap=10)
    idx = idxr.build_index([str(tmp_path)])

    # For one text ~132 chars, size=50, overlap=10 -> multiple chunks
    assert idx["meta"]["total_chunks"] >= 3
