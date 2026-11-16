#!/usr/bin/env python3
# TEST INSTRUMENT ONLY (not production, not a protocol implementation).
# Independent oracle for the matmul_u32 conformance packet. Written from
# specs/microjob/SPEC.md sections 3-4 and specs/aienet/jobpath/PROFILE.md, not
# from the Rust or Omega sources. Python stdlib plus `cryptography` (signature
# verification only).
#   oracle.py generate DIR   write vectors (bundle signatures are fresh; documents/payloads deterministic)
#   oracle.py check DIR      re-derive and compare; verify every bundle signature independently
import hashlib, struct, sys, os

U64 = (1 << 64) - 1
DOMAIN = b"AIEN-HETJOB-MATMUL-U32-V1"
MAXD = 256
NOW = 1_800_000_000
NONCE = bytes(range(0xA0, 0xB0))
P256_N = 0xFFFFFFFF00000000FFFFFFFFFFFFFFFFBCE6FAADA7179E84F3B9CAC2FC632551

def sha(*p):
    h = hashlib.sha256()
    for x in p: h.update(x)
    return h.digest()

def smix(st):
    st = (st + 0x9E3779B97F4A7C15) & U64
    z = st
    z = ((z ^ (z >> 30)) * 0xBF58476D1CE4E5B9) & U64
    z = ((z ^ (z >> 27)) * 0x94D049BB133111EB) & U64
    return st, z ^ (z >> 31)

def digest(m, k, n, seed):
    s = seed
    a = []; b = []
    for _ in range(m * k):
        s, v = smix(s); a.append(v & 0xFFFFFFFF)
    for _ in range(k * n):
        s, v = smix(s); b.append(v & 0xFFFFFFFF)
    out = bytearray()
    for i in range(m):                      # i-j-k: a third loop order, independent of both implementations
        for j in range(n):
            acc = 0
            for p in range(k):
                acc = (acc + a[i * k + p] * b[p * n + j]) & 0xFFFFFFFF
            out += struct.pack(">I", acc)
    return sha(DOMAIN, struct.pack(">HHHQ", m, k, n, seed), bytes(out))

def payload(m, k, n, seed, kind=1):
    return struct.pack(">BHHHQ", kind, m, k, n, seed)

# ---- payload contract (PROFILE.md "The job"): 15 bytes, kind 1, dims 1..256 ----
def payload_work(m, k, n): return m * k * n
def payload_mem(m, k, n): return 4 * (m * k + k * n + m * n)

def model_om_consumer(p):
    """matmul_u32_recompute.om documented behaviour: length, then kind, then dims; else digest."""
    if len(p) != 15: return "exit2"
    if p[0] != 1: return "exit3"
    m, k, n, seed = struct.unpack(">HHHQ", p[1:])
    if min(m, k, n) == 0 or max(m, k, n) > MAXD: return "exit4"
    return "ok " + digest(m, k, n, seed).hex()

def model_rust_decode(p):
    """MatmulU32::decode + in_bounds as documented in aienet0.rs: kind first, then length."""
    if len(p) == 0 or p[0] != 1: return "AN0_NOT_ALLOWLISTED"
    if len(p) != 15: return "AN0_BAD_BUNDLE"
    m, k, n, seed = struct.unpack(">HHHQ", p[1:])
    return "decode_ok"

# ---- MJB1 document (SPEC section 4) ----
def le_(b): return b
def build_node(**o):
    f = dict(job_id=sha(b"AIENET0-JOB-V1\0", NONCE)[:16], idem=sha(b"AIENET0-IDEM-V1\0", NONCE)[:16], generation=1,
             kind=1, op=2, profile=0, effect=1, in_tok=0, out_tok=0, req_in=0, req_out=0, verifier=1, retry=1,
             attempts=1, cancel=1, precision=0, substrate=1, dep_count=0, operand_count=1, result_type=7,
             result_rank=0, pure=1, reserved1=0, time_ms=120000, fuel=1, memory=1, work=1, expires=NOW + 3600,
             dims=[0, 0, 0, 0], capability=sha(b"AIENET0-CAPABILITY-MATMUL-U32-V1"), tenant=sha(b"AIENET0-TENANT-TUR-TEST-V1"),
             model_ref=bytes(32), verifier_ref=bytes(32), deps=bytes(48),
             operands=None)
    f.update(o)
    if f["operands"] is None:
        f["operands"] = bytes([3, 0, 0, 0]) + struct.pack(">I", 1) + sha(b"") + bytes(120)
    n = (f["job_id"] + f["idem"] + struct.pack(">I", f["generation"]) +
         bytes([f["kind"], f["op"], f["profile"], f["effect"]]) +
         struct.pack(">HHHH", f["in_tok"], f["out_tok"], f["req_in"], f["req_out"]) +
         bytes([f["verifier"], f["retry"], f["attempts"], f["cancel"], f["precision"], f["substrate"],
                f["dep_count"], f["operand_count"], f["result_type"], f["result_rank"], f["pure"], f["reserved1"]]) +
         struct.pack(">IQQQQ", f["time_ms"], f["fuel"], f["memory"], f["work"], f["expires"]) +
         struct.pack(">4I", *f["dims"]) + f["capability"] + f["tenant"] + f["model_ref"] + f["verifier_ref"] +
         f["deps"] + f["operands"])
    assert len(n) == 448, len(n)
    return n

