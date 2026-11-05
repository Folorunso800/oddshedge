"""Offline tests (stdlib unittest). Run: python3 -m unittest -v"""
import io, json, os, sys, tempfile, unittest, contextlib
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import agent, chainsig, paper

SNAP = os.path.join(os.path.dirname(__file__), "..", "fixtures", "snapshot_2026-11-05.json")
def quiet(fn, *a, **k):
    with contextlib.redirect_stdout(io.StringIO()) as buf: r = fn(*a, **k)
    return r, buf.getvalue()

class Model(unittest.TestCase):
    def test_at_the_money_is_about_half(self):
        p, d = agent.model(100, 100, 0.5, 1/365); self.assertAlmostEqual(p, 0.5, delta=0.01); self.assertGreater(d, 0)
    def test_far_strikes(self):
        self.assertLess(agent.model(100, 200, 0.5, 1/365)[0], 0.001)
        self.assertGreater(agent.model(100, 50, 0.5, 1/365)[0], 0.999)
    def test_stake_is_capped_at_5_percent(self):
        self.assertEqual(agent.stake_size(1000, 0.9, 0.1), 50.0)
        self.assertLess(agent.stake_size(1000, 0.02, 0.5), 50.0)

class ChainSignatures(unittest.TestCase):
    # root keys read from v1.signer (mainnet) and v1.signer-prod.testnet on 2026-11-05; expected addresses
    # computed independently with chainsig.js deriveChildPublicKey + viem keccak256.
    MAIN = "secp256k1:3tFRbMqmoa6AAALMrEFAYCEoHcqKxeW38YptwowBVBtXK1vo36HDbUWuR6EZmoK4JcH6HDkNMGGqP1ouV7VZUWya"
    TEST = "secp256k1:4NfTiv3UsGahebgTaHyD9vF8KYKMBnfd6kh94mK6xv8fGBiJB8TBtFMP5WWXz6B89Ac1fbpzPwAvoyQebemHFwx3"
    def test_keccak(self):
        self.assertEqual(chainsig.keccak256(b"").hex(), "c5d2460186f7233c927e7db2dcc703c0e500b653ca82273b7bfad8045d85a470")
    def test_matches_chainsig_js_mainnet(self):
        self.assertEqual(chainsig.derive_evm_address("oddshedge-demo.near", "hyperliquid-1", root=chainsig.parse_root(self.MAIN)),
                         "0x8b46e400b28006b8aa9f4fcd774071029c6c57cc")
    def test_matches_chainsig_js_testnet(self):
        self.assertEqual(chainsig.derive_evm_address("oddshedge-demo.testnet", "hyperliquid-1", root=chainsig.parse_root(self.TEST)),
                         "0x3b5ab07c489defb826f61a5800d7f195b11c0e13")

class Replay(unittest.TestCase):
    def run_replay(self, *extra):
        out = tempfile.mktemp(suffix=".json")
        return quiet(agent.main, ["--replay", SNAP, "--out", out, *extra])
    def test_replay_is_deterministic_and_dry(self):
        (a, _), (b, txt) = self.run_replay(), self.run_replay()
        self.assertEqual(a["proposals"], b["proposals"]); self.assertTrue(a["dry_run"]); self.assertTrue(a["replay"])
        self.assertIn("REPLAY of real data", txt)
        self.assertTrue(a["intents"]["request"]["dry"]); self.assertEqual(a["intents"]["status"], "ok")
    def test_proposals_respect_risk_limits(self):
        r, _ = self.run_replay()
        self.assertTrue(r["proposals"])
        for p in r["proposals"]:
            self.assertLessEqual(p["stake_usd"], 50.0)
            self.assertLessEqual(abs(p["hedge_coin"]) * p["spot"], 2 * p["stake_usd"] + 0.01)
            self.assertGreaterEqual(abs(p["edge"]), 0.05); self.assertGreaterEqual(p["hours_left"], 6)
            self.assertEqual(p["side"], "YES" if p["edge"] > 0 else "NO")
            # hedge direction: YES bet is long the coin -> short perp (negative size), NO -> long perp
            self.assertTrue((p["hedge_coin"] <= 0) if p["side"] == "YES" else (p["hedge_coin"] >= 0))

class Failures(unittest.TestCase):
    def snap_with(self, broken):
        s = json.load(open(SNAP))
        for k in list(s["calls"]):
            if broken in k: s["calls"][k] = {"_error": "HTTP 503 (simulated outage in test)"}
        f = tempfile.mktemp(suffix=".json"); json.dump(s, open(f, "w")); return f
    def run_with(self, broken):
        return quiet(agent.main, ["--replay", self.snap_with(broken), "--out", tempfile.mktemp()])
    def test_polymarket_down_others_continue(self):
        r, txt = self.run_with("gamma-api.polymarket.com")
        self.assertIn("polymarket unavailable", txt); self.assertTrue(all(p["venue"] != "Polymarket" for p in r["proposals"]))
    def test_hyperliquid_down_skips_asset(self):
        r, txt = self.run_with("api.hyperliquid.xyz")
        self.assertIn("Hyperliquid unavailable", txt); self.assertEqual(r["proposals"], [])
    def test_oneclick_down_keeps_request(self):
        r, txt = self.run_with("1click.chaindefuser.com")
        self.assertIn("unavailable", r["intents"]["status"]); self.assertTrue(r["intents"]["request"]["dry"])
    def test_chainsig_missing_uses_labelled_placeholder(self):
        s = json.load(open(SNAP)); s.pop("mpc_root", None); f = tempfile.mktemp(); json.dump(s, open(f, "w"))
        r, _ = quiet(agent.main, ["--replay", f, "--out", tempfile.mktemp()])
        self.assertEqual(r["intents"]["request"]["recipient"], agent.FALLBACK_RECIPIENT)
        self.assertIn("PLACEHOLDER", r["intents"]["recipient_source"])
    def test_too_few_candles_is_an_error_not_a_crash(self):
        old = agent.post; agent.post = lambda *a, **k: [{"c": "1"}] * 3
        try: self.assertRaises(RuntimeError, agent.hl_vol, "BTC")
        finally: agent.post = old

class Paper(unittest.TestCase):
    def test_pnl_math(self):
        pos = {"side": "NO", "entry_price": 0.8, "shares": 100, "perp_entry": 2000, "perp_size": 0.05}
        self.assertEqual(paper.pnl(pos, 0.0, 1900), (20.0, -5.0))   # NO wins: 0.8 -> 1.0; long hedge loses 100*0.05
        pos["side"] = "YES"; pos["entry_price"] = 0.2; pos["perp_size"] = -0.05
        self.assertEqual(paper.pnl(pos, 1.0, 2100), (80.0, -5.0))
    def test_open_is_idempotent(self):
        r, _ = quiet(agent.main, ["--replay", SNAP, "--out", tempfile.mktemp()])
        pf = tempfile.mktemp(); json.dump(r, open(pf, "w")); paper.LEDGER = tempfile.mktemp()
        n1, _ = quiet(paper.open_positions, pf); n2, _ = quiet(paper.open_positions, pf)
        self.assertEqual(n1, len([p for p in r["proposals"] if p.get("market_id")])); self.assertEqual(n2, 0)
        self.assertTrue(all(p["from_replay"] for p in paper.load()["positions"]))

if __name__ == "__main__": unittest.main()
