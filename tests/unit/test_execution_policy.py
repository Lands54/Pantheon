from pathlib import Path

from gods.tools.execution import (
    _is_localhost_url,
    _validate_command,
)


def test_validate_command_allows_python():
    territory = Path.cwd()
    assert _validate_command(["python", "app.py"], territory) is None


def test_validate_command_blocks_plain_pip():
    territory = Path.cwd()
    err = _validate_command(["pip", "install", "requests"], territory)
    assert err is not None
    assert "virtualenv" in err
    assert "Suggested next step:" in err


def test_validate_command_allows_venv_pip():
    territory = Path.cwd()
    assert _validate_command([".venv/bin/pip", "install", "requests"], territory) is None


def test_validate_command_blocks_non_localhost_curl():
    territory = Path.cwd()
    err = _validate_command(["curl", "https://example.com"], territory)
    assert err is not None
    assert "localhost" in err
    assert "Suggested next step:" in err


def test_validate_command_allows_localhost_curl():
    territory = Path.cwd()
    assert _validate_command(["curl", "http://localhost:8000/health"], territory) is None


def test_is_localhost_url():
    assert _is_localhost_url("http://localhost:8000")
    assert _is_localhost_url("http://127.0.0.1:8000")
    assert not _is_localhost_url("https://openrouter.ai")