def build_header(**o):
    f = dict(magic=b"MJB1", version=1, ceiling=1, count=1, objective=sha(b"AIENET0-OBJECTIVE-V1\0", NONCE),
             tenant=sha(b"AIENET0-TENANT-TUR-TEST-V1"), subject=bytes(32), approval=bytes(32), incarnation=1,
             reserved0=0, expires=NOW + 3600, b_time=120000, b_fuel=1, b_mem=1, b_work=1, b_in=0, b_out=0)
    f.update(o)
    h = (f["magic"] + bytes([f["version"], f["ceiling"]]) + struct.pack(">H", f["count"]) + f["objective"] +
         f["tenant"] + f["subject"] + f["approval"] + struct.pack(">II", f["incarnation"], f["reserved0"]) +
         struct.pack(">QQQQQ", f["expires"], f["b_time"], f["b_fuel"], f["b_mem"], f["b_work"]) +
         struct.pack(">II", f["b_in"], f["b_out"]))
    assert len(h) == 192, len(h)
    return h

def matmul_document(pl, submitter, op=2, node_over=None, head_over=None, work_mem=None):
    """One-node profile document (PROFILE.md 'Bundle AN0B' paragraph 3)."""
    if len(pl) == 15 and pl[0] == 1:
        m, k, n = struct.unpack(">HHH", pl[1:7]); work = max(payload_work(m, k, n), 1); mem = max(payload_mem(m, k, n), 1)
    else:
        work, mem = 1, 1
    if work_mem: work, mem = work_mem
    nonce = NONCE
    hd = dict(subject=sha(b"AIENET0-SUBJECT-V1\0", pl), approval=sha(b"AIENET0-APPROVAL-V1\0", submitter, nonce),
              b_fuel=work, b_mem=mem, b_work=work)
    hd.update(head_over or {})
    nd = dict(op=op, fuel=work, memory=mem, work=work, operands=bytes([3, 0, 0, 0]) + struct.pack(">I", 1) + sha(pl) + bytes(120))
    nd.update(node_over or {})
    return build_header(**hd) + build_node(**nd)

