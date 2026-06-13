# set options
set positional-arguments := true
set dotenv-load := true

# from .env
profile := "$PROFILE"

# List all the just commands
default:
  @just --list


############################################################################
#
#  Darwin related commands
#
############################################################################

# Rebuild and Switch to profile
[macos]
[group('darwin')]
darwin-build host=profile:
  nix build .#darwinConfigurations.{{host}}.system

  sudo ./result/sw/bin/darwin-rebuild switch --flake .#{{host}}

# Rebuild and Switch to profile(trace & verbose mode)
[macos]
[group('darwin')]
darwin-debug host=profile:
  nix build .#darwinConfigurations.{{host}}.system --show-trace --print-build-logs --verbose

  sudo ./result/sw/bin/darwin-rebuild switch --flake .#{{host}} --show-trace --print-build-logs --verbose --dry-run

############################################################################
#
#  nixos related commands
#
############################################################################

[group('nixos')]
nixos-debug host=profile:
  nix build .#nixosConfigurations.{{host}}.system --show-trace --print-build-logs --verbose

nixos-image host=profile:
  nix build '.#packages.aarch64-linux.{{host}}' --system aarch64-linux --show-trace --print-build-logs --verbose


############################################################################
#
#  common nix commands
#
############################################################################

# Update all the flake inputs
[group('common')]
up:
  nix flake update

# Update specific input
# Usage: just upp nixpkgs
[group('common')]
upp input:
  nix flake update {{input}}

# List all generations of the system profile
[group('common')]
history:
  nix profile history --profile /nix/var/nix/profiles/system

# Open a nix shell with the flake
[group('common')]
repl:
  nix repl -f flake:nixpkgs

# remove all generations older than 7 days
# on darwin, you may need to switch to root user to run this command
[group('common')]
clean:
  sudo nix profile wipe-history --profile /nix/var/nix/profiles/system  --older-than 7d

# Garbage collect all unused nix store entries
[group('common')]
gc:
  # garbage collect all unused nix store entries(system-wide)
  sudo nix-collect-garbage --delete-older-than 7d
  # garbage collect all unused nix store entries(for the user - home-manager)
  # https://github.com/NixOS/nix/issues/8508
  nix-collect-garbage --delete-older-than 7d

[group('common')]
fmt:
  # format the nix files in this repo
  nix fmt

# Show all the auto gc roots in the nix store
[group('common')]
gcroot:
  ls -al /nix/var/nix/gcroots/auto/


############################################################################
#
#  git related commands
#
############################################################################

# Stash & Pull & Pop
[group('git')]
git-temp:
  @git stash save 'temp'
  @git pull --rebase
  @git stash pop

# Calc Github Sha256
[group('git')]
prefetch-gh owner repo rev="HEAD":
    #!/usr/bin/env bash
    json=$(nix-prefetch-github --no-deep-clone --quiet --rev {{ rev }} {{ owner }} {{ repo }})
    owner=$(echo "$json" | jq -r '.owner')
    repo=$(echo "$json" | jq -r '.repo')
    rev=$(echo "$json" | jq -r '.rev' | cut -c 1-8)
    hash=$(echo "$json" | jq -r '.hash')
    cat <<EOF
    pkgs.fetchFromGitHub {
      owner = "$owner";
      repo  = "$repo";
      rev   = "$rev";
      hash  = "$hash";
    };
    EOF
