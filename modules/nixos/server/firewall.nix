{
  config,
  lib,
  ...
}: let
  cfg = config.my.server.firewall;
in {
  imports = [
    ../../shared/server/firewall-options.nix
  ];

  config = {
    networking.firewall = {
      inherit (cfg) enable allowPing;
      allowedTCPPorts = lib.unique cfg.allowedTCPPorts;
      allowedUDPPorts = lib.unique cfg.allowedUDPPorts;
    };
  };
}