# ---- MJB1 static check (SPEC 4.4), generic over nodes ----
def zero(b): return not any(b)
def check_document(b):
    if len(b) < 192: return "MJB_BAD_LENGTH"
    if b[0:4] != b"MJB1": return "MJB_BAD_MAGIC"
    if b[4] == 0: return "MJB_DOWNGRADE"
    if b[4] > 1: return "MJB_BAD_VERSION"
    cnt = struct.unpack(">H", b[6:8])[0]
    if cnt == 0 or cnt > 64: return "MJB_BAD_COUNT"
    if len(b) != 192 + 448 * cnt: return "MJB_BAD_LENGTH"
    if struct.unpack(">I", b[140:144])[0] != 0: return "MJB_RESERVED_NONZERO"
    ceil = b[5]
    if ceil > 2: return "MJB_BAD_ENUM"
    objective, tenant, subject, approval = b[8:40], b[40:72], b[72:104], b[104:136]
    if zero(objective): return "MJB_NO_OBJECTIVE"
    if zero(tenant): return "MJB_NO_TENANT"
    if zero(subject): return "MJB_NO_SUBJECT"
    if zero(approval): return "MJB_NO_APPROVAL"
    if struct.unpack(">I", b[136:140])[0] == 0: return "MJB_NO_OBJECTIVE"
    hexp, bt, bf, bm, bw, bi, bo = struct.unpack(">QQQQQII", b[144:192])
    sums = dict(t=0, f=0, w=0, i=0, o=0)
    nodes = []
    for i in range(cnt):
        n = b[192 + 448 * i: 192 + 448 * (i + 1)]
        nodes.append(n)
        jid, idem = n[0:16], n[16:32]
        gen = struct.unpack(">I", n[32:36])[0]
        if zero(jid) or zero(idem) or gen == 0: return "MJB_NO_JOB"
        kind, op, prof, eff = n[36], n[37], n[38], n[39]
        itok, otok, rin, rout = struct.unpack(">HHHH", n[40:48])
        ver, retry, att, canc, prec, sub, depc, opc, rtype, rrank, pure, res1 = n[48:60]
        rtime, fuel, mem, work, nexp = struct.unpack(">IQQQQ", n[60:96]) if False else (struct.unpack(">I", n[60:64])[0], *struct.unpack(">QQQQ", n[64:96]))
        dims = struct.unpack(">4I", n[96:112])
        cap, ten, mref, vref = n[112:144], n[144:176], n[176:208], n[208:240]
        deps = n[240:288]; ops = n[288:448]
        # rule 11 reserved
        r11 = res1 != 0
        for s in range(8):
            if s >= depc and any(deps[6 * s: 6 * s + 6]): r11 = True
        for s in range(4):
            sl = ops[40 * s: 40 * s + 40]
            if s >= opc and any(sl): r11 = True
            if s < opc and any(sl[1:4]): r11 = True
        for d in range(4):
            if d >= rrank and dims[d] != 0: r11 = True
        if r11: return "MJB_RESERVED_NONZERO"
        bad = False
        if kind not in (1, 2): bad = True
        elif kind == 1 and op not in range(1, 7): bad = True
        elif kind == 2 and op not in range(1, 5): bad = True
        if prof > 4 or eff > 2 or ver > 3 or retry not in (1, 2, 3) or att < 1 or att > 8 or canc not in (1, 2) or prec > 6:
            bad = True
        if sub == 0 or sub & 0xF8 or depc > 8 or opc > 4 or rtype not in range(1, 8) or rrank > 4 or pure > 1: bad = True
        for s in range(min(opc, 4)):
            if ops[40 * s] not in range(1, 6): bad = True
        if bad: return "MJB_BAD_ENUM"
        if ten != tenant: return "MJB_CROSS_TENANT"
        if zero(cap): return "MJB_NO_CAPABILITY"
        if eff > ceil: return "MJB_UNAUTHORIZED_EFFECT"
        if ver == 0 or (ver in (2, 3) and zero(vref)) or (ver == 1 and not zero(vref)) or (ver == 1 and pure != 1): return "MJB_NO_VERIFIER"
        if pure == 1 and (kind == 2 or eff == 2): return "MJB_IMPURE"
        if kind == 1:
            if prof != 0 or itok or otok or rin or rout or not zero(mref): return "MJB_TOKEN_PROFILE"
        else:
            cap_in = [0, 64, 128, 256, 512][prof]; cap_out = [0, 16, 32, 64, 128][prof]
            if prof == 0 or itok == 0 or otok == 0 or itok > cap_in or otok > cap_out or zero(mref): return "MJB_TOKEN_PROFILE"
        if rin > itok or rout > otok: return "MJB_NEEDS_EXPANSION"
        if (retry == 1 and att > 1) or (eff == 2 and retry == 2): return "MJB_BAD_RETRY"
        if rtime == 0 or fuel == 0 or mem == 0 or work == 0: return "MJB_ZERO_CAP"
        if nexp == 0 or nexp > hexp: return "MJB_BAD_EXPIRY"
        for s in range(min(opc, 4)):
            sl = ops[40 * s: 40 * s + 40]
            if struct.unpack(">I", sl[4:8])[0] == 0 or zero(sl[8:40]): return "MJB_MISSING_OPERAND"
        sums["t"] += rtime; sums["f"] += fuel; sums["w"] += work; sums["i"] += itok; sums["o"] += otok
    jids = [n[0:16] for n in nodes]; idems = [n[16:32] for n in nodes]
    if len(set(jids)) != cnt or len(set(idems)) != cnt: return "MJB_DUPLICATE_JOB"
    for i, n in enumerate(nodes):
        for s in range(n[54]):
            idx, g = struct.unpack(">HI", n[240 + 6 * s: 246 + 6 * s])
            if idx == i or idx >= cnt: return "MJB_MISSING_DEP"
    for i, n in enumerate(nodes):
        for s in range(n[54]):
            idx, g = struct.unpack(">HI", n[240 + 6 * s: 246 + 6 * s])
            if g != struct.unpack(">I", nodes[idx][32:36])[0]: return "MJB_STALE_GENERATION"
    # cycle by Kahn
    indeg = [nodes[i][54] for i in range(cnt)]
    done = set(); progress = True
    while progress:
        progress = False
        for i in range(cnt):
            if i in done: continue
            if all(struct.unpack(">H", nodes[i][240 + 6 * s: 242 + 6 * s])[0] in done for s in range(nodes[i][54])):
                done.add(i); progress = True
    if len(done) != cnt: return "MJB_CYCLE"
    if sums["t"] > bt or sums["f"] > bf or sums["w"] > bw or sums["i"] > bi or sums["o"] > bo: return "MJB_OVER_BUDGET"
    for n in nodes:
        if struct.unpack(">Q", n[72:80])[0] > bm: return "MJB_OVER_BUDGET"
    return "ok"

def dag_digest(d): return sha(d)

