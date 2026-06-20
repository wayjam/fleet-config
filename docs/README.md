# Fleet Configuration Docs

This directory documents the host fleet layout and the normal operating flow.
The public `fleet-config` repository provides reusable Nix modules, scripts,
templates, and documentation. Real host inventory belongs in the private
`fleet-inventory` repository.

Use the repository root [README.md](../README.md) for repository setup,
development commands, and a high-level map of public outputs. Use this document
for the fleet operating model: how the public repo, private inventory, host
files, secrets, and deployment tools fit together.

## Design

Keep shared logic public and host-specific data private.

- `fleet-config` is the public module layer. It defines reusable NixOS and
  system-manager modules, default variables, scripts, and sanitized templates.
- `fleet-inventory` is the private deployment layer. It contains real hosts,
  IP addresses, SSH ports, domains, provider notes, encrypted secrets, and
  Colmena deployment targets.
- `templates/fleet-inventory` is a sanitized skeleton for the private
  inventory. Copy from it when creating a new private inventory or a new host.

The public repository should not contain real public IP addresses, real
hostnames, private domains, provider-specific notes, xray/hysteria values, or
secret material.

## Directory Layout

Expected workspace layout:

```text
~/deploy/
  fleet-config/                  # Public repo: shared modules, scripts, docs, templates
    docs/                         # Public operational documentation
      README.md                   # Design overview and documentation index
      just-recipes.md             # Private inventory Justfile command reference
      setup-host.md               # New host setup flow and scenarios
      image-host-checklist.md      # Raw image/dd host discovery and boot checklist
      host-troubleshooting.md     # Inventory and deployment troubleshooting
    modules/                      # Reusable NixOS and system-manager modules
    templates/fleet-inventory/    # Sanitized private inventory skeleton
    vars/                         # Public default variables

  fleet-inventory/                # Private repo: real hosts, targets, domains, secrets
    flake.nix                     # Private flake wiring public modules and tools
    hive.nix                      # Colmena hive generated or maintained by inventory
    hosts/
      default.nix                 # Host index and deployment metadata
      <host-name>/default.nix     # Per-host NixOS configuration
    secrets/                      # Encrypted sops files tracked by the private repo
```

Important paths:

- `fleet-config/modules/nixos`: shared NixOS modules.
- `fleet-config/modules/system-manager`: shared system-manager modules for
  non-NixOS LXC hosts with Nix installed.
- `fleet-config/templates/fleet-inventory`: sanitized private inventory
  skeleton.
- `fleet-inventory/hosts/default.nix`: the private host index used to generate
  NixOS configurations and Colmena nodes.
- `fleet-inventory/hosts/<host>/default.nix`: one host configuration.
- `fleet-inventory/secrets`: encrypted sops files tracked by the private repo.

## Public Module Outputs

Main host profiles:

- `nixosModules.kvm-host`: common NixOS base profile for KVM hosts. It includes
  SSH, firewall, fail2ban, and server tuning.
- `systemManagerModules.lxc-host`: common profile for LXC or other non-NixOS
  hosts with Nix installed.

Optional service modules:

- `nixosModules.proxy-xray`
- `nixosModules.proxy-hy2`
- `nixosModules.proxy-realm`
- `nixosModules.monitoring-komari-agent`
- `nixosModules.web-caddy`
- `nixosModules.vpn-wireguard`

Reusable lower-level modules:

- `nixosModules.server-ssh`
- `nixosModules.server-firewall`
- `nixosModules.server-fail2ban`
- `nixosModules.server-tuning`

## Private Inventory Pattern

A private inventory imports public modules and adds real deployment data:

```nix
{
  inputs.dotfiles.url = "github:wayjam/fleet-config";
  inputs.nixpkgs.follows = "dotfiles/nixpkgs";
  inputs.colmena.url = "github:zhaofengli/colmena";

  outputs = {
    self,
    dotfiles,
    nixpkgs,
    colmena,
    ...
  }: {
    colmena = {
      meta.nixpkgs = import nixpkgs {system = "x86_64-linux";};

      "proxy-example" = {
        imports = [
          dotfiles.nixosModules.kvm-host
          dotfiles.nixosModules.proxy-xray
          ./hosts/proxy-example
        ];

        deployment = {
          targetHost = "203.0.113.10";
          targetPort = 2234;
          targetUser = "root";
          tags = ["proxy" "kvm"];
        };
      };
    };
  };
}
```

## Normal Workflow

Use the private inventory for all real operations.

1. Create or copy a host under `fleet-inventory/hosts/<host>`.
2. Register the host in `fleet-inventory/hosts/default.nix`.
3. Add encrypted sops files under `fleet-inventory/secrets`.
4. Run `just fmt`, `just check`, and `just eval`.
5. Install with `nixos-anywhere` or build a disk image and `dd` it.
6. Update the host with Colmena.

Use [setup-host.md](./setup-host.md) for the complete new-host flow.

Use [just-recipes.md](./just-recipes.md) for each private inventory Justfile
recipe's purpose, arguments, and example usage.

Use [image-host-checklist.md](./image-host-checklist.md) before building a raw
disk image for a new host. It covers provider OS hardware discovery, initrd
storage drivers, disko image configuration, first-boot secrets, disk expansion,
and Stage 1 boot failure triage.

Use [host-troubleshooting.md](./host-troubleshooting.md) when inventory,
flake lock, remote builder, or deployment behavior looks wrong.
