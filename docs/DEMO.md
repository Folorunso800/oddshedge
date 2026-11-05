# Demo video script (about 90 seconds, screen recording)

The rules (Q-012) say a local-only demo is fine as long as the X post has a **video**. Screenshots alone are not enough, so record a video.

| Time | Show | Say |
| --- | --- | --- |
| 0–10s | A Polymarket "Ethereum above $X on <date>" page next to a Kalshi ETH page | "Prediction markets and perps often disagree on the same question: will ETH be above $2,500 on Sunday?" |
| 10–25s | Terminal: type `./demo.sh` and press Enter | "OddsHedge reads Polymarket, Kalshi and Hyperliquid. It's all public data, with no keys and no account." |
| 25–45s | Highlight one line and its `PROPOSE:` | "The market says 14%, while the perp-implied model says 27%. It proposes a small YES bet plus a short perp hedge on Hyperliquid, so I'm not just betting on direction. Size is capped at 5% of the bankroll." |
| 45–65s | Highlight the "NEAR leg" block | "NEAR moves the money. Chain Signatures gives my NEAR account its own Hyperliquid address with no extra private key. A live NEAR Intents 1Click quote shows the USDC arriving there in about 20 seconds." |
| 65–80s | The `booked N paper positions` and P&L lines | "Each idea becomes a paper position, and `paper.py mark` re-prices it later from live data, so you can see whether the edge was real." |
| 80–90s | `python3 -m unittest` showing OK, then the GitHub repo | "It's a dry run, with nothing signed or sent, and it's tested offline on real recorded data. The repo is open, with the link below." |

Tips:
- Make the terminal font large and crop to the terminal.
- Skip the setup footage.
- If live data shows `no edges above threshold`, use `./demo.sh replay` and say "replaying real data from Nov 5".

# Draft X post (Mari posts it herself; nothing is posted by the bot)

Prediction markets and perps often disagree on the same question: "will ETH be above $2,500 on Sunday?"

I built OddsHedge at NEAR HACKATHON to catch that gap. It reads Polymarket and Kalshi odds, prices the same strike from Hyperliquid perp data, and proposes a bet plus a perp hedge, so you're not just betting on direction.

NEAR handles the money. Chain Signatures gives one NEAR account its own Hyperliquid address, and a NEAR Intents quote moves the USDC there in about 20 seconds. It's paper trading only, with nothing signed.

Repo: <GITHUB LINK>

When odds and perps disagree, which one do you trust more?

@NEARProtocol #NEARHackathon @NearBuilders @NearLegion
(attach the demo video)
