{
  inputs.utils.url = "github:numtide/flake-utils";
  outputs = { nixpkgs, utils, ... }:
    let
      pkg = ./default.nix;
      overlay = (self: super: {
        unhinged = self.callPackage pkg {};
      });
      module = ({...}: {
        imports = [ ./module.nix ];
        nixpkgs.overlays = [ overlay ];
      });
    in {
      inherit overlay;
      nixosModules.unhinged = module;
    } // utils.lib.eachDefaultSystem (system:
      let
        pkgs = import nixpkgs { inherit system; overlays = [overlay]; };
        inherit (pkgs) unhinged;
      in {
        packages = {
          inherit unhinged;
        };
        devShell = pkgs.mkShell {
          packages = [
            (pkgs.python3.withPackages
              (ps: (ps.callPackage pkg {}).buildInputs))
          ];
        };
        defaultPackage = pkgs.unhinged;
      }
    );
}
