{ lib, pkgs, python3Packages, kmod }:

python3Packages.buildPythonPackage {
  pname = "unhinged";
  version = "0.0.1";
  src = ./.;

  propagatedBuildInputs = [ kmod python3Packages.pyquaternion ];
}