# ---- AN0B bundle and profile admission (PROFILE.md) ----
BUNDLE_HEAD = 109
MAX_BUNDLE = 109 + 256 + 192 + 64 * 448
SUBMIT_DOM = b"AIENET0-MJB1-SUBMIT-V1\0"

def submit_msg(doc, pl): return SUBMIT_DOM + dag_digest(doc) + sha(pl)

def parse_key(seed_byte):
    from cryptography.hazmat.primitives.asymmetric import ec
    return ec.derive_private_key(int.from_bytes(bytes([seed_byte]) * 32, "big"), ec.SECP256R1())

def compressed(priv):
    nums = priv.public_key().public_numbers()
    return bytes([2 + (nums.y & 1)]) + nums.x.to_bytes(32, "big")

def sign_low_s(priv, msg):
    from cryptography.hazmat.primitives.asymmetric import ec
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.asymmetric.utils import decode_dss_signature
    r, s = decode_dss_signature(priv.sign(msg, ec.ECDSA(hashes.SHA256())))
    if s > P256_N // 2: s = P256_N - s
    return r.to_bytes(32, "big") + s.to_bytes(32, "big")

def verify_low_s(pub33, msg, sig):
    from cryptography.hazmat.primitives.asymmetric import ec
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.asymmetric.utils import encode_dss_signature
    r = int.from_bytes(sig[:32], "big"); s = int.from_bytes(sig[32:], "big")
    if s > P256_N // 2: return False
    try:
        pk = ec.EllipticCurvePublicKey.from_encoded_point(ec.SECP256R1(), pub33)
        pk.verify(encode_dss_signature(r, s), msg, ec.ECDSA(hashes.SHA256()))
        return True
    except Exception:
        return False

def seal(doc, pl, priv, plen=None, dlen=None, magic=b"AN0B", ver=1, res=0, key=None, sig=None):
    key = compressed(priv) if key is None else key
    sig = sign_low_s(priv, submit_msg(doc, pl)) if sig is None else sig
    return (magic + bytes([ver, res]) + struct.pack(">HI", len(pl) if plen is None else plen, len(doc) if dlen is None else dlen) +
            key + sig + pl + doc)

def admit(bundle, pinned, now):
    """Profile admission order (PROFILE.md 'Worker admission'), signature checked by OpenSSL."""
    b = bundle
    if not (len(b) >= BUNDLE_HEAD and len(b) <= MAX_BUNDLE and b[:4] == b"AN0B"): return "AN0_BAD_BUNDLE"
    if not (b[4] == 1 and b[5] == 0): return "AN0_BAD_BUNDLE"
    plen = struct.unpack(">H", b[6:8])[0]; dlen = struct.unpack(">I", b[8:12])[0]
    if not (plen <= 256 and BUNDLE_HEAD + plen + dlen == len(b)): return "AN0_BAD_BUNDLE"
    key, sig, pl, doc = b[12:45], b[45:109], b[109:109 + plen], b[109 + plen:]
    if key != pinned: return "AN0_BAD_SUBMITTER"
    if not verify_low_s(key, submit_msg(doc, pl), sig): return "AN0_BAD_SUBMITTER"
    c = check_document(doc)
    if c != "ok": return c
    hexp = struct.unpack(">Q", doc[144:152])[0]
    node = doc[192:640]
    if hexp < now: return "MJB_BAD_EXPIRY"
    if doc[6:8] != b"\x00\x01": return "AN0_NOT_ALLOWLISTED"
    if struct.unpack(">Q", node[88:96])[0] < now: return "MJB_BAD_EXPIRY"
    if not (node[36] == 1 and node[37] == 2): return "AN0_NOT_ALLOWLISTED"
    if not (node[48] == 1 and node[39] == 1): return "AN0_NOT_ALLOWLISTED"
    if not (node[55] == 1 and node[54] == 0): return "AN0_NOT_ALLOWLISTED"
    if node[288] != 3: return "AN0_NOT_ALLOWLISTED"
    if node[296:328] != sha(pl): return "AN0_PAYLOAD_MISMATCH"
    r = model_rust_decode(pl)
    if r != "decode_ok": return r
    m, k, n, seed = struct.unpack(">HHHQ", pl[1:])
    if not all(1 <= d <= 256 for d in (m, k, n)): return "AN0_OVER_BUDGET"
    w = m * k * n; mem = payload_mem(m, k, n)
    nwork, nfuel, nmem = struct.unpack(">Q", node[80:88])[0], struct.unpack(">Q", node[64:72])[0], struct.unpack(">Q", node[72:80])[0]
    bfuel = struct.unpack(">Q", doc[160:168])[0]
    if not (nwork >= w and nfuel >= w and bfuel >= w and nmem >= mem): return "AN0_OVER_BUDGET"
    return "ok dag_digest=" + dag_digest(doc).hex()

