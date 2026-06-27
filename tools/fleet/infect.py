"""`fleet infect` — multi-stage nixos-infect pipeline.

Stages: probe → render-config → upload-config → run-infect → install-secrets
→ reboot → wait-ssh → deploy-remote → health-check. State markers persist on
the target under REMOTE_INFECT_DIR so stages can resume.
"""

import argparse
import base64
import json
import shlex
import subprocess
import sys
import time

from builder import apply_builder_overrides, builder_config, ssh_args
from common import capture, die, repo_path
from deploy import cmd_deploy
from nix import eval_host_json, eval_host_raw, host_deployment
from target import (
    normalize_ssh_target,
    ssh_base as target_ssh_base,
    target_read_text,
    target_run,
    target_upload_text,
)


INFECT_STAGES = [
    "probe",
    "render-config",
    "upload-config",
    "run-infect",
    "install-secrets",
    "reboot",
    "wait-ssh",
    "deploy-remote",
    "health-check",
]

REMOTE_INFECT_DIR = "/root/fleet-infect"


def key_identity(key):
    parts = str(key).strip().split()
    if len(parts) < 2:
        return str(key).strip()
    return " ".join(parts[:2])


def nix_string(value):
    return json.dumps(str(value))


def nix_list(values):
    return "[ " + " ".join(nix_string(value) for value in values if str(value).strip()) + " ]"


def nix_bool(value):
    return "true" if value else "false"


def target_mark_stage(user, host, port, stage, *, timeout=30):
    marker = f"{REMOTE_INFECT_DIR}/{stage}.done"
    target_run(
        user,
        host,
        port,
        f"mkdir -p {REMOTE_INFECT_DIR}; date -u +%FT%TZ > {shlex.quote(marker)}",
        timeout=timeout,
    )


def infect_channel(host, args):
    if args.nix_channel:
        return args.nix_channel
    release = eval_host_raw(host, "system.nixos.release", "")
    state_version = eval_host_raw(host, "system.stateVersion", "25.05")
    source = release or state_version
    parts = source.split(".")
    if len(parts) >= 2 and parts[0].isdigit() and parts[1][:2].isdigit():
        return f"nixos-{parts[0]}.{parts[1][:2]}"
    return "nixos-25.05"


def detect_initrd_modules(host):
    modules = eval_host_json(host, "boot.initrd.availableKernelModules", [])
    forced = eval_host_json(host, "boot.initrd.kernelModules", [])
    fallback = ["virtio_pci", "virtio_blk", "virtio_scsi", "nvme", "sd_mod", "ahci", "ata_piix", "xhci_pci"]
    merged = []
    for item in [*modules, *forced, *fallback]:
        if item and item not in merged:
            merged.append(item)
    return merged


def build_networking_nix(probe, host_name=None):
    iface = probe.get("iface") or "eth0"
    lines = [
        "networking = {",
        f"  hostName = {nix_string(host_name)};" if host_name else "",
        "  useDHCP = false;",
        f"  interfaces.{nix_string(iface)} = {{",
    ]
    lines = [line for line in lines if line]
    ipv4 = probe.get("ipv4") or []
    ipv6 = probe.get("ipv6") or []
    if ipv4:
        lines.append("    ipv4.addresses = [")
        for item in ipv4:
            address, prefix = item.split("/", 1)
            lines.append(f"      {{ address = {nix_string(address)}; prefixLength = {int(prefix)}; }}")
        lines.append("    ];")
    if ipv6:
        lines.append("    ipv6.addresses = [")
        for item in ipv6:
            address, prefix = item.split("/", 1)
            lines.append(f"      {{ address = {nix_string(address)}; prefixLength = {int(prefix)}; }}")
        lines.append("    ];")
    lines.append("  };")
    if probe.get("gateway4"):
        lines.append(f"  defaultGateway = {nix_string(probe['gateway4'])};")
    if probe.get("gateway6"):
        lines.extend(
            [
                "  defaultGateway6 = {",
                f"    address = {nix_string(probe['gateway6'])};",
                f"    interface = {nix_string(iface)};",
                "  };",
            ]
        )
    nameservers = probe.get("nameservers") or ["1.1.1.1", "8.8.8.8"]
    lines.append(f"  nameservers = {nix_list(nameservers)};")
    lines.append("};")
    return "\n".join(lines)


