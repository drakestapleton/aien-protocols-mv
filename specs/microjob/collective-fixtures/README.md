# matmul_u32 conformance fixture packet (DRA-379 / DRA-666, preparation)

Status: PROPOSED fixture packet, host only. It is not accepted by any owner and is not a qualification of
any runtime, model or device. `GAPS.md` lists what the current contract does not define; nothing in this
directory invents semantics for those items.

## What is in scope

Only behavior the current sources already define for the pure `matmul_u32` job, observed in
`specs/microjob/SPEC.md` (MJB1 section 4), `specs/aienet/jobpath/PROFILE.md` (AN0B bundle, admission order,
job definition), `crates/aien-microjob/src/aienet0.rs` (Rust reference) and
`specs/aienet/jobpath/matmul_u32_recompute.om` (the Omega consumer):

- the 15-byte payload (`kind` 1, `m`,`k`,`n` u16 BE, `seed` u64 BE) and its output digest;
- the one-node MJB1 profile document and every static refusal of SPEC section 4.4 reachable from it;
- the AN0B bundle framing and the profile's admission order, with refusals.

Not in scope here: MJR1 receipts, AN0V verdicts, carrier frames, replay, cancellation, attempts, leases.
See `GAPS.md`.

## Files

| Path | Role |
|---|---|
| `vectors/payload-positive.tsv` | payload bytes and expected output digest, work and memory per case |
| `vectors/payload-negative.tsv` | malformed, truncated, oversize, wrong-kind, zero and over-bound payloads: expected Omega consumer exit status and expected Rust `decode` result, side by side |
| `vectors/document.tsv` | golden one-node MJB1 documents and single-byte mutants with the first refusal code SPEC 4.4 requires |
| `vectors/bundle.tsv` | signed AN0B bundles: positive, framing, signature, expiry, allowlist, binding, bound and cap refusals |
| `oracle/oracle.py` | independent oracle (test instrument only, Python stdlib + `cryptography` for ECDSA verify). Spec-derived digest/document/signature checks with a third loop order for matmul; refusal order is explicitly observed consumer behavior |
| `run-host.sh` | host runner and controls |
| `oracle/rust-probe/` | rebuildable external reference instrument with locked dependencies; no production use |

`oracle.py generate DIR` rewrites the vectors. Documents and payloads are deterministic. Bundle signatures
come from OpenSSL ECDSA and are not deterministic, so `bundle.tsv` stores the signatures it was generated
with and every check verifies them; regenerating produces different bundle bytes and the same verdicts.

## Run

```
flock -n <assigned queen pool lock> taskset -c <core> ./run-host.sh
cargo build --offline --locked --release --manifest-path oracle/rust-probe/Cargo.toml
RUST_PROBE="$PWD/oracle/rust-probe/target/release/ocf-probe" ./run-host.sh
```

The runner takes the compiler (`seed/out/omc`) and the SHA-256 unit from `main` of `~/git/omega-mv.git`
(`OMEGA_MV_GIT` overrides) at run time and prints their head and hashes, so no pin is typed in this
directory. Exit 0 requires every comparison to agree and every control to be detected; exit 3 is NOT_RUN.

Comparisons, each independent of the others:

1. oracle requires the full generated case identity set without missing, extra or duplicate rows, then re-derives every vector;
2. Omega consumer (built with that compiler) against every payload row, positive and negative;
3. historical Core #662 digests in `evidence/aienet0-20261028/xcheck662.log` against the Omega consumer;
4. the C reference checker `specs/microjob/tools/mjb_verify.c` against every document row;
5. a Rust probe linked to `crates/aien-microjob` against every row (decode, document check,
   `admit_bundle` with real P-256 verification).

Controls (each must be detected): a wrong expected digest, a wrong expected refusal, three mutated Omega
consumers (domain string, splitmix64 shift, dimension bound), a wrong expected admission for the Rust probe, missing negative cases, and duplicate negative cases. A node-expired/header-live bundle checks node expiry independently.

## Observed difference between the two consumers

For payloads of the wrong length or kind the Omega consumer checks length, then kind, then dimensions
(exit 2, 3, 4). The Rust `MatmulU32::decode` checks kind, then length. An empty payload, or a wrong-length
payload of another kind, therefore gives exit 2 in Omega and `AN0_NOT_ALLOWLISTED` in Rust. Both orders are
recorded in `payload-negative.tsv`; which one is the contract is gap G4.

## Evidence classes

Host fixture and host comparison only. No physical transport, no device, no GPU, no model. Native Omega
MJB1/MJR1 document parity is NOT_RUN (G8).

The existing `tests/gates/run.sh c-vectors` discovers `specs/microjob/tools/check-collective.sh`, which builds the locked reference probe offline in an isolated temporary target and runs this packet. Missing tools or the local Omega source store return NOT_RUN (a nonzero gate result). Python, cryptography, C and Rust are external test instruments only, never dependencies of a trusted production path. The runner prints the source head, dirty-source fingerprint, vector/oracle/runner/probe hashes and tool versions. Rust-builder byte parity remains outside this runner; it compares document admission and digest, not builder output.
