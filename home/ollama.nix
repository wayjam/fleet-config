{
  config,
  isDarwin,
  lib,
  pkgs,
  ...
}:
with lib; let
  cfg = config.my.ollama;
in {
  options.my.ollama = {
    enable = mkEnableOption "Ollama";
  };

  config = mkIf cfg.enable {
    home.packages = mkIf isDarwin [pkgs.ollama];

    services.ollama = mkIf (!isDarwin) {
      enable = true;
    };
  };
}
