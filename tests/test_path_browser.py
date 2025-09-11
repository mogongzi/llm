import os
from util.path_browser import PathBrowser


def test_parse_and_list_directory(tmp_path, monkeypatch):
    # Create temp structure
    d = tmp_path / "subdir"
    d.mkdir()
    f = tmp_path / "a.txt"
    f.write_text("hello world")
    hidden = tmp_path / ".hidden"
    hidden.write_text("secret")

    pb = PathBrowser(show_hidden=False)

    # Parsing explicit directory listing
    path, is_dir = pb.parse_at_command(f"@{tmp_path}/")
    assert is_dir is True
    assert os.path.samefile(path, str(tmp_path))

    # Parsing explicit file path
    fpath, is_dir = pb.parse_at_command(f"@{f}")
    assert is_dir is False
    assert os.path.samefile(fpath, str(f))

    # List directory: hidden excluded
    items = pb.list_directory(str(tmp_path))
    names = {it.name for it in items}
    assert "a.txt" in names and "subdir" in names
    assert ".hidden" not in names

    # Validate file item fields
    file_item = next(it for it in items if it.name == "a.txt")
    assert file_item.is_dir is False
    assert file_item.size and file_item.size == len("hello world")


def test_format_directory_listing_and_validation(tmp_path):
    # Build structure
    (tmp_path / "dir").mkdir()
    file_ok = tmp_path / "ok.txt"
    file_ok.write_text("ok")
    file_bad = tmp_path / "bad.bin"
    file_bad.write_bytes(b"\xff\xfe\xfa")  # invalid UTF-8

    pb = PathBrowser()

    # Fake context manager with the ok file in context
    class Ctx:
        def __init__(self, p):
            self.contexts = {str(p)}

        def get_status_summary(self):
            return "1 file"

    ctx = Ctx(file_ok)

    items = pb.list_directory(str(tmp_path))

    # Terminal style
    out_term = pb.format_directory_listing(str(tmp_path), items, context_manager=ctx, style="terminal")
    assert "dir/" in out_term
    assert "ok.txt" in out_term
    assert "Use @ commands" in out_term
    assert "✓" in out_term  # mark for context

    # Icon style
    out_icon = pb.format_directory_listing(str(tmp_path), items, context_manager=ctx, style="icons")
    # Do not rely on emoji; ensure names appear in output
    assert "dir/" in out_icon
    assert "ok.txt" in out_icon

    # Validate files for context
    is_valid, msg = pb.validate_file_for_context(str(file_ok))
    assert is_valid is True and msg == ""

    is_valid, msg = pb.validate_file_for_context(str(tmp_path / "dir"))
    assert is_valid is False and "not a file" in msg

    is_valid, msg = pb.validate_file_for_context(str(tmp_path / "missing.txt"))
    assert is_valid is False and "not found" in msg

    is_valid, msg = pb.validate_file_for_context(str(file_bad))
    assert is_valid is False and "UTF-8" in msg

    # Relative path shortening
    cwd = os.getcwd()
    try:
        os.chdir(str(tmp_path))
        rel = pb.get_relative_path(str(file_ok))
        assert rel == "ok.txt"
    finally:
        os.chdir(cwd)
