{
  config,
  lib,
  pkgs,
  rime-config,
  ...
}:
with lib; let
  cfg = config.my.squirrel;
in {
  options.my.squirrel = {
    enable = mkEnableOption "Enable Squirrel(rime)";
  };

  config = mkIf cfg.enable {
    home.file = {
      "${config.home.homeDirectory}/Library/Rime" = {
        source = rime-config;
        recursive = true;
      };
      "${config.home.homeDirectory}/Library/Rime/default.custom.yaml".source = ./default.custom.yaml;
      "${config.home.homeDirectory}/Library/Rime/squirrel.custom.yaml".source = ./squirrel.custom.yaml;
    };
  };
}
