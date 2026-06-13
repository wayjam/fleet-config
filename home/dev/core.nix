{pkgs, ...}: {
  home.packages = with pkgs; [
    age
    sops
    ssh-to-age

    # misc
    protobuf
    httpie
    buf
    universal-ctags
    global
  ];
}
