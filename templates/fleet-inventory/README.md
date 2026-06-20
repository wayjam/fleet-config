# Example Private Host Inventory

This directory is a sanitized template for the private host inventory repo.
Copy it into a private repository, then replace placeholder hosts, addresses,
domains, age recipients, and encrypted secrets.

The default `flake.nix` expects this layout after copying:

```text
~/deploy/
  fleet-config/
  fleet-inventory/
```

If your private repo lives somewhere else, update `inputs.dotfiles.url`.

The real private repo should keep:

- Real host IPs, domains, ports, and deployment targets
- Host-specific module imports and application configuration
- Encrypted `sops` secret files
- Local generated private material under ignored `local/`

The public `fleet-config` repo should keep reusable modules, shared scripts,
inventory-generation logic, docs, and this sanitized structure only. This
private skeleton should call those shared outputs instead of copying scripts.

## Host Inventory

Add each host once in `hosts/default.nix`.

- `nixos.<name>.path`: the host config file or directory. The host config owns
  its own `imports`.
- `nixos.<name>.deployment`: Colmena target host, port, user, and tags.
- `nixos.<name>.image = true`: also exposes `packages.x86_64-linux.<name>` for
  disko image builds.
- `system.<name>.path`: system-manager config for LXC/existing Linux.

For NixOS hosts, the inventory key becomes the default
`networking.hostName`. Override `networking.hostName` in the host config only
when it should differ from the inventory key.

## Common Commands

```shell
just check
just eval
just deploy proxy-example
just image image-example
just lxc-switch lxc-example
just secret-proxy
just profile proxy-example
```

Generate client connection profiles:

```shell
just profile proxy-example
nix run .#fleet -- profile proxy-example --kind xray
nix run .#fleet -- profile proxy-example --kind hy2
nix run .#fleet -- profile proxy-example --kind wireguard
nix run .#fleet -- profile proxy-example --kind xray --inbound vless-reality
nix run .#fleet -- profile proxy-example --host proxy.example.com --name proxy
```

The command reads Xray, HY2, and WireGuard connection details from the Nix host
configuration, then reads client-facing secrets from `secrets/<host>.yaml`.
Xray profiles include URI plus port, transport, Reality SNI, shortId, and other
details. HY2 profiles include port, SNI, TLS, masquerade, and a `hysteria2://`
URI. WireGuard profiles show interface addresses, listen port, public key when
`wg` is available locally, and peers.

## Secrets

Generate an age key for local editing:

```shell
just secret-age-file admin
```

Replace the age recipient in `.sops.yaml`, then create encrypted host secrets:

```shell
sops secrets/proxy-example.yaml
git add secrets/proxy-example.yaml
```
