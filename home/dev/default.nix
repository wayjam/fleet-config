{
  config,
  lib,
  pkgs,
  ...
}:
with lib; let
  cfg = config.my.dev;
in {
  options.my.dev = {
    enable = mkEnableOption "Development";
  };

  config = mkIf cfg.enable (
    {}
    // import ./core.nix {inherit config lib pkgs;}
    // import ./langs.nix {inherit config lib pkgs;}
  );
}
