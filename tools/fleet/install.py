"""`fleet install` — nixos-anywhere fresh install."""

from common import die, run
from nix import nixos_anywhere_cmd
from target import normalize_ssh_target


def cmd_install(args, _config):
    user, host, port, _ = normalize_ssh_target(
        args.ssh_target, default_port=22, default_user="root"
    )
    cmd = nixos_anywhere_cmd()
    if port and port != 22:
        cmd.extend(["--ssh-option", f"Port={port}"])
    if args.kexec_syscall:
        cmd.extend(["--kexec-extra-flags", "--kexec-syscall"])
    cmd.extend(["--flake", f".#{args.host}", f"{user}@{host}"])
    run(cmd)
