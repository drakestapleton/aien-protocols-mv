#!/bin/sh
# LTP0 native conformance runner: shell glue around the unchanged
# omega-mv om2 conductor. It adds no protocol logic.
#
# Usage: sh specs/latent-payload/run-native.sh OMEGA_SRC
#   OMEGA_SRC  an omega-mv checkout; the suite runs on the omc it commits
#              (named by its seed/out/omc.sha256). The original receipts'
#              revision stays recorded in sources.json.
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
    [ -f "$src/$rel" ] || die "missing $src/$rel (OMEGA_SRC must be an omega-mv checkout)"
done

# The compiler is the one OMEGA_SRC itself commits: its seed/out/omc.sha256 names it, the
# binary must match, and the run prints both so the log records which compiler ran.
[ -f "$src/seed/out/omc.sha256" ] || die "missing $src/seed/out/omc.sha256"
# The shell builtin read takes the first field, so no helper found on PATH decides the pin.
pin=
read -r pin _rest < "$src/seed/out/omc.sha256" || [ -n "$pin" ] || die "cannot read $src/seed/out/omc.sha256"
[ ${#pin} -eq 64 ] || die "$src/seed/out/omc.sha256 does not hold a sha256: $pin"
got=$(sha256sum "$src/seed/out/omc") || die "cannot hash $src/seed/out/omc"
got=${got%% *}
[ "$got" = "$pin" ] || die "$src/seed/out/omc sha256 $got, but its seed/out/omc.sha256 says $pin"
# The revision printed is the compiler's revision only when the checkout commits these exact
# bytes: a pair edited in the work tree is refused, not labelled with the commit it is not.
rev=unknown
if rev=$(git -C "$src" rev-parse --verify -q HEAD 2>/dev/null); then
    for rel in seed/out/omc seed/out/omc.sha256; do
        want=$(git -C "$src" rev-parse -q --verify "HEAD:$rel") || die "$src HEAD does not commit $rel"
        have=$(git -C "$src" hash-object "$src/$rel") || die "cannot hash $src/$rel"
        [ "$want" = "$have" ] || die "$src/$rel differs from what $src HEAD ($rev) commits; use a clean checkout"
    done
else
    rev="unknown (not a git checkout)"
fi
printf 'run-native: omc sha256 %s (OMEGA_SRC %s)\n' "$pin" "$rev"

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
