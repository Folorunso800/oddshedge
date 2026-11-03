#!/usr/bin/env python3
"""OddsHedge: reads public Polymarket + Kalshi crypto price odds, compares them to a
volatility model built from Hyperliquid perp data, and proposes delta-hedged
(binary + perp) positions. Funding legs are expressed as NEAR Intents 1Click
quote requests with dry=true. DRY RUN ONLY: no keys, no wallets, no orders."""
import json, math, re, sys, time, argparse, urllib.request, urllib.error, datetime as dt
import chainsig

UA = {"User-Agent": "oddshedge/0.1", "Content-Type": "application/json"}
def get(url):
    return json.load(urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=20))
def post(url, body, tries=3):
    r = urllib.request.Request(url, data=json.dumps(body).encode(), headers=UA, method="POST")
    for i in range(tries):
        try: return json.load(urllib.request.urlopen(r, timeout=20))
        except urllib.error.HTTPError as ex:
            if ex.code < 500 or i == tries-1:
                try: msg = json.load(ex).get("message", "")
                except Exception: msg = ""
                raise RuntimeError(f"HTTP {ex.code} {msg}".strip()) from None
        except (urllib.error.URLError, TimeoutError) as ex:
            if i == tries-1: raise RuntimeError(f"network error: {ex}") from None
        time.sleep(1.5*(i+1))

HL = "https://api.hyperliquid.xyz/info"
def hl_mid(coin): return float(post(HL, {"type": "allMids"})[coin])
def hl_vol(coin, hours=72):
    now = int(time.time()*1000)
    c = post(HL, {"type": "candleSnapshot", "req": {"coin": coin, "interval": "1h", "startTime": now-hours*3600_000, "endTime": now}})
    px = [float(x["c"]) for x in c]
    r = [math.log(b/a) for a, b in zip(px, px[1:])]
    m = sum(r)/len(r); var = sum((x-m)**2 for x in r)/(len(r)-1)
    return math.sqrt(var*24*365)  # annualised
def hl_funding(coin):
    meta, ctx = post(HL, {"type": "metaAndAssetCtxs"})
    i = [a["name"] for a in meta["universe"]].index(coin)
    return float(ctx[i]["funding"])

def N(x): return 0.5*(1+math.erf(x/math.sqrt(2)))
def model(spot, strike, vol, years):
    years = max(years, 1/8760)
    d2 = (math.log(spot/strike) - 0.5*vol*vol*years)/(vol*math.sqrt(years))
    prob = N(d2)
    delta = math.exp(-d2*d2/2)/math.sqrt(2*math.pi)/(spot*vol*math.sqrt(years))  # dP/dS per $1
    return prob, delta

def years_to(iso):
    t = dt.datetime.fromisoformat(iso.replace("Z", "+00:00"))
    return (t - dt.datetime.now(dt.timezone.utc)).total_seconds()/(365*86400)

def polymarket(asset_name):
    out = []
    try: evs = get("https://gamma-api.polymarket.com/events?limit=100&active=true&closed=false&tag_slug=crypto&order=volume24hr&ascending=false")
    except Exception as ex:
        print(f"  (polymarket unavailable: {ex})"); return out
    for e in evs:
        if not re.match(rf"{asset_name} above ___ on", e["title"]): continue
        for m in e.get("markets", []):
            if m.get("closed") or not m.get("outcomePrices"): continue
            k = re.search(r"\$([\d,\.]+)", m["question"])
            if not k: continue
            p = float(json.loads(m["outcomePrices"])[0])
            out.append({"venue": "Polymarket", "q": m["question"], "strike": float(k.group(1).replace(",", "")),
                        "yes": p, "end": m["endDate"], "url": f"https://polymarket.com/event/{e['slug']}"})
    return out

def kalshi(series):
    out = []
    try:
        d = get(f"https://api.elections.kalshi.com/trade-api/v2/markets?series_ticker={series}&status=open&limit=200")
    except Exception as ex:
        print(f"  (kalshi unavailable: {ex})"); return out
    for m in d.get("markets", []):
        if m.get("floor_strike") is None: continue
        bid, ask = float(m.get("yes_bid_dollars") or 0), float(m.get("yes_ask_dollars") or 0)
        if ask <= 0 or ask >= 1: continue
        out.append({"venue": "Kalshi", "q": f"{m['ticker']} >= {m['floor_strike']}", "strike": float(m["floor_strike"]),
                    "yes": (bid+ask)/2 if bid else ask, "end": m["close_time"],
                    "url": f"https://kalshi.com/markets/{m['event_ticker'].lower()}"})
    return out

ONECLICK = "https://1click.chaindefuser.com/v0/quote"  # docs: https://docs.near-intents.org/near-intents/integration/distribution-channels/1click-api
USDC_NEAR = "nep141:17208628f84f5d6ad33f0da3bbbeb27ffcb398eac501a31bd6ad2011e36133a1"   # native USDC on NEAR
USDC_HYPERCORE = "1cs_v1:hypercore:hip1:0x6d1e7cde53ba9467b783cb7c530ce054"            # USDC on Hyperliquid (HyperCore)
DEMO_ACCOUNT, DEMO_PATH = "oddshedge-demo.near", "hyperliquid-1"
FALLBACK_RECIPIENT = "0x000000000000000000000000000000000000dEaD"  # only if Chain Signatures lookup fails

def hedge_account(account, path):
    """Chain Signatures: the Hyperliquid (EVM) address controlled by `account` via the NEAR MPC signer. Read-only."""
    try: return chainsig.derive_evm_address(account, path), "derived via NEAR Chain Signatures (v1.signer)"
    except Exception as ex: return FALLBACK_RECIPIENT, f"chain-signatures lookup failed ({ex}); placeholder recipient"

