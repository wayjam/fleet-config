{lib, ...}: {
  options.my.server.firewall = {
    enable = lib.mkOption {
      type = lib.types.bool;
      default = true;
      description = "Enable host firewall support when the target platform can enforce it.";
    };

    allowedTCPPorts = lib.mkOption {
      type = with lib.types; listOf port;
      default = [];
      description = "TCP ports declared by managed services.";
    };

    allowedUDPPorts = lib.mkOption {
      type = with lib.types; listOf port;
      default = [];
      description = "UDP ports declared by managed services.";
    };

    allowPing = lib.mkOption {
      type = lib.types.bool;
      default = true;
      description = "Allow ICMP echo requests when firewall support is available.";
    };
  };
}
