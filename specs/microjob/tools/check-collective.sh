#!/usr/bin/env bash
# External verification instrument, discovered by the existing c-vectors gate.
set -euo pipefail
ROOT=$(cd "$(dirname "$0")/../../.." && pwd)
PKT=$ROOT/specs/microjob/collective-fixtures
for tool in cargo rustc; do command -v "$tool" >/dev/null || { echo "NOT_RUN: missing $tool"; exit 3; }; done
cargo --version
rustc --version
mkdir -p "$ROOT/target"
TASK=$(mktemp -d "$ROOT/target/collective-fixtures.XXXXXXXX")
trap 'rm -rf "$TASK"' EXIT
cargo build --offline --locked --release --manifest-path "$PKT/oracle/rust-probe/Cargo.toml" --target-dir "$TASK"
RUST_PROBE="$TASK/release/ocf-probe" bash "$PKT/run-host.sh"
