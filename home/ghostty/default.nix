{
  config,
  lib,
  ...
}:
with lib; let
  cfg = config.my.ghostty;
in {
  options.my.ghostty = {
    enable = mkEnableOption "Ghostty configuration";
  };

  config = mkIf cfg.enable {
    xdg.configFile."ghostty/config".source = ./config;
  };
}
