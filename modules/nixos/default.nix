{...}: {
  imports = [
    ./core.nix
    ./host-users.nix
    ./i18n.nix
    ./packages.nix
    ./secrets/sops-age-key.nix
  ];
}
