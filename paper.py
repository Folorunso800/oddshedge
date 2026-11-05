#!/usr/bin/env python3
"""OddsHedge paper ledger. PAPER MONEY ONLY: nothing is bought, sold or signed.

  python3 paper.py open  [proposals.json]   # book the agent's proposals as paper positions
  python3 paper.py mark                     # re-price every open position with live public data, show P&L
  python3 paper.py show                     # print the ledger without fetching anything

Each position = a binary bet (YES/NO shares bought at the market price) + a Hyperliquid perp hedge.
P&L = binary leg (current price - entry) * shares  +  perp leg (current mid - entry mid) * signed size.
When a market has resolved, its final price (0 or 1) is used. Fees and funding are ignored (stated in README)."""
import json, sys, os, datetime as dt
import agent

LEDGER = os.environ.get("ODDSHEDGE_LEDGER", "paper_ledger.json")

def load():
    return json.load(open(LEDGER)) if os.path.exists(LEDGER) else {"note": "PAPER positions only", "positions": []}
def save(d): json.dump(d, open(LEDGER, "w"), indent=1)

def open_positions(proposals_file="proposals.json"):
    p = json.load(open(proposals_file)); d = load()
    have = {(x["market_id"], x["opened"]) for x in d["positions"]}
    n = 0
    for x in p["proposals"]:
        if not x.get("market_id") or (x["market_id"], p["generated"]) in have: continue
        price = x["yes"] if x["side"] == "YES" else 1 - x["yes"]
        d["positions"].append({"opened": p["generated"], "from_replay": p.get("replay", False), "venue": x["venue"],
            "market_id": x["market_id"], "q": x["q"], "side": x["side"], "entry_price": round(price, 4),
            "shares": round(x["stake_usd"] / price, 4), "stake_usd": x["stake_usd"], "coin": x["coin"],
            "perp_size": x["hedge_coin"], "perp_entry": x["spot"], "url": x["url"], "status": "open"})
        n += 1
    save(d); print(f"booked {n} paper positions in {LEDGER}"); return n

def yes_price(venue, market_id):
    """Current YES price and whether the market is settled. Raises on failure."""
    if venue == "Polymarket":
        m = agent.get(f"https://gamma-api.polymarket.com/markets/{market_id}")
        yes = float(json.loads(m["outcomePrices"])[0]); return yes, bool(m.get("closed"))
    m = agent.get(f"https://api.elections.kalshi.com/trade-api/v2/markets/{market_id}")["market"]
    if m.get("result") in ("yes", "no"): return (1.0 if m["result"] == "yes" else 0.0), True
    bid, ask = float(m.get("yes_bid_dollars") or 0), float(m.get("yes_ask_dollars") or 0)
    if bid <= 0 or ask <= 0: raise RuntimeError("no two-sided quote right now")
    return (bid + ask) / 2, False

def pnl(pos, yes_now, mid_now):
    price_now = yes_now if pos["side"] == "YES" else 1 - yes_now
    bet = (price_now - pos["entry_price"]) * pos["shares"]
    hedge = (mid_now - pos["perp_entry"]) * pos["perp_size"]
    return round(bet, 2), round(hedge, 2)

def mark():
    d = load(); mids = {}
    try: mids = {k: float(v) for k, v in agent.post(agent.HL, {"type": "allMids"}).items() if k in ("BTC", "ETH")}
    except Exception as ex: print(f"(hyperliquid unavailable: {ex}; hedge leg not marked)")
    tot = 0.0
    for pos in d["positions"]:
        try: yes, settled = yes_price(pos["venue"], pos["market_id"])
        except Exception as ex:
            print(f"- {pos['q'][:60]} : could not price ({ex}); kept last mark"); continue
        mid = mids.get(pos["coin"], pos["perp_entry"])
        b, h = pnl(pos, yes, mid)
        pos.update(last_yes=yes, last_mid=mid, bet_pnl=b, hedge_pnl=h, total_pnl=round(b + h, 2),
                   marked=agent.now().strftime("%Y-%m-%dT%H:%M:%SZ"), status="settled" if settled else "open")
        tot += b + h
        print(f"- [{pos['venue']}] {pos['side']} {pos['q'][:58]} | bet {b:+.2f}  hedge {h:+.2f}  = {b+h:+.2f} USD ({pos['status']})")
    save(d); print(f"paper P&L total {tot:+.2f} USD over {len(d['positions'])} positions (paper money, fees/funding ignored)")
    return tot

def show():
    for p in load()["positions"]:
        print(f"- {p['opened']} [{p['venue']}] {p['side']} ${p['stake_usd']} {p['q'][:60]} | {p['status']} | P&L {p.get('total_pnl', 'not marked')}")

if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "show"
    {"open": lambda: open_positions(*(sys.argv[2:3] or ["proposals.json"])), "mark": mark, "show": show}[cmd]()
