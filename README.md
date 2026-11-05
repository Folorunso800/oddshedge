# OddsHedge: catch the gap between prediction-market odds and perp prices, hedge it, fund it through NEAR

Built at **NEAR HACKATHON** (Nov 2026). Tracks: `defi`, `agents`.
**Paper trading only.** No private keys, no wallet, no orders. Nothing is signed or sent on-chain.

## The problem
Polymarket and Kalshi run markets like "Will Bitcoin be above $78,000 on Nov 9?". The perp market on Hyperliquid (price plus volatility) implies its own odds for the same question, and the two often disagree. A trader who spots the gap still has two problems:
1. **Direction risk.** Buying YES is also a bet that the coin goes up.
2. **Scattered money.** Prediction-market collateral sits in one place and perp margin on Hyperliquid in another.

## What OddsHedge does
1. **Reads public odds.** It pulls the Polymarket Gamma API (`Bitcoin/Ethereum above ___ on <date>` events) and Kalshi `KXBTCD` / `KXETHD`. For Kalshi, it uses only two-sided quotes with a spread of at most 15 cents.
2. **Reads Hyperliquid.** It gets the BTC/ETH perp mid price, 72-hour realised volatility and funding from the public info API.
3. **Prices each strike.** A lognormal model gives each strike a probability, and the agent flags gaps of at least `--min-edge` (default 5 points). It skips markets with less than 6 hours to expiry.
4. **Proposes a trade.** Each proposal is a YES or NO bet sized at quarter-Kelly, with a maximum of 5% of the bankroll. It also includes a delta hedge on the Hyperliquid perp, with notional capped at 2x the stake.
5. **Paper ledger (`paper.py`).** This books the proposals as paper positions. It then re-prices them later from live public data (or the final 0/1 result once a market resolves) and shows P&L for the bet leg and the hedge leg.
6. **NEAR leg.** This plans how the hedge margin gets there:
   - **Chain Signatures.** It derives the Hyperliquid (EVM) address that a NEAR account controls through the NEAR MPC signer: `v1.signer` on mainnet, `v1.signer-prod.testnet` on testnet. It reads the MPC root key over public RPC, then does the derivation locally. The result was checked against `chainsig.js` (see tests). With this, one NEAR account can control the hedge account without a separate EVM key.
   - **NEAR Intents.** It requests a live **1Click quote with `dry: true`** for moving USDC from the NEAR Intents account to **USDC on Hyperliquid (HyperCore)**, delivered to that derived address. The quote gives the price, fees and time. Nothing is signed or deposited.

## Try it (Python 3.9+, standard library only, no API keys, no account)
```
git clone https://github.com/Folorunso800/oddshedge && cd oddshedge
./demo.sh                 # live data: scan -> proposals -> NEAR leg -> paper positions -> P&L
./demo.sh replay          # same pipeline, offline, from real data recorded 2026-11-05 08:00 UTC
python3 -m unittest -v    # 15 offline tests
```
Each command and what you should see:
- **`./demo.sh`:** For each asset you get a header (Hyperliquid mid / vol / funding), then `[Venue] question | mkt X vs model Y (edge)` lines, each with a `PROPOSE:` line. After that comes the NEAR leg (the derived hedge address and the 1Click dry-quote result), then `booked N paper positions` and a P&L line for each position. If no market clears the threshold, it prints `no edges above threshold`, which is normal.
- **`./demo.sh replay`:** It first prints `REPLAY of real data recorded ...` and then gives the same output every time.
- **`python3 agent.py --network testnet`:** The Chain Signatures address is derived from the **testnet** MPC signer for `oddshedge-demo.testnet`. NEAR Intents has no testnet (hackathon rule Q-007), so the quote stays a mainnet `dry: true` quote.
- **`python3 chainsig.py yourname.testnet hyperliquid-1`:** This prints only the Chain Signatures address.
- **`python3 paper.py mark`:** Run it hours or days later. It re-prices the open paper positions.

Options: `--bankroll 500 --min-edge 0.08 --top 3 --near-account yourname.near --path hyperliquid-1 --record FILE --replay FILE`.

## Data honesty
- Every number comes from a real public API, either live or from `fixtures/snapshot_2026-11-05.json`. That file is a recording of real responses made with `agent.py --record` and is labelled `REAL public API responses`. Replay output always starts with `REPLAY`.
- No mock or invented market data is used anywhere. The only made-up inputs live in the tests: simulated outages (labelled `simulated outage in test`) and a hand-written P&L example.
- `oddshedge-demo.near` / `.testnet` are example account names. They are used only as derivation inputs and the refund field of a dry quote, and nobody owns or funds them.

## Failure handling
- Each source fails on its own. If Polymarket, Kalshi or Hyperliquid is down, that source (or asset) is skipped with a message and the run continues. Tests cover this.
- POST requests retry on 5xx and network errors, with backoff. If 1Click is down, the exact quote request is still saved in `proposals.json`.
- If the Chain Signatures lookup fails, a clearly labelled `PLACEHOLDER` recipient is used so the quote can still be priced.
- Volatility needs at least 24 hourly candles; with fewer, the asset is skipped instead of producing a wrong number.
- If a paper position can't be priced (for example, no quote right now), it keeps its last mark and says so.

## How it maps to the tracks
- **`defi` (trading, NEAR Intents, Chain Signatures).** It is a trading agent whose cross-venue funding settles through NEAR Intents (1Click) into a Hyperliquid account controlled through Chain Signatures.
- **`agents` (agents that spend through NEAR Intents).** The agent finds opportunities, sizes them under hard risk limits, and prepares its own spending (the funding intent) for a human to approve.

## Limits
- It is a dry run. Going live would need a NEAR account key (kept in an env var, never committed), a non-dry quote, and a deposit to the returned address.
- The model is a simple lognormal with 72-hour realised vol. A big "edge" often means the model is too simple (vol smile, event risk) rather than free money. This is not financial advice.
- Prices are mids or last prices, not executable depth. Paper P&L ignores fees, funding and slippage. Hedges often hit the 2x-stake cap.
- 1Click without a JWT charges a 0.2% fee (rule Q-006), and no JWT is used.

## Files
`agent.py` (scanner, sizing, NEAR leg, record/replay) · `chainsig.py` (read-only Chain Signatures derivation, mainnet and testnet) · `paper.py` (paper ledger and P&L) · `tests/` · `fixtures/` (recorded real data) · `docs/DEMO.md` (video script) · `docs/SUBMISSION.md` (submission draft).

## Libraries and provenance
It uses the Python standard library only. Keccak-256, base58 and secp256k1 are implemented in `chainsig.py`. `chainsig.js` and `viem` were used once, outside the repo, to produce the test vectors. All code was written during the hackathon window, from the first commit on 2026-11-03, with AI assistance, so there is no pre-hackathon baseline. Public APIs: Polymarket Gamma, Kalshi, Hyperliquid info, NEAR RPC (mainnet and testnet), and NEAR Intents 1Click. License: MIT (see `LICENSE`).