# ---- case tables ----
POSITIVE = [  # id, m,k,n, seed, note
    ("min-1x1x1-seed0", 1, 1, 1, 0, "smallest job; also the first xcheck662 historical payload"),
    ("hist-2x3x4-seed7", 2, 3, 4, 7, "historical xcheck662 payload"),
    ("hist-7x5x3-a1e70001", 7, 5, 3, 0xA1E70001, "Rust unit-test job"),
    ("hist-64-seed-2716205057", 64, 64, 64, 2716205057, "exercised Spark-MacBook shape; historical digest 734fdc94...f1de2"),
    ("hist-64-seed-big", 64, 64, 64, 1311768467463790320, "historical xcheck662 payload"),
    ("hist-128x64x32-seed99", 128, 64, 32, 99, "historical xcheck662 payload"),
    ("max-256-cube", 256, 256, 256, 2716205057, "dimension upper bound; 16777216 multiply-adds"),
    ("edge-1x256x1", 1, 256, 1, 2716205057, "k at bound, others minimal"),
    ("edge-256x1x256", 256, 1, 256, 2716205057, "k minimal"),
    ("seed-max-u64", 3, 8, 1, U64, "seed 2^64-1: splitmix state wrap"),
    ("seed-zero-16x9x31", 16, 9, 31, 0, "odd shape, seed zero"),
]
NEGATIVE_PAYLOAD = [  # id, hex builder, note
    ("empty", b""),
    ("kind-only", b"\x01"),
    ("short-14", payload(2, 3, 4, 7)[:14]),
    ("long-16", payload(2, 3, 4, 7) + b"\x00"),
    ("long-17", payload(2, 3, 4, 7) + b"\x00\x00"),
    ("long-256", (payload(2, 3, 4, 7) + bytes(241))),
    ("kind-0", payload(2, 3, 4, 7, kind=0)),
    ("kind-2", payload(2, 3, 4, 7, kind=2)),
    ("kind-ff", payload(2, 3, 4, 7, kind=0xFF)),
    ("kind-2-short", payload(2, 3, 4, 7, kind=2)[:14]),
    ("m-zero", payload(0, 3, 4, 7)),
    ("k-zero", payload(2, 0, 4, 7)),
    ("n-zero", payload(2, 3, 0, 7)),
    ("all-zero-dims", payload(0, 0, 0, 0)),
    ("m-257", payload(257, 3, 4, 7)),
    ("k-257", payload(2, 257, 4, 7)),
    ("n-257", payload(2, 3, 257, 7)),
    ("m-65535", payload(65535, 3, 4, 7)),
    ("all-65535", payload(65535, 65535, 65535, U64)),
    ("m-256-k-257", payload(256, 257, 1, 1)),
]

