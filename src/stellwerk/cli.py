from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import uvicorn


@dataclass(frozen=True)
class ServerConfig:
    host: str
    port: int
    reload: bool


def _read_toml_file(path: Path) -> dict[str, Any]:
    try:
        import tomllib  # py>=3.11
    except ModuleNotFoundError as e:  # pragma: no cover
        raise RuntimeError("tomllib is required (Python >= 3.11)") from e

    with path.open("rb") as f:
        data = tomllib.load(f)
    if not isinstance(data, dict):
        raise ValueError("Config file must contain a TOML table at top-level")
    return data


def load_server_config(config_path: str | None) -> ServerConfig:
    default = ServerConfig(host="127.0.0.1", port=8002, reload=False)

    path: Path | None
    explicit = False
    if config_path:
        path = Path(config_path)
        explicit = True
    else:
        path = Path("stellwerk.toml")
        if not path.exists():
            return default

    if not path.exists():
        if explicit:
            raise FileNotFoundError(f"Config file not found: {path}")
        return default

    raw = _read_toml_file(path)

    # Allow both flat keys and a [server] section.
    server: dict[str, Any] = {}
    for key in ("host", "port", "reload"):
        if key in raw:
            server[key] = raw[key]

    section = raw.get("server")
    if isinstance(section, dict):
        for key in ("host", "port", "reload"):
            if key in section:
                server[key] = section[key]

    host = server.get("host", default.host)
    port = server.get("port", default.port)
    reload = server.get("reload", default.reload)

    if not isinstance(host, str) or not host.strip():
        raise ValueError("server.host must be a non-empty string")
    if not isinstance(port, int) or not (1 <= port <= 65535):
        raise ValueError("server.port must be an integer between 1 and 65535")
    if not isinstance(reload, bool):
        raise ValueError("server.reload must be a boolean")

    return ServerConfig(host=host, port=port, reload=reload)


def _build_parser(config: ServerConfig, config_path: str | None) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="stellwerk", description="Stellwerk – Ziele auf Schienen planen"
    )
    parser.add_argument(
        "--config",
        default=config_path,
        help="Pfad zu stellwerk.toml (Default: ./stellwerk.toml falls vorhanden)",
    )
    parser.add_argument("--host", default=config.host)
    parser.add_argument("--port", type=int, default=config.port)
    parser.add_argument(
        "--reload",
        action=argparse.BooleanOptionalAction,
        default=config.reload,
        help="Auto-reload (dev). Flags: --reload / --no-reload",
    )
    return parser


def main() -> None:
    pre = argparse.ArgumentParser(add_help=False)
    pre.add_argument("--config", default=None)
    pre_args, _ = pre.parse_known_args()

    try:
        config = load_server_config(pre_args.config)
    except Exception as e:
        print(f"[stellwerk] config error: {e}", file=sys.stderr)
        raise SystemExit(2) from e

    parser = _build_parser(config, pre_args.config)
    args = parser.parse_args()

    uvicorn.run("stellwerk.app:app", host=args.host, port=args.port, reload=args.reload)
