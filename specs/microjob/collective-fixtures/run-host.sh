#!/bin/bash
# Host-only conformance run of the matmul_u32 fixture packet. No network, no GPU, no service.
#   OMEGA_MV_GIT  bare omega-mv repository (default ~/git/omega-mv.git). The compiler and the SHA-256 unit are
#                 taken from its `main` at run time, so no pin is typed here; the head and hashes are printed.
#   RUST_PROBE    optional executable: reads "pdec HEX" / "ddec HEX" / "admit HEX KEYSEED NOW" lines (reference probe).
# Exit: 0 all agree and every control was discriminating; 1 disagreement or non-discriminating control; 3 NOT_RUN.
# Run it as: flock -n QUEEN_POOL_LOCK taskset -c CORE ./run-host.sh
set -u
set -o pipefail
export LC_ALL=C
HERE=$(cd "$(dirname "$0")" && pwd)
ROOT=$(cd "$HERE/../../.." && pwd)
MV=${OMEGA_MV_GIT:-$HOME/git/omega-mv.git}
T=$(mktemp -d); trap 'rm -rf "$T"' EXIT
fail=0; pass=0
ok() { pass=$((pass+1)); }
bad() { fail=$((fail+1)); echo "FAIL $*"; }
notrun() { echo "NOT_RUN: $*"; exit 3; }
for t in xxd python3 gcc git sha256sum; do command -v $t >/dev/null || notrun "missing $t"; done

HEAD=$(git --git-dir="$MV" rev-parse main) || notrun "no omega-mv main"
git --git-dir="$MV" show "$HEAD":seed/out/omc > "$T/omc" && chmod +x "$T/omc" || notrun "no omc on main"
git --git-dir="$MV" show "$HEAD":om/sha256/sha256-om2.om > "$T/sha.om" || notrun "no SHA unit on main"
echo "omega-mv main=$HEAD omc_sha256=$(sha256sum < "$T/omc" | cut -c1-64) sha_unit_sha256=$(sha256sum < "$T/sha.om" | cut -c1-64)"
echo "protocols_head=$(git -C "$ROOT" rev-parse HEAD)"
echo "protocols_diff_sha256=$(git -C "$ROOT" diff --binary HEAD -- specs/microjob specs/aienet/jobpath crates/aien-microjob | sha256sum | cut -c1-64)"
git -C "$ROOT" ls-files -- specs/microjob/collective-fixtures specs/microjob/tools/check-collective.sh | while IFS= read -r file; do sha256sum "$ROOT/$file"; done
python3 --version
python3 -c 'import cryptography; print("cryptography=" + cryptography.__version__)' || notrun "missing cryptography oracle dependency"
gcc --version | head -n 1
echo "microjob SPEC.md sha256=$(sha256sum < "$ROOT/specs/microjob/SPEC.md" | cut -c1-64) consumer .om sha256=$(sha256sum < "$ROOT/specs/aienet/jobpath/matmul_u32_recompute.om" | cut -c1-64)"
sed 's/^export fn /fn /' "$T/sha.om" > "$T/unit.om"   # program mode has no exports; the only edit, as jobpath/build.sh does

build() { # $1 consumer source, $2 out
  cat "$T/unit.om" "$1" > "$T/src.om" && "$T/omc" < "$T/src.om" > "$2" && chmod +x "$2"
}
build "$ROOT/specs/aienet/jobpath/matmul_u32_recompute.om" "$T/mm" || notrun "consumer did not compile"
echo "consumer binary sha256=$(sha256sum < "$T/mm" | cut -c1-64)"
gcc -std=c99 -O2 -Wall -Wextra -Werror -pedantic -o "$T/mjb_verify" "$ROOT/specs/microjob/tools/mjb_verify.c" || notrun "C checker did not build"

