// Test instrument only (not production): drives the existing Rust reference.
// stdin lines, hex fields separated by spaces. Output: one line per input.
use aien_microjob::aienet0::*;
use aien_microjob::{dag_digest, decode};
use p256::ecdsa::SigningKey;
use std::io::BufRead;
fn hx(s: &str) -> Vec<u8> {
    if s == "-" {
        return vec![];
    }
    (0..s.len() / 2)
        .map(|i| u8::from_str_radix(&s[2 * i..2 * i + 2], 16).unwrap())
        .collect()
}
fn to(b: &[u8]) -> String {
    b.iter().map(|x| format!("{:02x}", x)).collect()
}
fn main() {
    for l in std::io::stdin().lock().lines() {
        let l = l.unwrap();
        let f: Vec<&str> = l.split(' ').collect();
        match f[0] {
            "pdec" => {
                let p = hx(f[1]);
                match MatmulU32::decode(&p) {
                    Ok(j) => {
                        let d = if j.in_bounds() {
                            to(&matmul_u32_digest(&j))
                        } else {
                            String::new()
                        };
                        println!(
                            "OK in_bounds={} work={} memory={} digest={}",
                            j.in_bounds(),
                            j.work(),
                            j.memory(),
                            d
                        )
                    }
                    Err(e) => println!("{}", e.name()),
                }
            }
            "ddec" => {
                let d = hx(f[1]);
                match decode(&d) {
                    Ok(_) => println!("OK dag_digest={}", to(&dag_digest(&d))),
                    Err(e) => println!("{}", e.name()),
                }
            }
            // mkdoc payloadhex op noncehex submitter_keyseed now
            "mkbundle" => {
                let p = hx(f[1]);
                let op: u8 = f[2].parse().unwrap();
                let n: [u8; 16] = hx(f[3]).try_into().unwrap();
                let k = SigningKey::from_slice(&[f[4].parse::<u8>().unwrap(); 32]).unwrap();
                let now: u64 = f[5].parse().unwrap();
                let doc = build_document(&p, op, n, &public_key(&k), now);
                println!(
                    "{} {} {}",
                    to(&public_key(&k)),
                    to(&doc),
                    to(&seal_bundle(&doc, &p, &k))
                );
            }
            // admit bundlehex pinned_keyseed now
            "admit" => {
                let b = hx(f[1]);
                let k = SigningKey::from_slice(&[f[2].parse::<u8>().unwrap(); 32]).unwrap();
                let now: u64 = f[3].parse().unwrap();
                match admit_bundle(&b, &public_key(&k), now) {
                    Ok(a) => println!("OK dag_digest={}", to(&a.digest)),
                    Err(e) => println!("{}", e.name()),
                }
            }
            "admitkey" => {
                let b = hx(f[1]);
                let pin: [u8; 33] = hx(f[2]).try_into().unwrap();
                let now: u64 = f[3].parse().unwrap();
                match admit_bundle(&b, &pin, now) {
                    Ok(a) => println!("OK dag_digest={}", to(&a.digest)),
                    Err(e) => println!("{}", e.name()),
                }
            }
            _ => println!("BADCMD"),
        }
    }
}
