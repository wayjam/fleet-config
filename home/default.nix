{
  config,
  pkgs,
  lib,
  myvars,
  ...
}: {
  imports = [
    ./core.nix
    ./shell
    ./git.nix
    ./neovim
    ./dev
    ./media-collections
    ./alacritty
    ./wezterm
    ./ghostty
    ./squirrel
    ./tmux
    ./ollama.nix
  ];

  programs.home-manager.enable = true;

  # Home Manager needs a bit of information about you and the
  # paths it should manage.
  home = {
    username = myvars.userName;

    # This value determines the Home Manager release that your
    # configuration is compatible with. This helps avoid breakage
    # when a new Home Manager release introduces backwards
    # incompatible changes.
    #
    # You can update Home Manager without changing this value. See
    # the Home Manager release notes for a list of state version
    # changes in each release.
    stateVersion = "25.05";

    sessionPath = [
      "$HOME/bin"
      "$HOME/.local/bin"
    ];

    sessionVariables = {
      LANG = "en_US.UTF-8";
      TERM = "xterm-256color";
      LC_CTYPE = "en_US.UTF-8";
      NIX_PATH = "$HOME/.nix-defexpr/channels:/nix/var/nix/profiles/per-user/root/channels";
      # https://github.com/localsend/localsend/issues/461#issuecomment-1715170140
      XDG_DOWNLOAD_DIR = "$HOME/Downloads";
    };
  };
}
