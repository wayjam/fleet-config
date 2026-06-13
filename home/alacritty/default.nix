{
  config,
  lib,
  ...
}:
with lib; let
  cfg = config.my.alacritty;
in {
  options.my.alacritty = {
    enable = mkEnableOption "Alacritty configuration";
  };

  config = mkIf cfg.enable {
    xdg.configFile."alacritty/alacritty.toml".source = ./alacritty.toml;
  };
}