def document_cases():
    pl = payload(7, 5, 3, 0xA1E70001)
    sub = compressed(parse_key(1))
    base = matmul_document(pl, sub)
    def mut(off, val, doc=None):
        d = bytearray(base if doc is None else doc); d[off:off + len(val)] = val; return bytes(d)
    N = 192  # node base
    c = []
    c.append(("golden-matmul-7x5x3", base, "positive: one-node profile document"))
    c.append(("golden-matmul-1x1x1", matmul_document(payload(1, 1, 1, 0), sub), "positive: smallest"))
    c.append(("golden-matmul-256-cube", matmul_document(payload(256, 256, 256, 2716205057), sub), "positive: upper bound; work 16777216, memory 786432"))
    c.append(("len-empty", b"", ""))
    c.append(("len-191", base[:191], ""))
    c.append(("len-trailing", base + b"\x00", ""))
    c.append(("len-short-node", base[:-1], ""))
    c.append(("magic", mut(0, b"MJB2"), ""))
    c.append(("version-0", mut(4, b"\x00"), ""))
    c.append(("version-2", mut(4, b"\x02"), ""))
    c.append(("count-0", base[:6] + b"\x00\x00" + base[8:192], ""))
    c.append(("count-65", mut(6, b"\x00\x41", base[:192]), ""))
    c.append(("count-2-length-1", mut(6, b"\x00\x02"), "length check follows count check"))
    c.append(("reserved0", mut(140, b"\x00\x00\x00\x01"), ""))
    c.append(("ceiling-3", mut(5, b"\x03"), ""))
    c.append(("objective-zero", mut(8, bytes(32)), ""))
    c.append(("tenant-zero", mut(40, bytes(32)), ""))
    c.append(("subject-zero", mut(72, bytes(32)), ""))
    c.append(("approval-zero", mut(104, bytes(32)), ""))
    c.append(("incarnation-0", mut(136, bytes(4)), ""))
    c.append(("header-expiry-0", mut(144, bytes(8)), "rule 9: node then fails rule 22"))
    c.append(("job-id-zero", mut(N + 0, bytes(16)), ""))
    c.append(("idem-zero", mut(N + 16, bytes(16)), ""))
    c.append(("generation-0", mut(N + 32, bytes(4)), ""))
    c.append(("reserved1", mut(N + 59, b"\x01"), ""))
    c.append(("unused-dep-slot", mut(N + 240, b"\x01"), ""))
    c.append(("unused-operand-slot", mut(N + 288 + 40, b"\x01"), ""))
    c.append(("used-operand-reserved", mut(N + 289, b"\x01"), ""))
    c.append(("dims-past-rank", mut(N + 96, b"\x00\x00\x00\x01"), ""))
    c.append(("kind-3", mut(N + 36, b"\x03"), ""))
    c.append(("op-0", mut(N + 37, b"\x00"), ""))
    c.append(("op-7", mut(N + 37, b"\x07"), ""))
    c.append(("profile-5", mut(N + 38, b"\x05"), ""))
    c.append(("effect-3", mut(N + 39, b"\x03"), ""))
    c.append(("max-attempts-0", mut(N + 50, b"\x00"), ""))
    c.append(("max-attempts-9", mut(N + 50, b"\x09"), ""))
    c.append(("cancel-0", mut(N + 51, b"\x00"), ""))
    c.append(("precision-7", mut(N + 52, b"\x07"), ""))
    c.append(("substrate-0", mut(N + 53, b"\x00"), ""))
    c.append(("substrate-bit3", mut(N + 53, b"\x09"), ""))
    c.append(("dep-count-9", mut(N + 54, b"\x09"), ""))
    c.append(("operand-count-5", mut(N + 55, b"\x05"), ""))
    c.append(("result-type-0", mut(N + 56, b"\x00"), ""))
    c.append(("result-rank-5", mut(N + 57, b"\x05"), ""))
    c.append(("pure-2", mut(N + 58, b"\x02"), ""))
    c.append(("operand-kind-6", mut(N + 288, b"\x06"), ""))
    c.append(("cross-tenant", mut(N + 144, b"\xff" + sha(b"AIENET0-TENANT-TUR-TEST-V1")[1:]), ""))
    c.append(("capability-zero", mut(N + 112, bytes(32)), ""))
    c.append(("effect-above-ceiling", mut(N + 39, b"\x02"), "EFFECT node under COMPUTE ceiling"))
    c.append(("verifier-0", mut(N + 48, b"\x00"), ""))
    c.append(("recompute-with-verifier-ref", mut(N + 208, b"\x01" * 32), ""))
    c.append(("recompute-not-pure", mut(N + 58, b"\x00"), ""))
    c.append(("compute-profile-nonzero", mut(N + 38, b"\x01"), ""))
    c.append(("compute-model-ref", mut(N + 176, b"\x01" * 32), ""))
    c.append(("compute-token-cap", mut(N + 40, b"\x00\x01"), ""))
    c.append(("needs-expansion-required-without-cap", mut(N + 44, b"\x00\x01"), "required_input_tokens 1 > input_tokens 0; rule 18 fires first (compute token fields must be zero)"))
    c.append(("retry-never-two-attempts", mut(N + 50, b"\x02"), ""))
    c.append(("time-ms-zero", mut(N + 60, bytes(4)), ""))
    c.append(("fuel-zero", mut(N + 64, bytes(8)), ""))
    c.append(("memory-zero", mut(N + 72, bytes(8)), ""))
    c.append(("work-zero", mut(N + 80, bytes(8)), ""))
    c.append(("node-expiry-zero", mut(N + 88, bytes(8)), ""))
    c.append(("node-expiry-above-header", mut(N + 88, struct.pack(">Q", NOW + 3601)), ""))
    c.append(("operand-generation-0", mut(N + 292, bytes(4)), ""))
    c.append(("operand-digest-zero", mut(N + 296, bytes(32)), ""))
    c.append(("dep-self", mut(N + 54, b"\x01"), "dep_count 1, slot 0 = index 0 generation 0: names the node itself"))
    c.append(("dep-out-of-range", mut(N + 240, b"\x00\x05\x00\x00\x00\x01", mut(N + 54, b"\x01")), ""))
    c.append(("budget-work-short", mut(160 + 16, struct.pack(">Q", payload_work(7, 5, 3) - 1)), ""))
    c.append(("budget-fuel-short", mut(160, struct.pack(">Q", payload_work(7, 5, 3) - 1)), ""))
    c.append(("budget-time-short", mut(152, struct.pack(">Q", 119999)), ""))
    c.append(("budget-memory-short", mut(168, struct.pack(">Q", payload_mem(7, 5, 3) - 1)), "memory is a per-node peak bound"))
    c.append(("budget-memory-u64-max-ok", mut(168, struct.pack(">Q", U64)), "positive: u64 max memory budget is not an overflow"))
    return c