def render_infect_configs(host, probe, args):
    root_keys = eval_host_json(host, "users.users.root.openssh.authorizedKeys.keys", [])
    admin_keys = eval_host_json(host, "users.users.admin.openssh.authorizedKeys.keys", [])
    ssh_keys = []
    for key in [*root_keys, *admin_keys]:
        if key and key not in ssh_keys:
            ssh_keys.append(key)
    if not ssh_keys:
        die(f"{host} has no root/admin SSH authorized keys")

    target_port = args.target_port or int(host_deployment(host).get("targetPort", 2234))
    state_version = eval_host_raw(host, "system.stateVersion", "25.05")
    kernel_params = eval_host_json(host, "boot.kernelParams", [])
    grub_devices = eval_host_json(host, "boot.loader.grub.devices", [])
    if not grub_devices:
        legacy_grub_device = eval_host_raw(host, "boot.loader.grub.device", "")
        grub_devices = [legacy_grub_device or probe.get("disk") or "/dev/sda"]
    initrd_modules = detect_initrd_modules(host)
    root_device = f"/dev/disk/by-uuid/{probe['root_uuid']}" if probe.get("root_uuid") else probe["root_source"]
    root_fs = probe.get("root_fs") or "ext4"
    is_uefi = probe.get("boot_mode") == "uefi"
    esp_mount = probe.get("esp_mount") or "/boot/efi"
    esp_device = f"/dev/disk/by-uuid/{probe['esp_uuid']}" if probe.get("esp_uuid") else probe.get("esp_source", "")
    esp_fs = probe.get("esp_fs") or "vfat"

    configuration = f"""{{ config, pkgs, lib, modulesPath, ... }}:
{{
  imports = [ ./hardware-configuration.nix ];

  system.stateVersion = {nix_string(state_version)};

  boot.loader.timeout = 1;
  boot.tmp.cleanOnBoot = true;
  boot.kernelParams = {nix_list(kernel_params)};
  boot.initrd.availableKernelModules = {nix_list(initrd_modules)};
  boot.initrd.kernelModules = {nix_list(eval_host_json(host, "boot.initrd.kernelModules", []))};
  {("boot.loader.grub.devices = " + nix_list(grub_devices) + ";") if not is_uefi else 'boot.loader.grub.devices = [ "nodev" ];'}
  {('boot.loader.efi.efiSysMountPoint = ' + nix_string(esp_mount) + ';\n  boot.loader.grub.efiSupport = true;\n  boot.loader.grub.efiInstallAsRemovable = true;') if is_uefi else ''}

  {build_networking_nix(probe, host)}
  networking.firewall.allowedTCPPorts = [ 22 {target_port} ];

  services.openssh = {{
    enable = true;
    ports = [ 22 {target_port} ];
    settings = {{
      PermitRootLogin = "prohibit-password";
      PasswordAuthentication = false;
      KbdInteractiveAuthentication = false;
    }};
  }};

  users.mutableUsers = false;
  users.users.root.openssh.authorizedKeys.keys = {nix_list(ssh_keys)};
  users.users.admin = {{
    isNormalUser = true;
    extraGroups = [ "wheel" ];
    openssh.authorizedKeys.keys = config.users.users.root.openssh.authorizedKeys.keys;
    shell = pkgs.zsh;
  }};
  security.sudo.wheelNeedsPassword = false;
  programs.zsh.enable = true;

  nix.settings.experimental-features = [ "nix-command" "flakes" ];
  environment.systemPackages = with pkgs; [ curl git htop jq vim wget ];
  zramSwap.enable = true;
  systemd.coredump.enable = false;
  services.journald.extraConfig = ''
    Storage=volatile
    RuntimeMaxUse=32M
  '';
}}
"""

    hardware = f"""{{ modulesPath, ... }}:
{{
  imports = [ (modulesPath + "/profiles/qemu-guest.nix") ];
  fileSystems."/" = {{
    device = {nix_string(root_device)};
    fsType = {nix_string(root_fs)};
  }};
  {('fileSystems.' + nix_string(esp_mount) + ' = {\n    device = ' + nix_string(esp_device) + ';\n    fsType = ' + nix_string(esp_fs) + ';\n  };') if is_uefi and esp_device else ''}
}}
"""
    return configuration, hardware


def parse_probe_output(output):
    probe = {}
    list_keys = {"ipv4", "ipv6", "nameservers", "modules"}
    for raw in output.splitlines():
        if "\t" not in raw:
            continue
        key, value = raw.split("\t", 1)
        value = value.strip()
        if key in list_keys:
            probe[key] = [part for part in value.split("|") if part]
        else:
            probe[key] = value
    if not probe.get("root_source"):
        die("probe failed: missing root_source")
    if not probe.get("disk"):
        die("probe failed: missing parent disk")
    return probe


