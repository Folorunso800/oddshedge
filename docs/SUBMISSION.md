# Submission draft (NOT SENT; Mari confirms every field and submits herself)

Form: https://nearhackathon.com/#apply. The deadline is **2026-11-14 23:59 UTC = Nov 15, 12:59 AM Lagos**. You get one submission per project; mistakes are fixed later through https://nearhackathon.com/request-changes.

| Field | Value |
| --- | --- |
| Project name | OddsHedge |
| Team lead's name | Mari (confirm the exact spelling) |
| Contact email | Mari's email (left out of the public repo on purpose; HACKATHON.md says not to commit personal data) |
| Team size | `1` |
| Tracks | `defi`, `agents` |
| NEAR wallet address (prize payout, **mainnet**) | **Mari must create this herself** in a NEAR wallet (e.g. `mari.near` or a 64-character implicit account) |
| Repository link | https://github.com/Folorunso800/oddshedge (already public; the latest local commits are not pushed yet) |
| Demo post link | **Mari's X post** with the demo video, tagging @NEARProtocol and #NEARHackathon |
| Consent | Mari ticks: "I agree that the organizers may use these details to review our submission and contact us about this hackathon." |

## What we built (idea field, under 2000 characters)
Polymarket and Kalshi price questions like "Will ETH be above $2,500 on Nov 9?". The perp market on Hyperliquid implies its own odds for the same question, and the two often disagree. OddsHedge is a paper-trading agent that finds these gaps. It reads public odds from Polymarket and Kalshi, plus price and volatility from Hyperliquid, and prices each strike with a volatility model. When there is a gap, it proposes a YES/NO bet (quarter-Kelly, capped at 5% of bankroll) plus a delta hedge on the Hyperliquid perp, so the trader is not just betting on direction. A paper ledger then tracks the P&L from live prices.

NEAR is how the money moves. Chain Signatures (the v1.signer MPC, also on testnet) gives one NEAR account its own Hyperliquid address with no separate private key; our derivation is checked against chainsig.js. A live NEAR Intents 1Click quote (dry: true) prices moving the USDC hedge margin from NEAR Intents to USDC on Hyperliquid at that address, taking about 20 seconds. The agent prepares its own spending, and a human approves it.

All data is real public data, either live or from a labelled real recording for offline replay. Each data source can fail without breaking the run, and 15 offline tests cover the math, the risk limits, the Chain Signatures vectors and the outages. It uses the Python standard library only, needs no API keys, and is MIT licensed. Nothing is signed or sent: it is a dry run.
