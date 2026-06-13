{
  config,
  lib,
  pkgs,
  ...
}:
with lib; let
  cfg = config.my.tmux;
in {
  options.my.tmux = {
    enable = mkEnableOption "Tmux and its configuration";
  };

  config = mkIf cfg.enable (
    let
      tmuxConfig = pkgs.fetchFromGitHub {
        owner = "gpakosz";
        repo = ".tmux";
        rev = "master";
        sha256 = "sha256-TowIG+E2+zLsQgLFduchAllHxowZCLT3tDL7+8K9xeQ=";
      };
    in {
      programs.tmux = {
        enable = true; # 启用 tmux
        extraConfig = ''
          source-file ${config.xdg.configHome}/tmux/tmux.conf
          source-file ${config.xdg.configHome}/tmux/tmux.conf.local
        '';
      };

      xdg.configFile = {
        "tmux/tmux.conf".source = "${tmuxConfig}/.tmux.conf";
        "tmux/tmux.conf.local".source = ./tmux.conf.local;
      };
    }
  );
}