V=${VECTORS:-$HERE/vectors}
for input in "$V"/*.tsv; do sha256sum "$input" || notrun "missing vector input"; done
if [ -n "${RUST_PROBE:-}" ]; then sha256sum "$RUST_PROBE" || notrun "missing Rust reference executable"; fi
sha256sum "$T/mjb_verify" "$ROOT/specs/microjob/tools/mjb_verify.c"
run_payloads() { # $1 binary, $2 vectors dir; prints mismatch count of positives+negatives
  local mis=0 id hex exp got rc
  while IFS=$'\t' read -r id m k n seed hex dig w mem note; do
    case $id in \#*|"") continue;; esac
    got=$(printf '%s' "$hex" | xxd -r -p | "$1"); rc=$?
    [ "$rc" = 0 ] && [ "$got" = "$dig" ] || { mis=$((mis+1)); echo "  payload-positive $id rc=$rc got=$got want=$dig" >&2; }
  done < "$2/payload-positive.tsv"
  while IFS=$'\t' read -r id hex omx rust note; do
    case $id in \#*|"") continue;; esac
    [ "$hex" = "-" ] && hex=""
    got=$(printf '%s' "$hex" | xxd -r -p | "$1"); rc=$?
    case $omx in exit*) want=${omx#exit}; [ "$rc" = "$want" ] && [ -z "$got" ] || { mis=$((mis+1)); echo "  payload-negative $id rc=$rc out=$got want=$omx" >&2; };; *) mis=$((mis+1));; esac
  done < "$2/payload-negative.tsv"
  echo $mis
}
echo "== oracle self-check"
python3 "$HERE/oracle/oracle.py" check "$V" && ok || bad "oracle check"

echo "== Omega consumer vs vectors"
n=$(run_payloads "$T/mm" "$V"); [ "$n" = 0 ] && ok || bad "omega consumer: $n mismatches"
echo "payload rows: $(grep -vc '^#' "$V/payload-positive.tsv") positive, $(grep -vc '^#' "$V/payload-negative.tsv") negative; mismatches=$n"

echo "== historical Core #662 digests (evidence/aienet0-20261028/xcheck662.log) vs oracle and Omega consumer"
H=$ROOT/evidence/aienet0-20261028/xcheck662.log; hm=0; hn=0
if [ -f "$H" ]; then
  while read -r m k n seed rest; do
    case $m in *[!0-9]*|"") continue;; esac
    want=$(printf '%s' "$rest" | sed -n 's/^core662=\([0-9a-f]*\) .*/\1/p'); [ -n "$want" ] || continue
    pay=$(python3 -c "import struct,sys;print(struct.pack('>BHHHQ',1,$m,$k,$n,$seed).hex())")
    got=$(printf '%s' "$pay" | xxd -r -p | "$T/mm"); rc=$?; hn=$((hn+1))
    [ "$rc" = 0 ] && [ "$got" = "$want" ] || { hm=$((hm+1)); echo "  historical $m $k $n $seed want=$want got=$got"; }
  done < "$H"
  echo "historical rows=$hn mismatches=$hm"; [ "$hn" -ge 1 ] && [ "$hm" = 0 ] && ok || bad "historical digests"
else notrun "historical log absent"; fi

doc_check() { # $1 vectors dir; prints "rows mismatches"
  local mis=0 rows=0 id hex exp dg note line rc
  while IFS=$'\t' read -r id hex exp dg note; do
    case $id in \#*|"") continue;; esac
    rows=$((rows+1)); [ "$hex" = "-" ] && hex=""
    printf '%s' "$hex" | xxd -r -p > "$T/doc.bin"
    line=$("$T/mjb_verify" "$T/doc.bin" 2>/dev/null); rc=$?
    if [ "$exp" = ok ]; then [ "$rc" = 0 ] || mis=$((mis+1)); else [ "$rc" = 1 ] || mis=$((mis+1)); fi
    case $exp in
      ok) case $line in "ok nodes="*"digest=$dg "*|"ok nodes="*"digest=$dg") ;; *) mis=$((mis+1)); echo "  doc $id want ok digest=$dg got: $line" >&2;; esac;;
      *) [ "$line" = "refuse $exp" ] || { mis=$((mis+1)); echo "  doc $id want $exp got: $line" >&2; };;
    esac
  done < "$1/document.tsv"
  echo "$rows $mis"
}
echo "== C checker vs document vectors"
set -- $(doc_check "$V"); echo "document rows: $1; mismatches=$2"; [ "$1" -ge 1 ] && [ "$2" = 0 ] && ok || bad "C checker: $2 mismatches"

rust_check() { # $1 vectors dir; prints mismatch count
  local mis=0 id hex omx rust note exp dg pin now got want m k n seed w mem
  while IFS=$'\t' read -r id m k n seed hex dg w mem note; do case $id in \#*|"") continue;; esac
    got=$(echo "pdec ${hex}" | "$RUST_PROBE"); [ "$?" = 0 ] || { mis=$((mis+1)); continue; }
    [ "$got" = "OK in_bounds=true work=$w memory=$mem digest=$dg" ] || { mis=$((mis+1)); echo "  rust digest $id got=$got want=$dg" >&2; }
  done < "$1/payload-positive.tsv"
  while IFS=$'\t' read -r id hex omx rust note; do case $id in \#*|"") continue;; esac
    [ "$hex" = "-" ] && hex=""
    got=$(echo "pdec ${hex}" | "$RUST_PROBE" | cut -d' ' -f1); [ "$?" = 0 ] || { mis=$((mis+1)); continue; }
    want=$rust; [ "$want" = decode_ok_then_AN0_OVER_BUDGET ] && want=OK; [ "$want" = decode_ok ] && want=OK
    [ "$got" = "$want" ] || { mis=$((mis+1)); echo "  rust decode $id got=$got want=$want" >&2; }
  done < "$1/payload-negative.tsv"
  while IFS=$'\t' read -r id hex exp dg note; do case $id in \#*|"") continue;; esac
    got=$(echo "ddec ${hex}" | "$RUST_PROBE"); [ "$?" = 0 ] || { mis=$((mis+1)); continue; }; [ "$got" = "OK dag_digest=$dg" ] && got=ok
    [ "$got" = "$exp" ] || { mis=$((mis+1)); echo "  rust document $id got=$got want=$exp" >&2; }
  done < "$1/document.tsv"
  while IFS=$'\t' read -r id hex pin now exp note; do case $id in \#*|"") continue;; esac
    [ "$hex" = "-" ] && hex=""
    got=$(echo "admitkey ${hex} ${pin} ${now}" | "$RUST_PROBE" | sed 's/^OK /ok /'); [ "$?" = 0 ] || { mis=$((mis+1)); continue; }
    [ "$got" = "$exp" ] || { mis=$((mis+1)); echo "  rust bundle $id got=$got want=$exp" >&2; }
  done < "$1/bundle.tsv"
  echo $mis
}
if [ -n "${RUST_PROBE:-}" ]; then
  echo "== Rust reference probe (RUST_PROBE=$RUST_PROBE)"
  mis=$(rust_check "$V"); echo "rust probe mismatches=$mis"; [ "$mis" = 0 ] && ok || bad "rust probe: $mis mismatches"