def infect_stage_slice(args):
    if args.stage not in INFECT_STAGES:
        die(f"unknown infect stage: {args.stage}")
    if args.stop_after and args.stop_after not in INFECT_STAGES:
        die(f"unknown infect stop stage: {args.stop_after}")
    start = INFECT_STAGES.index(args.stage)
    end = INFECT_STAGES.index(args.stop_after) if args.stop_after else len(INFECT_STAGES) - 1
    if end < start:
        die("--stop-after must be the same as or after --stage")
    stages = INFECT_STAGES[start : end + 1]
    if args.no_reboot:
        stages = [stage for stage in stages if stage not in {"reboot", "wait-ssh", "deploy-remote", "health-check"}]
    if args.no_deploy:
        stages = [stage for stage in stages if stage not in {"deploy-remote"}]
    return stages


def resolve_infect_target(host, args):
    deployment = host_deployment(host)
    target_host = deployment.get("targetHost")
    target_user = deployment.get("targetUser", "root")
    current_port = args.current_port or 22
    target_port = args.target_port or int(deployment.get("targetPort", 2234))
    if args.ssh_target:
        target_user, target_host, parsed_port, _ = normalize_ssh_target(
            args.ssh_target, default_port=22, default_user=target_user
        )
        current_port = parsed_port
    if not target_host:
        die(f"missing targetHost for {host}; pass ssh-target explicitly")
    return target_user, target_host, current_port, target_port


def confirm_infect(host, user, target_host, current_port, args):
    if args.yes or args.dry_run:
        return
    if not sys.stdin.isatty():
        die("infect is destructive; rerun with --yes in non-interactive environments")
    print(f"This will replace the OS on {user}@{target_host}:{current_port}.")
    answer = input(f"Type the host name to continue ({host}): ")
    if answer != host:
        die("confirmation did not match; aborting")


def builder_public_key(builder):
    try:
        return capture([*ssh_args(builder), "cat /root/.ssh/id_ed25519.pub 2>/dev/null || true"]).strip()
    except subprocess.CalledProcessError as exc:
        die(f"failed to read builder root public key: {exc}")


def check_builder_key_authorized(host, builder):
    key = builder_public_key(builder)
    if not key:
        die("builder root key missing; create /root/.ssh/id_ed25519 on the builder and add its public key to sshAuthorizedKeys")
    host_keys = eval_host_json(host, "users.users.root.openssh.authorizedKeys.keys", [])
    identities = {key_identity(item) for item in host_keys}
    if key_identity(key) not in identities:
        die("builder root public key is not authorized by the host config; add it to sshAuthorizedKeys before infect")
    return key


