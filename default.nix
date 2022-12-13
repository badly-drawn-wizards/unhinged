{ lib, pkgs, python3Packages, kmod }:

python3Packages.buildPythonPackage {
  pname = "unhinged";
  version = "0.0.1";
  src = ./.;

  buildInputs = with python3Packages; [pyquaternion];
  propagatedBuildInputs = [ kmod ];
}