def bundle_cases():
    priv = parse_key(1); other = parse_key(2)
    pub = compressed(priv)
    pl = payload(7, 5, 3, 0xA1E70001)
    doc = matmul_document(pl, pub)
    cases = []
    def add(i, b, pinned, now, note=""): cases.append((i, b, pinned, now, admit(b, pinned, now), note))
    add("golden", seal(doc, pl, priv), pub, NOW, "positive")
    add("golden-now-equals-expiry", seal(doc, pl, priv), pub, NOW + 3600, "equality is admissible (SPEC section 7)")
    add("expired-by-one-second", seal(doc, pl, priv), pub, NOW + 3601)
    good = seal(doc, pl, priv)
    add("truncated-0", b"", pub, NOW); add("truncated-108", good[:108], pub, NOW)
    add("bad-magic", b"AN0X" + good[4:], pub, NOW)
    add("version-0", good[:4] + b"\x00" + good[5:], pub, NOW)
    add("version-2", good[:4] + b"\x02" + good[5:], pub, NOW)
    add("reserved-1", good[:5] + b"\x01" + good[6:], pub, NOW)
    add("trailing-byte", good + b"\x00", pub, NOW)
    add("missing-last-byte", good[:-1], pub, NOW)
    add("payload-length-257-consistent", seal(doc, pl + bytes(242), priv), pub, NOW, "plen 257 > 256 bound")
    add("payload-length-field-lies", good[:6] + struct.pack(">H", 16) + good[8:], pub, NOW)
    add("document-length-u32-max", good[:8] + b"\xff\xff\xff\xff" + good[12:], pub, NOW, "dlen 4294967295 must not wrap")
    add("over-max-bundle", seal(doc + bytes(30000), pl, priv), pub, NOW, "document longer than any valid MJB1 document")
    add("unpinned-key", seal(doc, pl, other), pub, NOW)
    bad = bytearray(good); bad[45 + 3] ^= 1
    add("signature-bit-flip", bytes(bad), pub, NOW)
    r = int.from_bytes(good[45:77], "big"); s = int.from_bytes(good[77:109], "big")
    high = good[:77] + (P256_N - s).to_bytes(32, "big") + good[109:]
    add("signature-high-s", high, pub, NOW, "valid math, refused for malleability")
    ddoc = bytearray(doc); ddoc[0] = ord("X")
    add("document-magic-signed", seal(bytes(ddoc), pl, priv), pub, NOW, "signature valid over a bad document")
    add("document-cross-tenant", seal(matmul_document(pl, pub, node_over=dict(tenant=b"\xff" * 32)), pl, priv), pub, NOW)
    add("op-arith", seal(matmul_document(pl, pub, op=1), pl, priv), pub, NOW, "valid MJB1, outside profile")
    add("op-compile", seal(matmul_document(pl, pub, op=5), pl, priv), pub, NOW, "valid MJB1, outside profile")
    add("two-nodes", seal(doc + doc[192:], pl, priv), pub, NOW, "count 1 header, 2 nodes: MJB_BAD_LENGTH")
    d2 = bytearray(doc + build_node(job_id=b"\x07" * 16, idem=b"\x08" * 16, fuel=84, work=84, memory=3 * 4 * 12)); d2[6:8] = b"\x00\x02"
    add("two-valid-nodes-budget", seal(bytes(d2), pl, priv), pub, NOW, "header budgets cover only one node: over budget")
    add("payload-not-bound", seal(matmul_document(payload(7, 5, 3, 1), pub), pl, priv), pub, NOW, "operand names a different payload")
    add("verifier-not-recompute", seal(matmul_document(pl, pub, node_over=dict(verifier=2, verifier_ref=b"\x01" * 32)), pl, priv), pub, NOW)
    add("effect-class-none", seal(matmul_document(pl, pub, node_over=dict(effect=0)), pl, priv), pub, NOW)
    add("operand-kind-world-state", seal(matmul_document(pl, pub, node_over=dict(operands=bytes([2, 0, 0, 0]) + struct.pack(">I", 1) + sha(pl) + bytes(120))), pl, priv), pub, NOW)
    for i, p in (("payload-kind-2", payload(7, 5, 3, 1, kind=2)), ("payload-empty", b""), ("payload-14", payload(7, 5, 3, 1)[:14]),
                 ("payload-16", payload(7, 5, 3, 1) + b"\x00"), ("dim-zero", payload(0, 5, 3, 1)), ("dim-257", payload(257, 5, 3, 1)),
                 ("dim-65535-all", payload(65535, 65535, 65535, 1))):
        add(i, seal(matmul_document(p, pub), p, priv), pub, NOW, "document is self-consistent with this payload")
    for i, wm in (("node-work-short", None), ):
        pass
    d = matmul_document(pl, pub, node_over=dict(work=payload_work(7, 5, 3) - 1)); add("node-work-below-job", seal(d, pl, priv), pub, NOW)
    d = matmul_document(pl, pub, node_over=dict(fuel=payload_work(7, 5, 3) - 1)); add("node-fuel-below-job", seal(d, pl, priv), pub, NOW)
    d = matmul_document(pl, pub, node_over=dict(memory=payload_mem(7, 5, 3) - 1), head_over=dict(b_mem=payload_mem(7, 5, 3) - 1)); add("node-memory-below-job", seal(d, pl, priv), pub, NOW)
    d = matmul_document(pl, pub, head_over=dict(b_fuel=payload_work(7, 5, 3) - 1), node_over=dict(fuel=payload_work(7, 5, 3) - 1, work=payload_work(7, 5, 3)));
    add("header-fuel-below-job", seal(d, pl, priv), pub, NOW, "node fuel below job work too")
    return cases

