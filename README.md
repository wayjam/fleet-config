# Fleet Config

Reusable Nix modules, scripts, templates, and documentation for WayJam's host
fleet.

This repository is the public configuration layer. It should contain shared
logic only. Real host inventory, public IP addresses, private domains, provider
notes, deployment targets, and encrypted secrets belong in the private
`fleet-inventory` repository.

This README is the repository entry point. It explains what this repo provides,
how to enter the development environment, and where to find operational
documentation. Fleet design details and host workflows live under `docs/`.

## Repository Layout

```text
fleet-config/
  README.md                         # Repository overview
  flake.nix                         # Public flake outputs
  Justfile                          # Local maintenance commands
  docs/                             # Fleet operation documentation
    README.md                       # Design overview and docs index
    just-recipes.md                 # Private inventory Justfile command reference
    setup-host.md                   # New host setup flow
    image-host-checklist.md         # Raw image/dd host discovery and boot checklist
    infect-host-flow.md             # Low-memory VPS conversion with nixos-infect
    host-troubleshooting.md         # Inventory and deployment troubleshooting
  modules/
    nixos/                          # NixOS host profiles and modules
    shared/                         # Modules shared by NixOS and system-manager
    darwin/                         # nix-darwin modules
  templates/fleet-inventory/        # Sanitized private inventory skeleton
  tools/                            # Helper CLI scripts exposed by the flake
  vars/                             # Public default variables
```

Expected local workspace:

```text
~/deploy/
  fleet-config/                     # This public repository
  fleet-inventory/                  # Private repository with real hosts
```

## What This Repo Provides

- Public NixOS and system-manager modules for KVM hosts, LXC hosts, proxy
  services, monitoring, Caddy, WireGuard, SSH, firewall, fail2ban, and tuning.
- Helper apps such as `fleet` and `secret-gen`.
- `lib.hostInventory`, used by the private inventory to generate host outputs.
- A development shell with the tools needed to work on this repository.
- A sanitized `templates/fleet-inventory` skeleton for the private repo.

This flake also still contains local Darwin and NixOS configurations for
personal machines.

## Private Inventory

Create a private inventory from the sanitized template:

```shell
cp -R templates/fleet-inventory ../fleet-inventory
```

Then update the private repo with real hosts, deployment targets, sops
recipients, and encrypted secrets.

The private inventory should import this public repo as `inputs.dotfiles` and
use the module outputs above. Do not copy public modules into the private repo.

## Documentation

- [docs/README.md](./docs/README.md): fleet design, directory conventions, and
  operating model.
- [docs/setup-host.md](./docs/setup-host.md): new host setup flow and common
  installation scenarios.
- [docs/host-troubleshooting.md](./docs/host-troubleshooting.md): inventory,
  flake lock, remote builder, and deployment troubleshooting.
- [templates/fleet-inventory/README.md](./templates/fleet-inventory/README.md):
  private inventory template notes.

## Prerequisites

Install Nix:

```shell
curl --proto '=https' --tlsv1.2 -sSf -L https://install.determinate.systems/nix | sh -s -- install
```

Optional Homebrew on macOS:

```shell
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
```

Install `just`:

```shell
brew install just
```

Enter the development shell:

```shell
nix develop
```

## Common Commands

List local recipes:

```shell
just
```

Format this repository:

```shell
just fmt
```

Update flake inputs:

```shell
just up
```

Build and switch a macOS host:

```shell
just darwin-build <host>
```

Build a NixOS host configuration:

```shell
just nixos-debug <host>
```

Most real host operations are run from the private `fleet-inventory`
repository, not from this public repository.
