"""Shared SSH-target transport helpers.

Used by `infect` and `install` to normalise `user@host:port` addresses and
execute scripts / upload files over SSH.
"""

import base64
import shlex
import subprocess
import sys
from pathlib import Path

from common import die


def normalize_ssh_target(value, default_port=22, default_user="root"):
    """Parse ``user@host:port`` into (user, host, port, raw_port).

    If *default_port* is set and the target does not include ``:port``, the
    default is used.  *raw_port* is the original port string (for error
    messages or special handling).
    """
    user = default_user
    host = value
    port = default_port
    raw_port = None

    if ":" in value.rsplit("@", 1)[-1]:
        # last segment contains a colon → port
        idx = value.rfind(":")
        port_str = value[idx + 1:]
        host = value[:idx]
        try:
            port = int(port_str)
        except ValueError:
            die(f"invalid port in ssh target: {port_str}")
        raw_port = port_str

    if "@" in host:
        user, host = host.split("@", 1)
        if not user or not host:
            die(f"invalid ssh target: {value}")

    return user, host, port, raw_port


def ssh_base(user, host, port, *, timeout=30):
    """Return the base SSH command-line for ``user@host:port``."""
    ssh_bin = "/usr/bin/ssh" if Path("/usr/bin/ssh").exists() else "ssh"
    return [
        ssh_bin,
        "-o", "BatchMode=yes",
        "-o", "StrictHostKeyChecking=accept-new",
        "-o", f"ConnectTimeout={int(timeout)}",
        "-o", "ConnectionAttempts=1",
        "-o", "ServerAliveInterval=15",
        "-o", "ServerAliveCountMax=4",
        "-p", str(port),
        f"{user}@{host}",
    ]


def target_run(user, host, port, script, *, timeout=30, input_text=None, capture_output=False):
    """Execute *script* on the target via SSH."""
    argv = [*ssh_base(user, host, port, timeout=timeout), "set -eu; " + script]
    printable = " ".join(shlex.quote(str(a)) for a in argv)
    print(f"+ {printable}", file=sys.stderr)
    if capture_output:
        return subprocess.check_output(argv, input=input_text, text=True)
    subprocess.run(argv, input=input_text, text=True, check=True)
    return ""


def target_upload_text(user, host, port, path, text, *, mode="0644", timeout=30):
    """Upload *text* (base64-encoded) to *path* on the target."""
    encoded = base64.b64encode(text.encode()).decode()
    script = (
        f"install -d -m 0755 {shlex.quote(str(Path(path).parent))}; "
        f"base64 -d > {shlex.quote(path)}; "
        f"chmod {shlex.quote(mode)} {shlex.quote(path)}"
    )
    target_run(user, host, port, script, timeout=timeout, input_text=encoded)


def target_read_text(user, host, port, path, *, timeout=30):
    """Read *path* contents from the target."""
    return target_run(user, host, port, f"cat {shlex.quote(path)}", timeout=timeout, capture_output=True)
