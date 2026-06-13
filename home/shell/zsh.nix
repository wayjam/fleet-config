{...}: {
  programs.zsh = {
    enable = true;
    enableCompletion = true;
    initContent = ''
      export PATH="$PATH:$HOME/bin:$HOME/.local/bin"
      [ -f "$HOME/.zshrc.local" ] && source $HOME/.zshrc.local
    '';
    shellAliases = {
      g = "git";
      unproxy = "unset https_proxy http_proxy";
    };
  };
}
