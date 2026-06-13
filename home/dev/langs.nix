{
  config,
  lib,
  pkgs,
  ...
}: {
  home.sessionVariables = {
    # for go
    # GOPROXY = "https://goproxy.io";
  };

  home.packages = with pkgs;
    [
      #-- node
      nodejs
      typescript
      prettier
      pnpm

      #-- c
      llvmPackages.clang

      #-- rust
      rustup

      #-- python
      python3
      uv

      #-- golang
      go
      delve
      protoc-gen-go
      protoc-gen-go-grpc

      #-- lua
      lua
      luarocks

      #-- container
      dive # A tool for exploring each layer in a docker image
    ]
    ++ lib.optionals (!stdenv.hostPlatform.isDarwin) [
      pdm
    ];

  programs.go = {
    enable = true;
    env.GOPATH = "${config.home.homeDirectory}/.go";
  };

  home.file.".config/pdm/config.toml".text = ''
    [venv]
    backend = "venv"
  '';
  home.file.".cargo/config.toml".text = ''
    # On Windows
    # ```
    # cargo install -f cargo-binutils
    # rustup component add llvm-tools-preview
    # ```
    [target.x86_64-pc-windows-msvc]
    rustflags = ["-C", "link-arg=-fuse-ld=lld"]
    [target.x86_64-pc-windows-gnu]
    rustflags = ["-C", "link-arg=-fuse-ld=lld"]

    # On Linux:
    # - Ubuntu, `sudo apt-get install lld clang`
    # - Arch, `sudo pacman -S lld clang`
    [target.x86_64-unknown-linux-gnu]
    rustflags = ["-C", "linker=clang", "-C", "link-arg=-fuse-ld=lld"]

    # On MacOS
    [target.x86_64-apple-darwin]
    rustflags = ["-C", "link-arg=-fuse-ld=lld"]
    [target.aarch64-apple-darwin]
    rustflags = ["-C", "link-arg=-fuse-ld=lld"]
  '';
}
