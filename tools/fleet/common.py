"""Shared helpers: config loading, subprocess wrappers, small utilities."""

import shlex
import subprocess
import sys
from pathlib import Path

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover
    print("error: Python 3.11+ is required for tomllib", file=sys.stderr)
    sys.exit(127)


DEFAULT_CONFIG = {
    "paths": {
        "ssh_config": "local/ssh-config",
        "remote_root": "/root",
        "secret_key_dir": "local/keys",
        "node_age_key": "local/node-age.txt",
    },
    "builder": {
        "default": "",
        "ssh_key": "-",
        "memory": 768,
        "use_kvm": True,
        "remote_nix": "auto",
    },
    "builders": {},
    "repos": {
        "public_name": "fleet-config",
        "inventory_name": "fleet-inventory",
    },
}


def deep_merge(base, override):
    result = dict(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def load_toml(path):
    if not path.exists():
        return {}
    with path.open("rb") as f:
        return tomllib.load(f)


def repo_root():
    return Path.cwd()


def load_config():
    root = repo_root()
    config = DEFAULT_CONFIG
    config = deep_merge(config, load_toml(root / "fleet.toml"))
    config = deep_merge(config, load_toml(root / "local" / "fleet.toml"))
    return config


def repo_path(value):
    path = Path(value).expanduser()
    if path.is_absolute():
        return path
    return repo_root() / path


def remote_repo_path(config, value, builder):
    path = Path(value).expanduser()
    if path.is_absolute():
        try:
            rel = path.relative_to(repo_root())
        except ValueError:
            return str(path)
    else:
        rel = path
    repos = config.get("repos", {})
    inventory_name = repos.get("inventory_name", "fleet-inventory")
    return str(Path(builder["remote_root"]) / inventory_name / rel)


def run(argv, *, env=None, cwd=None):
    printable = " ".join(shlex.quote(str(a)) for a in argv)
    print(f"+ {printable}", file=sys.stderr)
    subprocess.run([str(a) for a in argv], env=env, cwd=cwd, check=True)


def capture(argv, *, env=None, cwd=None):
    return subprocess.check_output([str(a) for a in argv], env=env, cwd=cwd, text=True)


def die(message, code=2):
    print(f"error: {message}", file=sys.stderr)
    sys.exit(code)


def parse_bool(value):
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        lowered = value.lower()
        if lowered in {"1", "true", "yes", "on"}:
            return True
        if lowered in {"0", "false", "no", "off"}:
            return False
    return bool(value)
