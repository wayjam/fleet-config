{pkgs, ...}: {
  home.packages = with pkgs; [
    # ssh
    age
    sops
    ssh-to-age

    # archives
    zip
    xz
    unzip
    p7zip
    zstd
    gnutar

    # utils
    fd # simple, fast and user-friendly alternative to find
    ripgrep # recursively searches directories for a regex pattern
    jq # A lightweight and flexible command-line JSON processor
    yq-go # yaml processor https://github.com/mikefarah/yq
    htop # A better top
    nix-prefetch-git
    nix-prefetch-github

    socat # replacement of openbsd-netcat
    nmap # A utility for network discovery and security auditing
    bind

    # misc
    gnumake
    cowsay
    file
    which
    tree
    gnused
    gawk
    gnupg
  ];

  programs = {
    fastfetch.enable = true;

    direnv = {
      enable = true;
      nix-direnv.enable = true;
    };

    # A modern replacement for ‘ls’
    # useful in bash/zsh prompt, not in nushell.
    eza = {
      enable = true;
      git = true;
      icons = "auto";
      enableZshIntegration = true;
    };

    fzf = {
      enable = true;
      enableZshIntegration = true;
    };

    # terminal file manager
    yazi = {
      enable = true;
      enableZshIntegration = true;
      shellWrapperName = "yy";
      settings = {
        manager = {
          show_hidden = true;
          sort_dir_first = true;
        };
      };
    };
  };
}
