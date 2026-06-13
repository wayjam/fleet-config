{
  description = "Nix configuration for wayjam";

  # the nixConfig here only affects the flake itself, not the system configuration!
  nixConfig = {
    # override the default substituters
    extra-substituters = [
      # cache mirror located in China
      # status: https://mirror.sjtu.edu.cn/
      # "https://mirror.sjtu.edu.cn/nix-channels/store"
      # status: https://mirrors.ustc.edu.cn/status/
      "https://mirrors.ustc.edu.cn/nix-channels/store"

      "https://cache.nixos.org"

      # nix community's cache server
      "https://nix-community.cachix.org"
    ];
    extra-trusted-public-keys = [
      # nix community's cache server public key
      "nix-community.cachix.org-1:mB9FSh9qf2dCimDSUo8Zy7bkq5CX+/rkCWyvRCYg3Fs="
    ];
  };

  # This is the standard format for flake.nix. `inputs` are the dependencies of the flake,
  # Each item in `inputs` will be passed as a parameter to the `outputs` function after being pulled and built.
  inputs = {
    flake-utils.url = "github:numtide/flake-utils";

    # Official NixOS package source, using nixos's unstable branch by default
    nixpkgs.url = "github:nixos/nixpkgs/nixos-unstable";
    # unstable-nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
    # nixpkgs-unstable.url = "github:nixos/nixpkgs/nixos-unstable-small";
    darwin-nixpkgs.url = "github:nixos/nixpkgs/nixpkgs-unstable";

    darwin = {
      url = "github:LnL7/nix-darwin";
      inputs.nixpkgs.follows = "darwin-nixpkgs";
    };

    # home-manager, used for managing user configuration
    home-manager = {
      url = "github:nix-community/home-manager";
      # The `follows` keyword in inputs is used for inheritance.
      # Here, `inputs.nixpkgs` of home-manager is kept consistent with the `inputs.nixpkgs` of the current flake,
      # to avoid problems caused by different versions of nixpkgs dependencies.
      inputs.nixpkgs.follows = "nixpkgs";
    };
    darwin-home-manager = {
      url = "github:nix-community/home-manager";
      inputs.nixpkgs.follows = "darwin-nixpkgs";
    };

    sops-nix = {
      # Last commit before sops-nix switched to Go 1.25 and dropped 25.05-or-older compatibility.
      url = "github:Mic92/sops-nix/17eea6f3816ba6568b8c81db8a4e6ca438b30b7c";
      inputs.nixpkgs.follows = "nixpkgs";
    };

    rime-config = {
      url = "github:Mintimate/oh-my-rime/main";
      flake = false;
    };

    impermanence.url = "github:nix-community/impermanence";

    disko = {
      url = "github:nix-community/disko";
      inputs.nixpkgs.follows = "nixpkgs";
    };
  };

  # The `outputs` function will return all the build results of the flake.
  # A flake can have many use cases and different types of outputs,
  # parameters in `outputs` are defined in `inputs` and can be referenced by their names.
  # However, `self` is an exception, this special parameter points to the `outputs` itself (self-reference)
  # The `@` syntax here is used to alias the attribute set of the inputs's parameter, making it convenient to use inside the function.
  outputs = inputs @ {
    self,
    flake-utils,
    nixpkgs,
    ...
  }: let
    utils = import ./utils.nix {inherit inputs self nixpkgs flake-utils;};
    inherit (utils) hostInventory;
    lib = nixpkgs.lib;
    hostInventoryLib = import ./lib/host-inventory.nix {inherit lib;};
  in
    flake-utils.lib.eachDefaultSystem (system: let
      pkgs = nixpkgs.legacyPackages.${system};
      isDarwin = pkgs.stdenv.hostPlatform.isDarwin;
      secretGen = pkgs.writeShellApplication {
        name = "secret-gen";
        runtimeInputs = with pkgs;
          [
            age
            openssh
            openssl
            xray
          ]
          ++ lib.optionals (!isDarwin) [
            wireguard-tools
          ];
        text = builtins.readFile ./tools/secret-gen;
      };
      fleet = pkgs.writeShellApplication {
        name = "fleet";
        runtimeInputs = with pkgs; [
          gnutar
          nix
          openssh
        ];
        text = ''
          exec ${pkgs.python3}/bin/python3 ${./tools/fleet} "$@"
        '';
      };
    in {
      formatter = pkgs.alejandra;
      packages.fleet = fleet;
      apps = {
        fleet = {
          type = "app";
          program = "${fleet}/bin/fleet";
        };
        secret-gen = {
          type = "app";
          program = "${secretGen}/bin/secret-gen";
        };
      };
    })
    // {
      lib = {
        hostInventory = hostInventoryLib;
      };

      # nixos host
      nixosConfigurations = lib.mapAttrs (hostName: host:
        utils.mkHost hostName host.system)
      hostInventory.nixos;

      # darwin host
      darwinConfigurations = lib.mapAttrs (hostName: host:
        utils.mkHost hostName host.system)
      hostInventory.darwin;

      # image
      packages = lib.mapAttrs (_system: hosts:
        lib.mapAttrs (_name: hostName:
          self.nixosConfigurations.${hostName}.config.system.build.diskoImages)
        hosts)
      hostInventory.packages;

      nixosModules = {
        default = ./modules/nixos;
        kvm-host = ./modules/nixos/profiles/kvm-host.nix;
        server-base = ./modules/shared/server/base.nix;
        server-firewall-options = ./modules/shared/server/firewall-options.nix;
        server-ssh = ./modules/nixos/server/ssh.nix;
        server-firewall = ./modules/nixos/server/firewall.nix;
        server-fail2ban = ./modules/nixos/server/fail2ban.nix;
        server-tuning = ./modules/nixos/server/tuning.nix;
        vpn-wireguard = ./modules/nixos/vpn/wireguard.nix;
        proxy-xray = ./modules/shared/proxy/xray.nix;
        proxy-hy2 = ./modules/shared/proxy/hy2.nix;
        proxy-realm = ./modules/shared/proxy/realm.nix;
        monitoring-komari-agent = ./modules/shared/monitoring/komari-agent.nix;
        web-caddy = ./modules/shared/web/caddy.nix;
      };

      systemManagerModules = {
        lxc-host = ./modules/shared/profiles/lxc-host.nix;
        server-base = ./modules/shared/server/base.nix;
        server-firewall-options = ./modules/shared/server/firewall-options.nix;
        proxy-xray = ./modules/shared/proxy/xray.nix;
        proxy-hy2 = ./modules/shared/proxy/hy2.nix;
        proxy-realm = ./modules/shared/proxy/realm.nix;
        monitoring-komari-agent = ./modules/shared/monitoring/komari-agent.nix;
      };

      # devShell
      devShells =
        nixpkgs.lib.genAttrs [
          "x86_64-linux"
          "aarch64-linux"
          "x86_64-darwin"
          "aarch64-darwin"
        ] (system: {
          default = nixpkgs.legacyPackages.${system}.mkShell {
            buildInputs = with nixpkgs.legacyPackages.${system}; [
              age
              colmena
              just
              nixos-anywhere
              sops
              ssh-to-age
            ];
          };
        });
    };
}
