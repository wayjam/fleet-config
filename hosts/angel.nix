{
  nixpkgs,
  system,
  hostName,
}: let
  myvars = import ../vars {inherit (nixpkgs) lib;};
  # user level
  mycfgs = {
    my.container.enable = true;
  };
in {
  root = {
    system.stateVersion = "25.05";
    fileSystems."/" = {
      device = "/dev/disk/by-label/nixos";
      fsType = "ext4";
    };
    boot.loader.grub.devices = ["/dev/sda"];
  };

  myvars = myvars;

  module = {
    config,
    pkgs,
    lib,
    ...
  }: {
    # sys level
    users.allowNoPasswordLogin = true;

    imports = [
    ];
  };
}
