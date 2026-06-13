{
  config,
  lib,
  pkgs,
  ...
}:
with lib; let
  cfg = config.my.mediaCollections;
in {
  options.my.mediaCollections = {
    enable = mkEnableOption "Media Related Collection";
  };

  config = mkIf cfg.enable {
    home.packages = with pkgs; [
      mpv
      ffmpeg
      yt-dlp
    ];
  };
}
