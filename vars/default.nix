{lib, ...}: rec {
  # User specific variables
  userName = "wayjam";
  userFullName = "WayJam So";
  userEmail = "imsuwj@gmail.com";
  userSigningKey = "";

  # Networking
  networking = import ./networking.nix {inherit lib;};

  # Security
  # Keep real password hashes in the private inventory repo. Public SSH keys are
  # safe to reuse from this public module.
  hashedPassword = null;
  sshAuthorizedKeys = [
    "ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAACAQCzjSosCVgOZT8FQblRsHfEt+VRUv5BvmjNf67nIGBdFfKL+97qqh0ORJS5KviKMBxJXWyiYd+qGnk9oUw0efRw1sn4QMru3HvaK7D77Gafse9MF2c4goYRiDVmFPmzwWPtu4pQME4A+P+dcX+BdriI9ew44fkJaQ6TedCzsyc8P+C4zeg2daATJ/zaw2aSrxl+K7tA0wlIAQ0W5Ha4/KpGeYf5JCseGheysQ9rsdVqENBe7AO0qiwkmCizp2enxdqM0u1q1iTM9Hb70QN8xr9c9Xc9We1L+p4oeslhflLbfqJNpr8cEihBekK5EaElk4B6O7vMm/snuG/C+oMojzMDOtJZXZfy3pEApKKdfBLfhuxx6klETZRAg/RtqnT755HgaqlUwpPecsX3b51c1SWGCpyOzyxxApUJz016tIbMN8OCUPCdkd7IP4rIczr/EhS0rz0gC1YSsMME2600pYnbFPL8XxK4uvcbhjtxfB7nZVnCY9wY+LZDPUvL+UXeqqdE4jT2i/q7QtFlYH+Uev+BC6v8EUdrTxPj0ODHNUD02/0qsb7Eko43F9IAj8wgClX/lvFFoc8xu0NVYOni7mgyXeoRA+27XS+PtwJl3kr9bKr9z7gVOq6YZLLrl+JOI9aEKKgKl5YPVrN4LwqodvLQJ3NHEZ0f7YpX27Y4nWpoyQ=="
    "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAINkeEP02um5ZHvKuRhQmGKhYyyGesUpQDHwaQksnpdOk root@builder"
  ];
}
