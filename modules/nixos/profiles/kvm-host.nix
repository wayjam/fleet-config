{...}: {
  imports = [
    ../../nix-core.nix
    ../../shared/server/base.nix
    ../secrets/sops-age-key.nix
    ../server/disk-expansion.nix
    ../server/ssh.nix
    ../server/firewall.nix
    ../server/fail2ban.nix
    ../server/tuning.nix
  ];

  my.server = {
    base.enable = true;
    ssh.enable = true;
    firewall.enable = true;
    fail2ban.enable = true;
    tuning.enable = true;
  };
}