def hexs(b): return b.hex() if b else "-"

def generate(out):
    os.makedirs(out, exist_ok=True)
    with open(f"{out}/payload-positive.tsv", "w") as f:
        f.write("# id\tm\tk\tn\tseed\tpayload_hex\toutput_digest_hex\twork\tmemory_bytes\tnote\n")
        for i, m, k, n, s, note in POSITIVE:
            f.write(f"{i}\t{m}\t{k}\t{n}\t{s}\t{payload(m,k,n,s).hex()}\t{digest(m,k,n,s).hex()}\t{payload_work(m,k,n)}\t{payload_mem(m,k,n)}\t{note}\n")
    with open(f"{out}/payload-negative.tsv", "w") as f:
        f.write("# id\tpayload_hex\tomega_consumer_expect\trust_decode_expect\tnote\n")
        for i, p in NEGATIVE_PAYLOAD:
            om = model_om_consumer(p); rd = model_rust_decode(p)
            if rd == "decode_ok":
                m, k, n, _ = struct.unpack(">HHHQ", p[1:]); rd = "decode_ok_then_AN0_OVER_BUDGET" if not all(1 <= d <= 256 for d in (m, k, n)) else rd
            f.write(f"{i}\t{hexs(p)}\t{om}\t{rd}\t\n")
    with open(f"{out}/document.tsv", "w") as f:
        f.write("# id\tdocument_hex\texpect\tdag_digest_hex\tnote\n")
        for i, d, note in document_cases():
            r = check_document(d)
            f.write(f"{i}\t{hexs(d)}\t{r}\t{dag_digest(d).hex() if r=='ok' else '-'}\t{note}\n")
    with open(f"{out}/bundle.tsv", "w") as f:
        f.write("# id\tbundle_hex\tpinned_submitter_hex\tnow\texpect\tnote\n")
        for i, b, pin, now, r, note in bundle_cases():
            f.write(f"{i}\t{hexs(b)}\t{pin.hex()}\t{now}\t{r}\t{note}\n")

def rows(path):
    out = []
    for l in open(path):
        if l.startswith("#") or not l.strip(): continue
        out.append(l.rstrip("\n").split("\t"))
    return out

def unhex(s): return b"" if s == "-" else bytes.fromhex(s)

def check(d):
    bad = 0
    def fail(msg):
        nonlocal bad; bad += 1; print("ORACLE_FAIL", msg)
    for r in rows(f"{d}/payload-positive.tsv"):
        i, m, k, n, s = r[0], *map(int, r[1:5]); 
        if r[5] != payload(m, k, n, s).hex() or r[6] != digest(m, k, n, s).hex() or int(r[7]) != payload_work(m, k, n) or int(r[8]) != payload_mem(m, k, n): fail("positive " + i)
    for r in rows(f"{d}/payload-negative.tsv"):
        p = unhex(r[1])
        if model_om_consumer(p) != r[2]: fail("negative-om " + r[0])
    # documents: deterministic -> must equal regenerated bytes; verdicts must equal check_document
    regen = {i: dd for i, dd, _ in document_cases()}
    for r in rows(f"{d}/document.tsv"):
        dd = unhex(r[1])
        if regen.get(r[0]) != dd: fail("document-bytes " + r[0])
        v = check_document(dd)
        if v != r[2]: fail(f"document-verdict {r[0]} {v} != {r[2]}")
        if (r[3] != "-") != (v == "ok") or (v == "ok" and r[3] != dag_digest(dd).hex()): fail("document-digest " + r[0])
    for r in rows(f"{d}/bundle.tsv"):
        v = admit(unhex(r[1]), unhex(r[2]), int(r[3]))
        if v != r[4]: fail(f"bundle-verdict {r[0]} {v} != {r[4]}")
    print("ORACLE_CHECK fail=%d" % bad)
    return bad

if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "generate": generate(sys.argv[2])
    elif len(sys.argv) == 3 and sys.argv[1] == "check": sys.exit(1 if check(sys.argv[2]) else 0)
    else: print(__doc__); sys.exit(2)
