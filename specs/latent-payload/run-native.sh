#!/bin/sh
# LTP0 native conformance runner: shell glue around the unchanged pinned
# omega-mv om2 conductor. It adds no protocol logic.
#
# Usage: sh specs/latent-payload/run-native.sh OMEGA_SRC
#   OMEGA_SRC  checkout of the omega-mv revision named in sources.json.
#              The OMEGA_SRC environment variable is used when no argument
#              is given.
#
# The conductor reads its SHA-256 constant fixtures from the fixed relative
# path seed/qualification/om2/fixtures/, and host.cases names its sources
# relative to this repository root. The runner therefore works from the
# repository root (found from its own location, not the caller's cwd),
# links build/nl3-omega and a temporary root `seed` to OMEGA_SRC, and removes
# the `seed` link again on exit. Every missing input is named before the
# conductor runs.
#
# Exit: the conductor's status (0 PASS, 1 FAIL, 3 INVALID, ...), or 2 when
# a prerequisite is missing or a path would be overwritten.

pin=d6290c7663c2b4bafb59eb3fdf812476e977f4c144def71095c6248ef9b96b84
cases=specs/latent-payload/host.cases
scratch=build/nl3-run

die() {
    printf 'run-native: %s\n' "$1" >&2
    exit 2
}

src=${1:-${OMEGA_SRC:-}}
[ -n "$src" ] || die 'usage: run-native.sh OMEGA_SRC (or set OMEGA_SRC)'
[ -d "$src" ] || die "OMEGA_SRC is not a directory: $src"
src=$(cd "$src" && pwd -P) || die "cannot resolve OMEGA_SRC: $src"

here=$(dirname "$0")
root=$(cd "$here/../.." && pwd -P) || die "cannot resolve repository root from $0"
cd "$root" || die "cannot enter repository root $root"
[ -f "$cases" ] || die "missing $root/$cases"

for rel in seed/out/omc \
    seed/qualification/om2/gate.om \
    seed/qualification/om2/fixtures/sha256-k.dec \
    seed/qualification/om2/fixtures/sha256-iv.dec \
    om/tls/sha2.om; do
    [ -f "$src/$rel" ] || die "missing $src/$rel (OMEGA_SRC must be omega-mv at the sources.json revision)"
done

got=$(sha256sum "$src/seed/out/omc") || die "cannot hash $src/seed/out/omc"
got=${got%% *}
[ "$got" = "$pin" ] || die "$src/seed/out/omc sha256 $got, expected $pin"

# Link targets: reuse a link that already points at OMEGA_SRC, refuse anything else.
link() {
    if [ -L "$2" ]; then
        [ "$(cd "$2" && pwd -P)" = "$1" ] || die "$root/$2 links elsewhere; remove it or pass that tree"
        return 1
    fi
    [ ! -e "$2" ] || die "$root/$2 exists and is not a link to $1"
    ln -s "$1" "$2" || die "cannot create link $root/$2"
}

[ ! -e "$scratch" ] || die "scratch $root/$scratch exists; remove it first"
mkdir -p build || die "cannot create $root/build"
link "$src" build/nl3-omega
if link "$src/seed" seed; then
    trap 'rm -f "$root/seed"' EXIT
    trap 'exit 130' INT TERM
fi

if build/nl3-omega/seed/out/omc < build/nl3-omega/seed/qualification/om2/gate.om > build/nl3-gate; then
    chmod +x build/nl3-gate || die "cannot chmod $root/build/nl3-gate"
else
    rc=$?
    printf 'run-native: conductor compile failed, rc=%s\n' "$rc" >&2
    exit "$rc"
fi

build/nl3-gate build/nl3-omega/seed/out/omc "$pin" "$cases" "$scratch"
