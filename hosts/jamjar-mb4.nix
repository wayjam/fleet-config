{
  nixpkgs,
  system,
  hostName,
  ...
}: let
  myvars = import ../vars {inherit (nixpkgs) lib;};
  brewUtils = import ../lib/homebrew.nix {inherit (nixpkgs) lib;};

  # user level (home-manager)
  mycfgs = {
    my.dev.enable = true;
    my.squirrel.enable = true;
    my.tmux.enable = true;
    my.mediaCollections.enable = true;
    my.ollama.enable = true;
    my.alacritty.enable = false;
    my.wezterm.enable = false;
    my.ghostty.enable = true;
  };
in {
  root = {
    system.stateVersion = 5;
  };

  inherit myvars;

  module = {
    config,
    pkgs,
    lib,
    ...
  }: {
    inherit (mycfgs);

    imports = [
      ../modules/font
    ];

    nix.extraOptions = ''
      extra-platforms = x86_64-darwin aarch64-darwin
    '';

    homebrew.casks =
      (brewUtils.mkBrewCasks mycfgs)
      ++ [
      ];

    home-manager.users.${myvars.userName} =
      mycfgs
      // {
        home.packages = with pkgs; [hugo];
      };
  };
}
