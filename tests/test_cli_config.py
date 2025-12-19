from __future__ import annotations

import pytest

from stellwerk.cli import load_server_config


def test_load_server_config_defaults_without_file(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    cfg = load_server_config(None)
    assert cfg.host == "127.0.0.1"
    assert cfg.port == 8002
    assert cfg.reload is False


def test_load_server_config_reads_server_section(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "stellwerk.toml").write_text(
        """
[server]
host = "0.0.0.0"
port = 8123
reload = true
""".lstrip(),
        encoding="utf-8",
    )

    cfg = load_server_config(None)
    assert cfg.host == "0.0.0.0"
    assert cfg.port == 8123
    assert cfg.reload is True


def test_load_server_config_flat_keys_override_defaults(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "stellwerk.toml").write_text(
        """
host = "127.0.0.1"
port = 9000
reload = false
""".lstrip(),
        encoding="utf-8",
    )

    cfg = load_server_config(None)
    assert cfg.host == "127.0.0.1"
    assert cfg.port == 9000
    assert cfg.reload is False


def test_load_server_config_explicit_missing_file_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        load_server_config(str(tmp_path / "missing.toml"))


@pytest.mark.parametrize(
    "toml_text",
    [
        "[server]\nport = 0\n",
        "[server]\nport = 70000\n",
        '[server]\nport = "8002"\n',
        '[server]\nhost = ""\n',
        "[server]\nreload = 1\n",
    ],
)
def test_load_server_config_invalid_values_raise(monkeypatch, tmp_path, toml_text):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "stellwerk.toml").write_text(toml_text, encoding="utf-8")

    with pytest.raises(ValueError):
        load_server_config(None)
