{
  description = "Example private host inventory for reusable fleet-config modules";

  inputs = {
    dotfiles.url = "path:../fleet-config";

    nixpkgs.follows = "dotfiles/nixpkgs";
    sops-nix.follows = "dotfiles/sops-nix";
    disko.follows = "dotfiles/disko";

    colmena = {
      url = "github:zhaofengli/colmena";
      inputs.nixpkgs.follows = "nixpkgs";
    };

    system-manager = {
      url = "github:numtide/system-manager";
      inputs.nixpkgs.follows = "nixpkgs";
    };
  };

  outputs = inputs @ {
    self,
    dotfiles,
    nixpkgs,
    system-manager,
    ...
  }: let
    system = "x86_64-linux";
    pkgs = import nixpkgs {inherit system;};
    inventory = import ./hosts {inherit inputs pkgs system;};
  in
    dotfiles.lib.hostInventory.mkPrivateRepoOutputs {
      inherit self inputs nixpkgs system-manager inventory system;
    };
}
