"""`fleet deploy <target>` and `fleet deploy-all`.

With ``--builder``: sync the local worktree to the remote builder and apply
from there (merges the old ``deploy-remote`` recipe).
"""

import shlex

from builder import (
    apply_builder_overrides,
    builder_config,
    remote_nix_expr,
    remote_shell,
    sync_to_builder,
)
from common import run
from nix import colmena_cmd


def cmd_deploy(args, config):
    if args.builder:
        builder = apply_builder_overrides(builder_config(config, args.builder), args)
        sync_to_builder(config, builder)
        repos = config.get("repos", {})
        public_name = repos.get("public_name", "fleet-config")
        inventory_name = repos.get("inventory_name", "fleet-inventory")
        remote_root = builder["remote_root"]
        remote_nix = remote_nix_expr(builder)
        public_path = shlex.quote(remote_root + "/" + public_name)
        script = (
            f"cd {shlex.quote(remote_root + '/' + inventory_name)}; "
            f"remote_nix={remote_nix}; "
            f"$remote_nix flake lock --override-input dotfiles path:{public_path}; "
            f"$remote_nix run .#colmena -- --impure --config flake.nix apply --on {shlex.quote(args.target)}"
        )
        remote_shell(builder, script)
    else:
        run([*colmena_cmd(), "apply", "--on", args.target])


def cmd_deploy_all(args, config):
    if args.builder:
        builder = apply_builder_overrides(builder_config(config, args.builder), args)
        sync_to_builder(config, builder)
        repos = config.get("repos", {})
        public_name = repos.get("public_name", "fleet-config")
        inventory_name = repos.get("inventory_name", "fleet-inventory")
        remote_root = builder["remote_root"]
        remote_nix = remote_nix_expr(builder)
        public_path = shlex.quote(remote_root + "/" + public_name)
        script = (
            f"cd {shlex.quote(remote_root + '/' + inventory_name)}; "
            f"remote_nix={remote_nix}; "
            f"$remote_nix flake lock --override-input dotfiles path:{public_path}; "
            f"$remote_nix run .#colmena -- --impure --config flake.nix apply"
        )
        remote_shell(builder, script)
    else:
        run([*colmena_cmd(), "apply"])
