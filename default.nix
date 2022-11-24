{ lib, pkgs, python3Packages }:

python3Packages.buildPythonPackage {
  pname = "unhinged";
  version = "0.0.1";
  src = ./.;
}
