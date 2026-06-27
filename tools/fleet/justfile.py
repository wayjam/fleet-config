"""`fleet justfile render` — emit the Justfile template (source of truth).

The generated Justfile in fleet-inventory is produced by `just update-justfile`,
which runs `fleet justfile render --output Justfile`.
"""

from pathlib import Path

JUSTFILE_TEMPLATE = """set positional-arguments := true

default:
  @just --list

# Format all Nix files.
fmt:
  nix run .#fleet -- fmt

# Run flake checks (--show-trace).
check:
  nix run .#fleet -- check

# Evaluate all fleet outputs (list node names).
eval:
  nix run .#fleet -- eval

# Build a host system closure — `just build <host> [builder=<x>] [dry-run=true]`
build host builder="" dry-run="false":
  nix run .#fleet -- build {{host}} --builder {{builder}} --dry-run {{dry-run}}

# Check SSH + nix connectivity to a remote builder — `just builder-ping [<name>]`
builder-ping builder="":
  nix run .#fleet -- builder-ping {{builder}}

# Deploy to a host (with --builder: sync worktree & apply remotely) — `just deploy <target> [builder=<x>]`
deploy target builder="":
  nix run .#fleet -- deploy {{target}} --builder {{builder}}

# Deploy to all Colmena hosts — `just deploy-all [builder=<x>]`
deploy-all builder="":
  nix run .#fleet -- deploy-all --builder {{builder}}

# Build a disko image (local/remote/--no-kvm) — `just image <host> [builder=<x>] [no-kvm=true]`
image host builder="" no-kvm="false":
  nix run .#fleet -- image {{host}} --builder {{builder}} --no-kvm {{no-kvm}}

# Download remote-built disko image via SCP — `just download-image <host> builder=<x> [output=path]`
download-image host builder="" output="":
  nix run .#fleet -- download-image {{host}} --builder {{builder}} --output {{output}}

#   just infect <host> [ssh-target=user@ip:22] [builder=<x>]
# Convert Debian/Ubuntu → NixOS with nixos-infect (multi-stage pipeline).
infect host ssh-target="root@localhost:22" builder="":
  nix run .#fleet -- infect {{host}} --ssh-target {{ssh-target}} --builder {{builder}}

#   just install <host> ssh-target=root@ip:22 [kexec-syscall=true]
# Fresh NixOS install via nixos-anywhere.
install host ssh-target="root@localhost:22" kexec-syscall="false":
  nix run .#fleet -- install {{host}} --ssh-target {{ssh-target}} --kexec-syscall {{kexec-syscall}}

# Switch a system-manager LXC or existing Linux host — `just lxc-switch <host>`
lxc-switch host:
  nix run .#fleet -- lxc-switch {{host}}

# Print allowed TCP & UDP firewall ports — `just ports <host>`
ports host:
  nix run .#fleet -- ports {{host}}

# Show client proxy/VPN profiles (xray/hy2/wireguard) — `just profile <host> [kind=xray]`
profile host kind="":
  nix run .#fleet -- profile {{host}} --kind {{kind}}

#   just secret uuid | password | hex | age | age-file <n> | wireguard | ssh <n> | xray-reality | proxy
# Generate secrets — runs `fleet secret <args>` (see just --help for sub-commands).
secret +args:
  nix run .#fleet -- secret {{args}}

# Regenerate this Justfile from the fleet template (source of truth).
update-justfile:
  nix run --refresh .#fleet -- justfile render --output Justfile
"""


def cmd_justfile_render(args, _config):
    if args.output == "-":
        print(JUSTFILE_TEMPLATE, end="")
        return
    Path(args.output).write_text(JUSTFILE_TEMPLATE)
    print(f"wrote {args.output}")
