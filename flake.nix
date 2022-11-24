{
  inputs.utils.url = "github:numtide/flake-utils";
  outputs = { nixpkgs, utils, ... }:
    let
      overlay = (self: super: {
        unhinged = self.callPackage ./default.nix {};
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
      in {
        packages = {
          unhinged = pkgs.unhinged;
        };
        defaultPackage = pkgs.unhinged;
      }
    );
}
