{
  config,
  lib,
  ...
}:
with lib; let
  cfg = config.my.wezterm;
in {
  options.my.wezterm = {
    enable = mkEnableOption "Wezterm configuration";
  };

  config = mkIf cfg.enable {
    xdg.configFile."wezterm/wezterm.lua".source = ./wezterm.lua;
  };
}
