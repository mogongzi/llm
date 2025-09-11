import os
from util.at_completer import AtCommandCompleter


def test_at_completions_basic(tmp_path, monkeypatch):
    # Prepare temp dir with files
    (tmp_path / "dir").mkdir()
    (tmp_path / "file.txt").write_text("x")
    (tmp_path / ".hidden.txt").write_text("y")

    monkeypatch.chdir(tmp_path)

    comp = AtCommandCompleter()

    # Complete current directory with just '@'
    completions = comp._get_path_completions("")
    texts = [c.text for c in completions]
    assert "@dir/" in texts
    assert "@file.txt" in texts
    # Hidden file should not appear by default
    assert all("hidden" not in t for t in texts)

    # Partial filter
    completions = comp._get_path_completions("fi")
    texts = [c.text for c in completions]
    assert texts == ["@file.txt"]

    # Completing inside a directory
    (tmp_path / "dir" / "nested.md").write_text("z")
    completions = comp._get_path_completions("dir/")
    texts = [c.text for c in completions]
    assert "@dir/nested.md" in texts

