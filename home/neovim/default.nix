{
  lib,
  pkgs,
  config,
  ...
}: let
  vimConfig = pkgs.fetchFromGitHub {
    owner = "wayjam";
    repo = "vim-config";
    rev = "master";
    sha256 = "sha256-jTSp8oHNqVvBwfKXZsstqvN7k5zRh3gYxpInJ+gvz9U=";
  };
in {
  programs.neovim = {
    enable = true;
    defaultEditor = true;

    viAlias = true;
    vimAlias = true;

    withPython3 = true;
    withNodeJs = true;
    withRuby = true;

    extraLuaPackages = ps: [
      ps.lua
      ps.luarocks-nix
    ];

    extraPython3Packages = ps:
      with ps; [
        pillow # for pastify plugin
        pynvim # for pastify plugin
      ];

    extraPackages = with pkgs; [
      fzf
    ];
  };

  # link to ~/.config/nvim
  xdg.configFile = {
    "nvim" = {
      source = vimConfig;
      recursive = true;
    };
  };
}
