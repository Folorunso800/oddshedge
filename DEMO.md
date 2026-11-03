# 60-second demo outline (screen recording)

| Time | Show | Say (voice-over or captions) |
| --- | --- | --- |
| 0–8s | Polymarket "BTC above $X" page next to a Kalshi BTC page | "Polymarket and Kalshi price BTC and ETH 'above X' odds. The perp market often disagrees." |
| 8–20s | Terminal: type `./demo.sh`, press Enter | "OddsHedge reads both venues plus Hyperliquid price and volatility, all public data, no keys." |
| 20–38s | Scroll the output, highlight one line + its `PROPOSE:` | "Here the market says 25%, the perp-implied model says 5%. It proposes buy NO, plus a perp hedge on Hyperliquid so I'm not just betting on direction." |
| 38–52s | Highlight the "NEAR leg" block | "NEAR does the money movement: Chain Signatures gives my NEAR account a Hyperliquid address, and a live NEAR Intents 1Click quote moves USDC there in about 20 seconds." |
| 52–60s | `proposals.json` open, then the GitHub repo | "It's a dry run, nothing signed or sent. Repo is open, link below." |

Tips: zoom the terminal font, crop to the terminal, no setup footage.

# Draft X post (Mari publishes it herself)

Prediction markets and perps often disagree on the same question: "will BTC be above $78k tonight?"

I built OddsHedge at #NEARHackathon to catch that gap. It reads Polymarket and Kalshi odds, prices the same strike from Hyperliquid perp data, and proposes a trade plus a perp hedge so you're not just betting on direction.

NEAR handles the money: Chain Signatures gives one NEAR account its own Hyperliquid address, and a NEAR Intents quote moves the USDC there in ~20s. Dry run only, nothing signed.

Repo: <GITHUB LINK>

When odds and perps disagree, which one do you trust more?

@NEARProtocol @NearBuilders @NearLegion