def run_infect_probe(user, host, port, args):
    script = rf"""
mkdir -p {REMOTE_INFECT_DIR}
root_source=$(findmnt -n -o SOURCE / | head -n1)
root_real=$(realpath "$root_source" 2>/dev/null || printf '%s' "$root_source")
root_fs=$(findmnt -n -o FSTYPE / | head -n1)
root_uuid=$(blkid -s UUID -o value "$root_real" 2>/dev/null || true)
disk_name=$(lsblk -n -o PKNAME "$root_real" 2>/dev/null | head -n1 | tr -d '[:space:]')
partn=$(lsblk -n -o PARTN "$root_real" 2>/dev/null | head -n1 | tr -d '[:space:]')
if [ -n "$disk_name" ]; then disk="/dev/$disk_name"; else disk="$root_real"; fi
if [ -d /sys/firmware/efi ]; then boot_mode=uefi; else boot_mode=bios; fi
esp_mount=""
esp_source=""
esp_fs=""
esp_uuid=""
if [ "$boot_mode" = uefi ]; then
  for candidate in /boot/efi /boot/EFI /boot; do
    if mountpoint -q "$candidate"; then
      esp_mount="$candidate"
      esp_source=$(findmnt -n -o SOURCE "$candidate" | head -n1)
      esp_real=$(realpath "$esp_source" 2>/dev/null || printf '%s' "$esp_source")
      esp_fs=$(findmnt -n -o FSTYPE "$candidate" | head -n1)
      esp_uuid=$(blkid -s UUID -o value "$esp_real" 2>/dev/null || true)
      break
    fi
  done
fi
iface=$(ip -4 route show default 2>/dev/null | awk '{{print $5; exit}}')
if [ -z "$iface" ]; then iface=$(ip route show default 2>/dev/null | awk '{{print $5; exit}}'); fi
ipv4=$(ip -o -4 addr show scope global dev "$iface" 2>/dev/null | awk '{{print $4}}' | paste -sd '|' -)
ipv6=$(ip -o -6 addr show scope global dev "$iface" 2>/dev/null | awk '{{print $4}}' | grep -v '^fe80:' | paste -sd '|' - || true)
gateway4=$(ip -4 route show default 2>/dev/null | awk '{{print $3; exit}}')
gateway6=$(ip -6 route show default 2>/dev/null | awk '{{print $3; exit}}')
nameservers=$(awk '/^nameserver / {{print $2}}' /etc/resolv.conf | sed 's/^127\..*/1.1.1.1/; s/^::1$/2606:4700:4700::1111/' | paste -sd '|' -)
modules=$(lsmod 2>/dev/null | awk 'NR>1 {{print $1}}' | sort | paste -sd '|' -)
mem_kb=$(awk '/MemTotal/ {{print $2}}' /proc/meminfo)
kernel=$(uname -a)
for key in root_source root_real root_fs root_uuid disk partn boot_mode esp_mount esp_source esp_fs esp_uuid iface ipv4 ipv6 gateway4 gateway6 nameservers modules mem_kb kernel; do
  eval "value=\${{$key:-}}"
  printf '%s\t%s\n' "$key" "$value"
done
"""
    output = target_run(user, host, port, script, timeout=args.timeout, capture_output=True)
    probe = parse_probe_output(output)
    target_upload_text(user, host, port, f"{REMOTE_INFECT_DIR}/probe.json", json.dumps(probe, indent=2) + "\n", timeout=args.timeout)
    target_mark_stage(user, host, port, "probe", timeout=args.timeout)
    return probe


def remote_probe_json(user, host, port, args):
    try:
        return json.loads(target_read_text(user, host, port, f"{REMOTE_INFECT_DIR}/probe.json", timeout=args.timeout))
    except (subprocess.CalledProcessError, json.JSONDecodeError):
        die("missing remote probe.json; run --stage probe first")


def remote_configs_exist(user, host, port, args):
    try:
        target_run(
            user,
            host,
            port,
            f"test -s {REMOTE_INFECT_DIR}/configuration.nix && test -s {REMOTE_INFECT_DIR}/hardware-configuration.nix",
            timeout=args.timeout,
        )
        return True
    except subprocess.CalledProcessError:
        return False


def run_infect_script(user, host, port, nix_channel, args):
    script = rf"""
if [ -e /etc/NIXOS ] && [ ! -e /etc/NIXOS_LUSTRATE ]; then
  echo "target already appears to be NixOS; resume with --stage wait-ssh or --stage deploy-remote"
  exit 2
fi
mkdir -p {REMOTE_INFECT_DIR}
cd {REMOTE_INFECT_DIR}
if [ ! -s nixos-infect ]; then
  if command -v curl >/dev/null 2>&1; then
    curl -L https://raw.githubusercontent.com/elitak/nixos-infect/master/nixos-infect -o nixos-infect
  else
    wget -O nixos-infect https://raw.githubusercontent.com/elitak/nixos-infect/master/nixos-infect
  fi
fi
chmod +x nixos-infect
perl -0pi -e 's#mktemp /tmp/nixos-infect\.XXXXX\.swp#mktemp /root/fleet-infect/nixos-infect.XXXXX.swp#g; s#rm -vf /tmp/nixos-infect\.\*\.swp#rm -vf /root/fleet-infect/nixos-infect.*.swp#g' nixos-infect
NIX_CHANNEL={shlex.quote(nix_channel)} NO_REBOOT=1 bash -x ./nixos-infect 2>&1 | tee {REMOTE_INFECT_DIR}/infect.log
"""
    target_run(user, host, port, script, timeout=args.timeout)
    target_mark_stage(user, host, port, "run-infect", timeout=args.timeout)


def install_node_age_key(user, host, port, config, args):
    key_path = repo_path(config.get("paths", {}).get("node_age_key", "local/node-age.txt"))
    if not key_path.exists():
        die(f"missing node age key: {key_path}")
    encoded = base64.b64encode(key_path.read_bytes()).decode()
    script = rf"""
install -d -m 0700 /etc/sops/age
base64 -d > /etc/sops/age/key.txt
chmod 0400 /etc/sops/age/key.txt
touch /etc/NIXOS_LUSTRATE
grep -qxF etc/sops/age/key.txt /etc/NIXOS_LUSTRATE || printf '%s\n' etc/sops/age/key.txt >> /etc/NIXOS_LUSTRATE
"""
    target_run(user, host, port, script, timeout=args.timeout, input_text=encoded)
    target_mark_stage(user, host, port, "install-secrets", timeout=args.timeout)


