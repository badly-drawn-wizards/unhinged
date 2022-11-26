{ config, lib, pkgs, ... }:

let
  inherit (lib) types;
  cfg = config.services.unhinged;
  pkg = cfg.package;
in
{
  options = with lib.types; {
    services.unhinged = {
      enable = lib.mkEnableOption "unhinged service";
      package = lib.mkOption {
        default = pkgs.unhinged;
        type = types.package;
        description = ''The package for the unhinged daemon'';
      };
    };
  };

  config = {
    systemd.services.unhinged = lib.mkIf cfg.enable {
      description = "Unhinged service";
      wantedBy = [ "multi-user.target" ];
      serviceConfig = {
        ExecStart = "${pkg}/bin/unhinged.py";
      };
    };
  };

}
