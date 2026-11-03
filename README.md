# OddsHedge — prediction-market odds vs perp-implied odds, hedged, funded through NEAR Intents

Built at **NEAR HACKATHON** (Nov 2026). Tracks: `defi`, `agents`.
**DRY RUN ONLY:** no private keys, no wallet, no orders, nothing is signed or sent on-chain.

## Problem
"Will BTC/ETH be above $X on <date>?" markets on Polymarket and Kalshi often disagree with what the perp market
(price + volatility) implies. A trader who spots the gap still carries directional risk, and the money is spread across
chains: prediction-market collateral in one place, perp margin on Hyperliquid in another.

## What it does
1. Reads public odds: Polymarket Gamma API (`Bitcoin/Ethereum above ___ on <date>` events) and Kalshi (`KXBTCD`, `KXETHD`).
2. Reads Hyperliquid BTC/ETH perp mid, 72h realised volatility and funding (public info API).
3. Prices each strike with a lognormal model and flags edges of at least `--min-edge` (default 5 points). Skips markets within 6h of expiry.
4. Proposes a trade: buy YES/NO (quarter-Kelly, max 5% of bankroll) **plus** a delta hedge on the Hyperliquid perp (notional capped at 2x stake).
5. **NEAR leg** — plans how the hedge gets funded:
   - **Chain Signatures:** derives the Hyperliquid (EVM) address controlled by a NEAR account through the NEAR MPC signer `v1.signer`
     (reads the MPC root key over public RPC, then derives locally; see `chainsig.py`). One NEAR account can control the hedge account without a separate EVM key.
   - **NEAR Intents:** requests a live **1Click quote with `dry: true`** moving USDC from the NEAR Intents account to **USDC on Hyperliquid (HyperCore)**, delivered to that derived address. A dry quote returns a price, fees and a time estimate, and no deposit address. Nothing is signed or sent.

## Try it (Python 3.9+, standard library only, no API keys)
```
git clone <repo> && cd <repo>
./demo.sh                       # = python3 agent.py --bankroll 1000 --min-edge 0.05 --top 5
python3 agent.py --bankroll 500 --min-edge 0.08 --top 3 --near-account yourname.near --path hyperliquid-1
python3 chainsig.py yourname.near hyperliquid-1    # just the Chain Signatures address
```
Do `./demo.sh` and you should see: per asset a header with Hyperliquid mid/vol/funding, a list of `[Venue] question | mkt vs model (edge)` lines,
each followed by a `PROPOSE:` line, then the NEAR leg (derived hedge address + 1Click dry-quote result). Everything is also written to `proposals.json`.

### Example output (Nov 3, 2026, trimmed)
```
OddsHedge (DRY RUN - no keys, no orders, no funds, nothing signed)

=== Bitcoin: Hyperliquid mid $77,096.50 | 72h realised vol 19% | funding/h 0.000013
- [Kalshi] KXBTCD-26NOV0317-T76249.99 >= 76249.99 | mkt 0.635 vs model 0.900 (edge +0.265, 17.5h left)
    PROPOSE: buy YES $50.0  +  SHORT 0.00130 BTC-PERP on Hyperliquid (~$100.00, capped at 2x stake)   https://kalshi.com/markets/kxbtcd-26nov0317
- [Polymarket] Will the price of Bitcoin be above $78,000 on November 3? | mkt 0.255 vs model 0.054 (edge -0.201, 12.5h left)
    PROPOSE: buy NO $50.0  +  LONG 0.00130 BTC-PERP on Hyperliquid (~$100.00, capped at 2x stake)   https://polymarket.com/event/bitcoin-above-on-november-3-2026
...
--- NEAR leg: fund $500.00 of Hyperliquid hedge margin from NEAR Intents
Hedge account 0x8b46e400b28006b8aa9f4fcd774071029c6c57cc (derived via NEAR Chain Signatures (v1.signer); account oddshedge-demo.near, path 'hyperliquid-1')
1Click quote (dry=true) USDC NEAR Intents -> USDC Hyperliquid: ok
  in 500.0 USDC -> out 499.596157 USDC (min 494.60), ~20s  | signed by 1Click: ed25519:EtkEtDHRCiFipjMq...
saved proposals.json
```
Live numbers change every run.

## Reliability
- Every data source fails independently: if Polymarket, Kalshi or Hyperliquid is down, that source is skipped with a message and the run continues.
- POSTs retry on 5xx/network errors with backoff. If 1Click is unavailable, the exact quote request is still saved to `proposals.json`.
- If the Chain Signatures RPC lookup fails, a clearly labelled placeholder recipient is used so the quote can still be priced.

## How it maps to the tracks
- **`defi` (trading, NEAR Intents, Chain Signatures):** a trading agent whose cross-venue funding settles through NEAR Intents (1Click) into a Hyperliquid account controlled via Chain Signatures.
- **`agents` (agents that spend, pay through NEAR Intents):** an autonomous agent that finds opportunities, sizes them under risk limits, and prepares its own spending (the funding intent) for a human to approve.

## Limits / honesty
- Dry run: no execution on any venue, no signing. Turning it live would need a NEAR account key (env var, never committed), a non-dry quote, and a deposit into the returned address.
- The model is a simple lognormal with 72h realised vol. Large "edges" often mean the model is too simple (vol smile, event risk), not free money. Not financial advice.
- Polymarket prices are last/mid, Kalshi uses bid/ask mid; neither reflects executable depth. Hedges hit the 2x-stake cap often.
- `chainsig.py` follows the NEAR MPC v1 derivation (epsilon = sha3_256 of `near-mpc-recovery v0.1.0 epsilon derivation:{account},{path}`); it has not been cross-checked against `chainsig.js` in this repo. Treat the address as illustrative until verified.
- `oddshedge-demo.near` is a demo name used only as a derivation input and refund field in a dry quote.
- 1Click without a JWT charges a 0.2% fee (hackathon rule Q-006); no JWT is used.

## Libraries & provenance
Python standard library only (Keccak-256, base58 and secp256k1 math are implemented in `chainsig.py`). All code was written during the hackathon window (Nov 2026), with AI assistance. Public APIs: Polymarket Gamma, Kalshi, Hyperliquid info, NEAR RPC, NEAR Intents 1Click. License: MIT (see `LICENSE`).