def wait_for_ssh(user, host, port, timeout):
    deadline = time.time() + int(timeout)
    while time.time() < deadline:
        result = subprocess.run(
            [*target_ssh_base(user, host, port, timeout=8), "true"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        if result.returncode == 0:
            return
        time.sleep(5)
    die(f"timed out waiting for SSH on {user}@{host}:{port}")


def infect_health_check(user, host, port, args):
    script = "hostname; readlink /run/current-system; findmnt -no SOURCE,FSTYPE /; systemctl --failed --no-pager; systemctl is-active sshd || systemctl is-active ssh; systemctl is-active fail2ban || true"
    target_run(user, host, port, script, timeout=args.timeout)


def cmd_infect(args, config):
    builder = apply_builder_overrides(builder_config(config, args.builder), args)
    user, target_host, current_port, target_port = resolve_infect_target(args.host, args)
    stages = infect_stage_slice(args)
    nix_channel = infect_channel(args.host, args)

    if args.dry_run:
        print(
            json.dumps(
                {
                    "host": args.host,
                    "target": f"{user}@{target_host}",
                    "current_port": current_port,
                    "target_port": target_port,
                    "builder": builder["name"],
                    "nix_channel": nix_channel,
                    "stages": stages,
                    "remote_state_dir": REMOTE_INFECT_DIR,
                },
                indent=2,
            )
        )
        return

    confirm_infect(args.host, user, target_host, current_port, args)
    if "deploy-remote" in stages:
        check_builder_key_authorized(args.host, builder)

    probe = None
    active_port = current_port
    for stage in stages:
        print(f"[fleet] infect stage: {stage}", file=sys.stderr)
        if stage == "probe":
            probe = run_infect_probe(user, target_host, active_port, args)
        elif stage == "render-config":
            if probe is None:
                probe = remote_probe_json(user, target_host, active_port, args)
            configuration, hardware = render_infect_configs(args.host, probe, args)
            target_upload_text(user, target_host, active_port, f"{REMOTE_INFECT_DIR}/configuration.nix", configuration, timeout=args.timeout)
            target_upload_text(user, target_host, active_port, f"{REMOTE_INFECT_DIR}/hardware-configuration.nix", hardware, timeout=args.timeout)
            target_mark_stage(user, target_host, active_port, stage, timeout=args.timeout)
        elif stage == "upload-config":
            if not remote_configs_exist(user, target_host, active_port, args):
                die("missing rendered config; run --stage render-config first")
            target_run(
                user,
                target_host,
                active_port,
                f"install -d -m 0755 /etc/nixos; cp {REMOTE_INFECT_DIR}/configuration.nix /etc/nixos/configuration.nix; cp {REMOTE_INFECT_DIR}/hardware-configuration.nix /etc/nixos/hardware-configuration.nix",
                timeout=args.timeout,
            )
            target_mark_stage(user, target_host, active_port, stage, timeout=args.timeout)
        elif stage == "run-infect":
            run_infect_script(user, target_host, active_port, nix_channel, args)
        elif stage == "install-secrets":
            install_node_age_key(user, target_host, active_port, config, args)
        elif stage == "reboot":
            try:
                target_run(user, target_host, active_port, "reboot", timeout=8)
            except subprocess.CalledProcessError:
                pass
            active_port = target_port
        elif stage == "wait-ssh":
            active_port = target_port
            wait_for_ssh(user, target_host, active_port, args.timeout)
        elif stage == "deploy-remote":
            deploy_args = argparse.Namespace(
                target=args.host,
                builder=builder["name"],
                port=builder.get("port"),
                ssh_key=builder.get("ssh_key"),
                ssh_config=builder.get("ssh_config"),
                remote_root=builder.get("remote_root"),
                remote_nix=builder.get("remote_nix"),
                memory=builder.get("memory"),
                kvm=False,
                no_kvm=not builder.get("use_kvm", False),
            )
            cmd_deploy(deploy_args, config)
        elif stage == "health-check":
            active_port = target_port
            infect_health_check(user, target_host, active_port, args)
        else:  # pragma: no cover
            die(f"unhandled stage: {stage}")
