{
  inputs,
  self,
  nixpkgs,
  flake-utils,
}: let
  hostInventory = {
    nixos = {
      bootstrap.system = "aarch64-linux";
      angel.system = "x86_64-linux";
      example-host.system = "x86_64-linux";
    };

    darwin = {
      jamjar-mb4.system = "aarch64-darwin";
    };

    packages = {
      aarch64-linux.bootstrap = "bootstrap";
    };
  };

  loadHostConfig = {
    nixpkgs,
    hostName,
    system,
  }: let
    hostPath = ./hosts/${hostName};
    configFile =
      if nixpkgs.lib.pathExists (hostPath + "/default.nix")
      then hostPath + "/default.nix"
      else hostPath + ".nix";
    importedConfig = import configFile {inherit nixpkgs hostName system;};
  in
    if nixpkgs.lib.isFunction importedConfig
    then importedConfig {} # 假设不需要额外参数调用
    else importedConfig;

  # 定义 mkHost 函数
  # 它只需要 hostName 和 system 作为直接参数
  # 其他依赖项通过外层传入的 'inputs' 和 'self' 访问
  mkHost = hostName: system: let
    # 通过 inputs 访问依赖
    isDarwin = builtins.elem system inputs.nixpkgs.lib.platforms.darwin;
    specifics =
      {
        nixos = {
          nixpkgs = inputs.nixpkgs;
          nixSystem = inputs.nixpkgs.lib.nixosSystem;
          modules = [
            inputs.home-manager.nixosModules.home-manager
            ./modules/nixos # 路径相对于 utils.nix
          ];
        };
        darwin = {
          nixpkgs = inputs.darwin-nixpkgs;
          nixSystem = inputs.darwin.lib.darwinSystem;
          modules = [
            inputs.darwin-home-manager.darwinModules.home-manager
            ./modules/darwin # 路径相对于 utils.nix
          ];
        };
      }
      .${
        if isDarwin
        then "darwin"
        else "nixos"
      };

    # 调用上面定义的 loadHostConfig
    hostConfig = loadHostConfig {
      inherit (specifics) nixpkgs; # 传递正确的 nixpkgs (nixos 或 darwin 的)
      inherit hostName system;
    };

    # 使用正确的 nixpkgs 创建 lib
    lib = specifics.nixpkgs.lib.extend (final: prev: {
      # …
    });

    # 使用传入的 inputs 创建 freezeRegistry
    freezeRegistry = {
      nix.registry = lib.mkForce (lib.mapAttrs (_: flake: {inherit flake;}) inputs);
    };

    hostRootModule =
      {
        system.configurationRevision =
          if (self ? rev) # 使用传入的 self
          then self.rev
          else null;
      }
      // hostConfig.root;

    homeManagerModules = [
      ({config, ...}: {
        home-manager = {
          backupFileExtension = "backup";
          useGlobalPkgs = true;
          useUserPackages = true;
          users.${hostConfig.myvars.userName} = import ./home;
          extraSpecialArgs = {
            inherit isDarwin;
            inherit (hostConfig) myvars;
            rime-config = inputs.rime-config;
          };
        };
      })
    ];

    # 调用基础系统构建函数
    baseSystemConfig = specifics.nixSystem {
      inherit system;

      specialArgs = {
        inherit (specifics) nixpkgs;
        inherit isDarwin hostName lib;
        inherit (hostConfig) myvars;
        # 通过 inputs 访问
        impermanence = inputs.impermanence;
        disko = inputs.disko;
      };

      modules =
        [
          ./modules/nix-core.nix
          freezeRegistry
        ]
        ++ specifics.modules
        ++ [
          hostRootModule
          hostConfig.module
        ]
        ++ homeManagerModules;
    };
    # 无条件地为所有 host 添加 .system 属性
  in
    baseSystemConfig
    // {
      system = baseSystemConfig.config.system.build.toplevel;
    };
  # 返回包含两个函数的属性集
in {
  inherit hostInventory loadHostConfig mkHost;
  forAllSystems = flake-utils.lib.eachDefaultSystem;
}
