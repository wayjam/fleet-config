"""`fleet image <host>` and `fleet download-image <host>`.

Unified commands that replace the old ``image build``, ``image remote``,
and ``image download`` subcommands.
"""

import shlex
from pathlib import Path

from builder import (
    apply_builder_overrides,
    builder_config,
    builder_spec,
    nix_ssh_env,
    remote_nix_expr,
    remote_repo_path,
    remote_shell,
    scp_args,
    sync_to_builder,
)
from common import repo_path, run


def cmd_image(args, config):
    """Build a disko image for *host*.

    Without ``--builder``: local ``nix build``.
    With ``--builder``: remote build (KVM if available, ``--no-kvm`` to force
    non-KVM).
    """
    if not args.builder:
        run(["nix", "build", f".#packages.x86_64-linux.{args.host}"])
        return

    builder = apply_builder_overrides(builder_config(config, args.builder), args)
    if args.no_kvm:
        builder["use_kvm"] = False

    if builder["use_kvm"]:
        env = nix_ssh_env(builder)
        run(
            [
                "nix",
                "build",
                "--builders",
                builder_spec(builder, require_kvm=True),
                "--option",
                "builders-use-substitutes",
                "true",
                "--max-jobs",
                "0",
                f".#packages.x86_64-linux.{args.host}",
            ],
            env=env,
        )
        return

    # Non-KVM remote build via diskoImagesScript.
    sync_to_builder(config, builder)
    repos = config.get("repos", {})
    public_name = repos.get("public_name", "fleet-config")
    inventory_name = repos.get("inventory_name", "fleet-inventory")
    remote_root = builder["remote_root"]
    remote_nix = remote_nix_expr(builder)
    paths = config.get("paths", {})
    node_age_key = paths.get("node_age_key", "local/node-age.txt")
    node_age_key_arg = ""
    if node_age_key and repo_path(node_age_key).exists():
        node_age_key_arg = (
            " --post-format-files "
            + shlex.quote(remote_repo_path(config, node_age_key, builder))
            + " /etc/sops/age/key.txt"
        )
    script = (
        f"cd {shlex.quote(remote_root + '/' + inventory_name)}; "
        f"remote_nix={remote_nix}; "
        f"script=$($remote_nix build --print-out-paths "
        f"--override-input dotfiles path:{shlex.quote(remote_root + '/' + public_name)} "
        f".#nixosConfigurations.{shlex.quote(args.host)}.config.system.build.diskoImagesScript); "
        f"out_dir={shlex.quote(remote_root + '/disko-' + args.host)}; "
        f"mkdir -p \"$out_dir\"; "
        f"cd \"$out_dir\"; "
        f"\"$script\" --build-memory {int(builder['memory'])}{node_age_key_arg} & "
        "pid=$!; "
        "echo \"[fleet] image build started on builder (pid=$pid)\"; "
        "(while kill -0 \"$pid\" 2>/dev/null; do "
        "sleep 30; "
        "echo \"[fleet] image build still running on builder (pid=$pid)\"; "
        "done) & "
        "heartbeat=$!; "
        "set +e; "
        "wait \"$pid\"; "
        "fleet_status=$?; "
        "kill \"$heartbeat\" 2>/dev/null; "
        "wait \"$heartbeat\" 2>/dev/null; "
        "exit \"$fleet_status\""
    )
    remote_shell(builder, script)


def cmd_download_image(args, config):
    """Download a remote-built disko image."""
    builder = apply_builder_overrides(builder_config(config, args.builder), args)
    remote_path = args.remote_path or f"{builder['remote_root']}/disko-{args.host}/main.raw"
    output_path = Path(args.output)
    if output_path.parent != Path("."):
        output_path.parent.mkdir(parents=True, exist_ok=True)
    run([*scp_args(builder), f"{builder['alias']}:{remote_path}", str(output_path)])
