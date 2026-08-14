{
  description = "Lecturer dev shell";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
    flake-utils.url = "github:numtide/flake-utils";
  };

  outputs = { self, nixpkgs, flake-utils }:
    flake-utils.lib.eachDefaultSystem (system:
      let
        pkgs = nixpkgs.legacyPackages.${system};
      in
      {
        devShells.default = pkgs.mkShell {
          # uv manages the Python interpreter and every project dependency
          # (see uv.lock) itself — nothing Python-related belongs here, or a
          # venv ends up built against a nix store path that moves out from
          # under it on the next nixpkgs update or GC.
          packages = [
            # headless: only the CLI muxes .m4b chapters, no GUI/X11 build needed
            pkgs.ffmpeg-headless
            pkgs.uv
            pkgs.just
          ];
        };
      });
}
