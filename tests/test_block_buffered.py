from render.block_buffered import BlockBuffer


def test_paragraph_flush():
    b = BlockBuffer()
    out = b.feed("Hello world\n\nNext")
    assert out == ["Hello world\n\n"]
    rest = b.flush_remaining()
    assert rest == "Next"


def test_code_fence_flush_spanning_chunks():
    b = BlockBuffer()
    out1 = b.feed("```python\nprint('hi')\n")
    assert out1 == []  # not closed yet
    out2 = b.feed("```\nThen para\n\n")
    # First the code block, then paragraph
    assert out2[0].startswith("```python\n") and out2[0].endswith("```\n")
    assert out2[1] == "Then para\n\n"

