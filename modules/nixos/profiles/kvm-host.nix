{...}: {
  imports = [
    ../../shared/server/base.nix
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
