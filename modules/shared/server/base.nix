{
  config,
  lib,
  pkgs,
  ...
}: let
  cfg = config.my.server.base;
in {
  options.my.server.base = {
    enable = lib.mkEnableOption "shared base configuration for hosts";

    packages = lib.mkOption {
      type = with lib.types; listOf package;
      default = with pkgs; [
        curl
        wget
        rsync
        logrotate
        tcpdump
        mtr
        findutils
        gnugrep
        gnused
        gawk
        gnutar
        xz
        zstd
        python3
        vim
        git
        htop
        jq
        lsof
      ];
      description = "Base packages installed on managed hosts.";
    };
  };

  config = lib.mkIf cfg.enable {
    environment.systemPackages = cfg.packages;

    nix.settings = {
      experimental-features = ["nix-command" "flakes"];
      builders-use-substitutes = lib.mkDefault true;
    };

    nix.optimise.automatic = lib.mkDefault true;
  };
}
