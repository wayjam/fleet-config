# Xray xHTTP Support Design

Date: 2026-06-28

## Goal

Add xHTTP transport support to the shared Xray module and Fleet helper commands.
The default path should stay simple for ordinary hosts, while advanced hosts can
pass through full Xray `xhttpSettings` when needed.

## Scope

- Extend `my.proxy.xray` VLESS inbounds with `transport = "xhttp"`.
- Support xHTTP path as either plain Nix config or a SOPS-backed runtime file.
- Add a generic `fleet secret randstr` command for random strings.
- Include xHTTP details in `fleet profile` text, JSON, and VLESS URI output.
- Update the public fleet inventory template and relevant command docs.
- Keep existing TCP, gRPC, WebSocket, HTTPUpgrade, Reality, and Shadowsocks
  behavior compatible.

## Module API

Each VLESS inbound gains an `xhttp` submodule. The intended shape is:

```nix
my.proxy.xray.inbounds.vless-reality = {
  type = "vless";
  listenPort = 443;
  uuidFile = config.sops.secrets.xray_uuid.path;
  flow = "xtls-rprx-vision";
  transport = "xhttp";
  xhttp = {
    path = "";
    pathFile = config.sops.secrets.xray_xhttp_path.path;
    host = "";
    mode = "auto";
    settings = {};
  };
  reality = {
    enable = true;
    privateKeyFile = config.sops.secrets.xray_reality_private_key.path;
    dest = "www.example.invalid:443";
    serverNames = ["www.example.invalid"];
    shortIds = ["0123456789abcdef"];
  };
};
```

Rules:

- Add `"xhttp"` to the `transport` enum.
- `xhttp.mode` defaults to `"auto"`.
- `xhttp.pathFile` has priority over `xhttp.path`.
- `xhttp.settings` is a raw escape hatch for full Xray `xhttpSettings`.
- Final `xhttpSettings` uses `xhttp.settings` as the base, then overlays the
  common first-class fields: `path`, `host`, and `mode`.
- First-class fields intentionally override raw settings with the same key, so a
  host cannot accidentally configure a secret path that is ignored by a raw
  `settings.path`.

## Rendering And Validation

The module keeps the existing render flow: Nix serializes inbound options to a
JSON file, then the systemd `preStart` Python script reads runtime secret files
and writes `/run/xray/config.json`.

When `transport = "xhttp"`, the generated inbound uses:

```json
{
  "streamSettings": {
    "network": "xhttp",
    "security": "reality",
    "realitySettings": {},
    "xhttpSettings": {
      "path": "/example",
      "mode": "auto"
    }
  }
}
```

Behavior:

- If `xhttp.pathFile` is set, `preStart` reads its contents and uses that value
  as `xhttpSettings.path`.
- Otherwise, if `xhttp.path` is non-empty, use it directly.
- If `xhttp.host` is non-empty, write it as `xhttpSettings.host`.
- If `transport != "xhttp"`, do not emit `xhttpSettings`.
- VLESS + Reality validation stays unchanged.
- Firewall handling stays unchanged for VLESS: open the TCP listen port when
  `openFirewall = true`.

Assertions:

- For `transport = "xhttp"`, one of these must provide a path:
  `xhttp.pathFile`, `xhttp.path`, or `xhttp.settings.path`.
- `xhttp.pathFile` is not read during Nix evaluation.

## Fleet Secret CLI

Add a generic random-string generator:

```bash
fleet secret randstr
fleet secret randstr --bytes 16
fleet secret randstr --prefix /
```

Behavior:

- Output random hex.
- `--bytes` defaults to `16` and must be a positive integer.
- `--prefix` defaults to the empty string and is prepended to the generated hex.
- `fleet secret randstr --prefix /` is the recommended way to generate an xHTTP
  path value for SOPS.

Update `fleet secret proxy` to include:

```yaml
xray_xhttp_path: /...
```

The proxy bundle uses the same generic random-string logic.

## Fleet Profile Output

For VLESS xHTTP inbounds, `fleet profile` includes xHTTP information in all
output formats.

VLESS URI query parameters:

- `type=xhttp`
- `path=<resolved xhttp path>`
- `mode=<configured mode>`
- `host=<configured host>`, only when non-empty
- Existing Reality fields remain: `security=reality`, `pbk`, `fp`, `sni`, and
  `sid`.

JSON profile entries add:

```json
{
  "xhttp": {
    "path": "/example",
    "host": "",
    "mode": "auto",
    "settings": {}
  }
}
```

Text output prints transport, xHTTP path, mode, and host when present. If
profile generation cannot decrypt a path file, it fails the same way existing
secret-backed URI generation fails.

## Template And Inventory Updates

Public `fleet-config` updates:

- Update `templates/fleet-inventory/hosts/proxy-example/default.nix`.
- Add `sops.secrets.xray_xhttp_path = {};`.
- Show the VLESS Reality example using `transport = "xhttp"` and
  `xhttp.pathFile = config.sops.secrets.xray_xhttp_path.path`.
- Update Justfile or docs comments that list secret commands so they mention
  `randstr`.

Private `fleet-inventory` updates during implementation are limited to structure
only unless the operator supplies encrypted secrets:

- Add `sops.secrets.xray_xhttp_path = {};` to hosts that should use xHTTP.
- Add `transport = "xhttp"` and `xhttp.pathFile = ...` to the target VLESS
  inbound.
- Add encrypted `xray_xhttp_path` values with SOPS outside the implementation
  patch. No plaintext production path belongs in git.

## Testing

Minimum verification:

- `fleet secret randstr --prefix /` prints a slash-prefixed random hex path.
- `nix flake check` passes, or if full check is unavailable, evaluate at least
  the Xray module options and a template host.
- `nix eval` confirms an xHTTP inbound serializes with `transport = "xhttp"` and
  the expected xHTTP fields.
- `fleet profile --kind xray --format json` emits xHTTP fields when secrets can
  be decrypted.
- If local SOPS keys are unavailable, profile testing may use a synthetic or
  public-template configuration instead of real host secrets.

## Out Of Scope

- Changing existing non-xHTTP hosts by default.
- Replacing Reality, UUID, or Shadowsocks secret names.
- Adding client-specific import formats beyond the existing URI/text/JSON
  profile outputs.
- Managing or committing plaintext production xHTTP paths.
