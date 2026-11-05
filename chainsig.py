"""Read-only NEAR Chain Signatures helper (stdlib only).

Derives the EVM address that a NEAR account would control through the NEAR MPC
signer (v1.signer) for a given derivation path. It only READS the MPC root public
key over public RPC and does elliptic-curve math locally. It never signs, never
holds a private key and never sends a transaction.

Derivation (NEAR MPC v1, as in near/chainsig.js; cross-checked against chainsig.js
deriveChildPublicKey on 2026-11-05, see tests/test_chainsig.py):
  epsilon = sha3_256("near-mpc-recovery v0.1.0 epsilon derivation:" + account + "," + path)
  child_pub = root_pub + epsilon * G   (secp256k1)
  evm_address = keccak256(child_pub_xy)[-20:]
"""
import hashlib, json, urllib.request, base64

NETWORKS = {  # MPC signer contract per network (see docs.near.org/chain-abstraction/chain-signatures)
    "mainnet": {"rpc": "https://rpc.mainnet.near.org", "signer": "v1.signer"},
    "testnet": {"rpc": "https://rpc.testnet.near.org", "signer": "v1.signer-prod.testnet"},
}
RPC, SIGNER = NETWORKS["mainnet"]["rpc"], NETWORKS["mainnet"]["signer"]
P = 2**256 - 2**32 - 977
N = 0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFEBAAEDCE6AF48A03BBFD25E8CD0364141
G = (0x79BE667EF9DCBBAC55A06295CE870B07029BFCDB2DCE28D959F2815B16F81798,
     0x483ADA7726A3C4655DA4FBFC0E1108A8FD17B448A68554199C47D08FFB10D4B8)

def _add(a, b):
    if a is None: return b
    if b is None: return a
    if a[0] == b[0] and (a[1] + b[1]) % P == 0: return None
    if a == b: l = 3 * a[0] * a[0] * pow(2 * a[1], -1, P) % P
    else: l = (b[1] - a[1]) * pow(b[0] - a[0], -1, P) % P
    x = (l * l - a[0] - b[0]) % P
    return x, (l * (a[0] - x) - a[1]) % P

def _mul(k, pt):
    r = None
    while k:
        if k & 1: r = _add(r, pt)
        pt = _add(pt, pt); k >>= 1
    return r

_B58 = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
def b58decode(s):
    n = 0
    for c in s: n = n * 58 + _B58.index(c)
    raw = n.to_bytes((n.bit_length() + 7) // 8, "big")
    return b"\0" * (len(s) - len(s.lstrip("1"))) + raw

# Minimal Keccak-256 (Ethereum variant, not NIST SHA3) ------------------------
_RC = [0x1, 0x8082, 0x800000000000808A, 0x8000000080008000, 0x808B, 0x80000001, 0x8000000080008081,
       0x8000000000008009, 0x8A, 0x88, 0x80008009, 0x8000000A, 0x8000808B, 0x800000000000008B,
       0x8000000000008089, 0x8000000000008003, 0x8000000000008002, 0x8000000000000080, 0x800A,
       0x800000008000000A, 0x8000000080008081, 0x8000000000008080, 0x80000001, 0x8000000080008008]
_ROT = [[0, 36, 3, 41, 18], [1, 44, 10, 45, 2], [62, 6, 43, 15, 61], [28, 55, 25, 21, 56], [27, 20, 39, 8, 14]]
M64 = 2**64 - 1
def _rol(v, n): return ((v << n) | (v >> (64 - n))) & M64 if n else v
def _f(s):
    for rc in _RC:
        c = [s[x][0] ^ s[x][1] ^ s[x][2] ^ s[x][3] ^ s[x][4] for x in range(5)]
        d = [c[(x - 1) % 5] ^ _rol(c[(x + 1) % 5], 1) for x in range(5)]
        s = [[s[x][y] ^ d[x] for y in range(5)] for x in range(5)]
        b = [[0] * 5 for _ in range(5)]
        for x in range(5):
            for y in range(5): b[y][(2 * x + 3 * y) % 5] = _rol(s[x][y], _ROT[x][y])
        s = [[b[x][y] ^ (~b[(x + 1) % 5][y] & b[(x + 2) % 5][y]) for y in range(5)] for x in range(5)]
        s[0][0] ^= rc
    return s
def keccak256(data):
    rate = 136
    data = bytearray(data) + b"\x01"
    data += b"\0" * (-len(data) % rate); data[-1] |= 0x80
    s = [[0] * 5 for _ in range(5)]
    for off in range(0, len(data), rate):
        for i in range(rate // 8):
            s[i % 5][i // 5] ^= int.from_bytes(data[off + 8 * i: off + 8 * i + 8], "little")
        s = _f(s)
    return b"".join(s[i % 5][i // 5].to_bytes(8, "little") for i in range(4))

def parse_root(key):
    raw = b58decode(key.split(":", 1)[1])
    return int.from_bytes(raw[:32], "big"), int.from_bytes(raw[32:], "big")

def mpc_root_key(network="mainnet"):
    net = NETWORKS[network]
    body = {"jsonrpc": "2.0", "id": 1, "method": "query", "params": {"request_type": "call_function",
            "finality": "final", "account_id": net["signer"], "method_name": "public_key", "args_base64": "e30="}}
    r = urllib.request.Request(net["rpc"], data=json.dumps(body).encode(), headers={"Content-Type": "application/json"})
    res = json.load(urllib.request.urlopen(r, timeout=20))["result"]["result"]
    key = json.loads(bytes(res).decode())
    return key, parse_root(key)

def derive_evm_address(account_id, path, root=None, network="mainnet"):
    if root is None: _, root = mpc_root_key(network)
    eps = int.from_bytes(hashlib.sha3_256(
        f"near-mpc-recovery v0.1.0 epsilon derivation:{account_id},{path}".encode()).digest(), "big")
    child = _add(root, _mul(eps, G))
    return "0x" + keccak256(child[0].to_bytes(32, "big") + child[1].to_bytes(32, "big"))[-20:].hex()

if __name__ == "__main__":
    import sys
    assert keccak256(b"").hex() == "c5d2460186f7233c927e7db2dcc703c0e500b653ca82273b7bfad8045d85a470"
    acct = sys.argv[1] if len(sys.argv) > 1 else "oddshedge-demo.near"
    path = sys.argv[2] if len(sys.argv) > 2 else "hyperliquid-1"
    network = sys.argv[3] if len(sys.argv) > 3 else ("testnet" if acct.endswith(".testnet") else "mainnet")
    print(derive_evm_address(acct, path, network=network))