else
  echo "== Rust reference probe: NOT_RUN (RUST_PROBE unset)"
fi

echo "== discriminating controls (each must be detected)"
# C1: a wrong expected digest in a copy of the vectors must be caught by the Omega consumer.
mkdir -p "$T/v1"; cp "$V"/* "$T/v1/"
awk 'BEGIN{FS=OFS="\t"} !/^#/ && !d {sub(/^./,(substr($7,1,1)=="0"?"1":"0"),$7); d=1} {print}' "$T/v1/payload-positive.tsv" > "$T/v1/p" && mv "$T/v1/p" "$T/v1/payload-positive.tsv"
n=$(run_payloads "$T/mm" "$T/v1" 2>/dev/null); [ "$n" -ge 1 ] && ok || bad "control C1 not detected"
# C2: a wrong expected refusal in a copy of the document vectors must be caught by the same comparison.
cp "$V/document.tsv" "$T/v1/document.tsv"; sed -i '0,/\tMJB_BAD_MAGIC\t/s//\tMJB_BAD_COUNT\t/' "$T/v1/document.tsv"
set -- $(doc_check "$T/v1" 2>/dev/null); [ "$2" -ge 1 ] && ok || bad "control C2 not detected"
# C3/C4: mutated consumers (domain string; splitmix64 shift; wrapping loop order irrelevant) must fail the positives.
S=$ROOT/specs/aienet/jobpath/matmul_u32_recompute.om
sed 's/AIEN-HETJOB-MATMUL-U32-V1/AIEN-HETJOB-MATMUL-U32-V2/' "$S" > "$T/m3.om"
sed 's/z = xor z shr z 27/z = xor z shr z 28/' "$S" > "$T/m4.om"
sed 's/gt m 256/gt m 255/' "$S" > "$T/m5.om"
for c in 3 4 5; do
  [ "$(cmp -s "$S" "$T/m$c.om" && echo same)" = same ] && { bad "control C$c mutation did not apply"; continue; }
  if build "$T/m$c.om" "$T/mm$c"; then n=$(run_payloads "$T/mm$c" "$V" 2>/dev/null); [ "$n" -ge 1 ] && ok || bad "control C$c mutant consumer not detected"; else bad "control C$c mutant did not compile"; fi
done
if [ -n "${RUST_PROBE:-}" ]; then # C6: the Rust comparison must notice a wrong expectation
  cp "$V/bundle.tsv" "$T/v1/bundle.tsv"; sed -i '0,/\tok dag_digest=/s//\tAN0_BAD_BUNDLE_X /' "$T/v1/bundle.tsv"
  cp "$V/payload-positive.tsv" "$T/v1/payload-positive.tsv"; cp "$V/document.tsv" "$T/v1/document.tsv"; cp "$V/payload-negative.tsv" "$T/v1/payload-negative.tsv"
  n=$(rust_check "$T/v1" 2>/dev/null); [ "$n" -ge 1 ] && ok || bad "control C6 not detected"
fi
# Missing or duplicated cases must not turn a reduced packet into a successful full run.
for control in missing duplicate; do
  mkdir -p "$T/$control"; cp "$V"/* "$T/$control/"
  if [ "$control" = missing ]; then
    awk '!/^#/ && !d {d=1; next} {print}' "$V/payload-negative.tsv" > "$T/$control/payload-negative.tsv"
  else
    awk '{print} !/^#/ && !d {print; d=1}' "$V/payload-negative.tsv" > "$T/$control/payload-negative.tsv"
  fi
  python3 "$HERE/oracle/oracle.py" check "$T/$control" > "$T/$control.out" 2>&1; rc=$?
  [ "$rc" = 1 ] && grep -q 'ORACLE_FAIL coverage payload-negative.tsv' "$T/$control.out" && ok || bad "control $control coverage not detected"
done
echo "RESULT pass=$pass fail=$fail"
[ "$fail" = 0 ] || exit 1
# Fail closed: bundle admission is otherwise checked only by the oracle that generated the rows.
[ -n "${RUST_PROBE:-}" ] || { echo "NOT_RUN: Rust reference probe absent; bundle rows are not independently checked (exit 3)"; exit 3; }
