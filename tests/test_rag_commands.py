from unittest.mock import Mock

from util.command_helpers import handle_special_commands


def make_rag_status(indexed=True):
    return {
        "enabled": False,
        "type": "naive",
        "files": 1 if indexed else 0,
        "chunks": 2 if indexed else 0,
        "vocab": 3 if indexed else 0,
        "chunk_size": 1000,
        "overlap": 200,
        "k": 3,
        "char_cap": 6000,
        "indexed": indexed,
    }


def test_rag_status_and_toggle():
    console = Mock()
    conv = Mock()
    rag = Mock()
    rag.status.return_value = make_rag_status(indexed=False)

    # /rag status
    assert handle_special_commands("/rag status", conv, console, None, None, rag) is True
    assert console.print.called

    # /rag on
    console.reset_mock()
    rag.enabled = False
    assert handle_special_commands("/rag on", conv, console, None, None, rag) is True
    assert rag.enabled is True
    assert console.print.called

    # /rag off
    console.reset_mock()
    assert handle_special_commands("/rag off", conv, console, None, None, rag) is True
    assert rag.enabled is False
    assert console.print.called


def test_rag_index_and_search(tmp_path):
    console = Mock()
    conv = Mock()
    rag = Mock()
    rag.status.return_value = make_rag_status(indexed=True)
    rag.search.return_value = [
        {"path": "/x/doc.txt", "start": 0, "end": 10, "text": "hello world"}
    ]

    # /rag index naive <path>
    path = str(tmp_path)
    assert handle_special_commands(f"/rag index naive {path}", conv, console, None, None, rag) is True
    rag.index.assert_called()
    args, kwargs = rag.index.call_args
    assert args[0] == [path]
    assert kwargs.get("index_type") == "naive"

    # /rag search query 5
    console.reset_mock()
    assert handle_special_commands("/rag search hello 5", conv, console, None, None, rag) is True
    rag.search.assert_called_with("hello", k=5)
    # Expect at least one print for header and one for result
    assert console.print.call_count >= 2

    # /rag clear
    console.reset_mock()
    assert handle_special_commands("/rag clear", conv, console, None, None, rag) is True
    rag.clear.assert_called_once()
    assert console.print.called