def intents_quote(amount_usdc, account=DEMO_ACCOUNT, path=DEMO_PATH):
    """NEAR Intents 1Click DRY quote: USDC in the NEAR Intents account -> USDC on Hyperliquid, delivered to the
    Chain-Signatures address. dry=true returns a price and no deposit address; nothing is signed or sent."""
    recipient, how = hedge_account(account, path)
    req = {"dry": True, "swapType": "EXACT_INPUT", "slippageTolerance": 100,
           "originAsset": USDC_NEAR, "depositType": "INTENTS", "destinationAsset": USDC_HYPERCORE,
           "amount": str(int(round(amount_usdc*1e6))), "refundTo": account, "refundType": "INTENTS",
           "recipient": recipient, "recipientType": "DESTINATION_CHAIN",
           "deadline": (dt.datetime.now(dt.timezone.utc)+dt.timedelta(minutes=10)).strftime("%Y-%m-%dT%H:%M:%S.000Z"),
           "referral": "oddshedge"}
    try:
        res = post(ONECLICK, req); status = "ok"
    except Exception as ex:
        res, status = None, f"unavailable ({ex}); exact request saved in proposals.json"
    return {"request": req, "status": status, "response": res, "recipient_source": how, "near_account": account, "path": path}

def run(asset, coin, kseries, bankroll, min_edge, top):
    try: spot, vol, fund = hl_mid(coin), hl_vol(coin), hl_funding(coin)
    except Exception as ex:
        print(f"\n=== {asset}: Hyperliquid unavailable ({ex}); skipping"); return []
    print(f"\n=== {asset}: Hyperliquid mid ${spot:,.2f} | 72h realised vol {vol:.0%} | funding/h {fund:.6f}")
    mk = polymarket(asset) + (kalshi(kseries) if kseries else [])
    ideas = []
    for m in mk:
        T = years_to(m["end"])
        if T*8760 < 6: continue  # skip markets <6h from expiry (gamma explodes)
        p, delta = model(spot, m["strike"], vol, T)
        edge = p - m["yes"]
        if abs(edge) < min_edge or not (0.03 < m["yes"] < 0.97): continue
        side = "YES" if edge > 0 else "NO"
        price = m["yes"] if side == "YES" else 1-m["yes"]
        stake = round(min(bankroll*0.05, bankroll*abs(edge)/max(1-price, 1e-3)*0.25), 2)  # quarter-Kelly, capped 5%
        shares = stake/price
        hedge_coin = shares*delta*(1 if side == "YES" else -1)  # long binary YES = long delta -> short perp
        cap = 2*stake/spot  # risk cap: hedge notional <= 2x stake
        capped = abs(hedge_coin) > cap
        hedge_coin = max(-cap, min(cap, hedge_coin))
        ideas.append({**m, "model": round(p, 3), "edge": round(edge, 3), "side": side, "stake_usd": stake,
                      "perp_hedge": f"{'SHORT' if hedge_coin > 0 else 'LONG'} {abs(hedge_coin):.5f} {coin}-PERP on Hyperliquid (~${abs(hedge_coin)*spot:,.2f}{', capped at 2x stake' if capped else ''})",
                      "hours_left": round(T*8760, 1)})
    ideas.sort(key=lambda x: -abs(x["edge"]))
    for i in ideas[:top]:
        print(f"- [{i['venue']}] {i['q']} | mkt {i['yes']:.3f} vs model {i['model']:.3f} (edge {i['edge']:+.3f}, {i['hours_left']}h left)")
        print(f"    PROPOSE: buy {i['side']} ${i['stake_usd']}  +  {i['perp_hedge']}   {i['url']}")
    if not ideas: print("  no edges above threshold")
    return ideas[:top]

if __name__ == "__main__":
    a = argparse.ArgumentParser(description="OddsHedge dry-run agent")
    a.add_argument("--bankroll", type=float, default=1000); a.add_argument("--min-edge", type=float, default=0.05)
    a.add_argument("--top", type=int, default=5); a.add_argument("--out", default="proposals.json")
    a.add_argument("--near-account", default=DEMO_ACCOUNT, help="NEAR account whose Chain-Signatures address receives the hedge margin (read-only)")
    a.add_argument("--path", default=DEMO_PATH, help="Chain Signatures derivation path")
    o = a.parse_args()
    print("OddsHedge (DRY RUN - no keys, no orders, no funds, nothing signed)")
    allp = run("Bitcoin", "BTC", "KXBTCD", o.bankroll, o.min_edge, o.top) + run("Ethereum", "ETH", "KXETHD", o.bankroll, o.min_edge, o.top)
    total = sum(p["stake_usd"] for p in allp)
    hedge_margin = round(total, 2)  # hedge notional <= 2x stake; at ~2x leverage this is the margin needed
    print(f"\n--- NEAR leg: fund ${hedge_margin:,.2f} of Hyperliquid hedge margin from NEAR Intents")
    q = intents_quote(max(hedge_margin, 1), o.near_account, o.path)
    print(f"Hedge account {q['request']['recipient']} ({q['recipient_source']}; account {o.near_account}, path '{o.path}')")
    print(f"1Click quote (dry=true) USDC NEAR Intents -> USDC Hyperliquid: {q['status']}")
    if q["response"]:
        r = q["response"]["quote"]
        print(f"  in {r['amountInFormatted']} USDC -> out {r['amountOutFormatted']} USDC (min {int(r['minAmountOut'])/1e8:.2f}), ~{r['timeEstimate']}s"
              f"  | signed by 1Click: {q['response'].get('signature','')[:24]}...")
    json.dump({"generated": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "dry_run": True,
               "proposals": allp, "intents": q}, open(o.out, "w"), indent=1)
    print(f"saved {o.out}")
