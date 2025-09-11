import os
from util.simple_pt_input import _is_complete_at_command


def test_is_complete_at_command(tmp_path, monkeypatch):
    # Create files and dirs in tmp
    (tmp_path / "sub").mkdir()
    (tmp_path / "note.md").write_text("hi")

    monkeypatch.chdir(tmp_path)

    # Not complete cases
    assert _is_complete_at_command("@", None) is False
    assert _is_complete_at_command("@sub/", None) is False

    # Complete readable file
    assert _is_complete_at_command("@note.md", None) is True

    # Absolute path also works
    abs_file = tmp_path / "note.md"
    assert _is_complete_at_command(f"@{abs_file}", None) is True
