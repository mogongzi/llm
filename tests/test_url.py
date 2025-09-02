import importlib.util
from pathlib import Path


def _load_llm_cli():
    p = Path(__file__).resolve().parents[1] / "llm-cli.py"
    spec = importlib.util.spec_from_file_location("llm_cli_module", str(p))
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)  # type: ignore[attr-defined]
    return mod


def test_to_mock_url_basic():
    mod = _load_llm_cli()
    f = mod.to_mock_url
    assert f("http://h:8000/invoke") == "http://h:8000/mock"
    assert f("http://h:8000") == "http://h:8000/mock"
    assert f("http://h:8000/") == "http://h:8000/mock"
    assert f("http://h:8000/anything") == "http://h:8000/anything/mock"
