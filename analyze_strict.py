#!/usr/bin/env python3
"""
Stricter entry conditions: fewer trades, more confidence?

Builds entry tiers from loose to strict (all: short at 24h after listing,
2x, SL 45%, close by day 10) and reports for each tier:
  - trades, win rate, mean return per trade (on margin)
  - bootstrap 90% confidence interval of the mean, and P(mean > 0)
  - mean in each of three time periods
  - a $200 account simulation at several margin sizes (overlapping positions)

Usage:
    python analyze_strict.py new_listings_binance-archive.zip --capital 200
"""

import argparse
import random
import statistics as st
from types import SimpleNamespace

import analyze_10d as a10
import analyze_filters as af
import analyze_indicators as ai
import backtest as bt
import simulate_portfolio as sp

DAY = bt.DAY

TIERS = [
    ("T0 base: pump<20%",
     lambda t: True),
    ("T1 current: +(drop>8% or funding<0) +ATR>=0.65%",
     lambda t: (t["chg24"] < -0.08 or t["funding"] < 0) and t["atr"] >= 0.65),
    ("T2: T1 + below VWAP + EMA9<EMA21",
     lambda t: (t["chg24"] < -0.08 or t["funding"] < 0) and t["atr"] >= 0.65
     and t["vwap"] < 0 and t["ema"] < 0),
    ("T3: drop>8% AND funding<0 +ATR>=0.65%",
     lambda t: t["chg24"] < -0.08 and t["funding"] < 0 and t["atr"] >= 0.65),
    ("T4: T1 + ATR>=1.2% + below VWAP + RSI<=60",
     lambda t: (t["chg24"] < -0.08 or t["funding"] < 0) and t["atr"] >= 1.2
     and t["vwap"] < 0 and t["rsi"] <= 60),
    ("T5: drop>12% AND funding<0 +ATR>=1.2% +below VWAP",
     lambda t: t["chg24"] < -0.12 and t["funding"] < 0 and t["atr"] >= 1.2 and t["vwap"] < 0),
]


def bootstrap(r, n=4000, seed=7):
    rng = random.Random(seed)
    means = sorted(st.mean(rng.choice(r) for _ in r) for _ in range(n))
    return means[int(0.05 * n)], means[int(0.95 * n)], sum(m > 0 for m in means) / n


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("data")
    ap.add_argument("--capital", type=float, default=200)
    a = ap.parse_args()

    coins, _ = bt.load(a.data, min_bars=0)
    coins = [c for c in coins if c.t[-1] >= c.t0 + 10 * DAY - 5 * bt.MIN]
    src = bt.Source(a.data)
    cfg = SimpleNamespace(leverage=2, fee=0.0005, slippage=0.002)
    rows = []
    for c in coins:
        if a10.pump24(c) >= 0.2:
            continue
        c.qv = [float(r[6] or 0) for r in src.rows(f"{c.symbol}/k5m.csv")]
        ind, f = ai.features_24h(c), af.features(c, None)
        t = ai.sim(c, c.idx_at(c.t0 + DAY), 10, cfg, 0.45)
        if not (ind and t):
            continue
        t.update(chg24=f["chg24"], funding=f["funding"], atr=ind["ATR % of price"],
                 vwap=ind["price vs VWAP %"], ema=ind["EMA9 vs EMA21 %"], rsi=ind["RSI(14) 15m"])
        rows.append(t)
    t0s = sorted(c.t0 for c in coins)
    cuts = (t0s[len(t0s) // 3], t0s[2 * len(t0s) // 3])
    months = (max(t["xt"] for t in rows) - min(t["et"] for t in rows)) / (30.4 * DAY)

    print(f"{len(rows)} base trades over {months:.1f} months; short at 24h, 2x, SL 45%, close by day 10\n")
    print(f"{'tier':50} {'n':>4} {'/mo':>4} {'win':>5} {'mean':>7} {'90% CI of mean':>17} {'P>0':>5} {'worst':>6}  periods")
    picked = []
    for name, fn in TIERS:
        g = [t for t in rows if fn(t)]
        if len(g) < 5:
            print(f"{name:50} {len(g):>4}  too few")
            continue
        r = [t["ret"] for t in g]
        lo, hi, p = bootstrap(r)
        print(f"{name:50} {len(g):>4} {len(g) / months:>4.1f} {sum(x > 0 for x in r) / len(r):>5.0%} "
              f"{st.mean(r) * 100:>+6.1f}% [{lo * 100:>+5.1f}%, {hi * 100:>+5.1f}%] {p:>5.0%} "
              f"{min(r) * 100:>+5.0f}%  {ai.periods(g, cuts)}")
        picked.append((name, g))

    print(f"\n${a.capital:g} account, compounding, overlapping positions (max 10):")
    print(f"{'tier':50} {'margin':>6} | {'final $':>8} {'avg/mo':>7} {'$/mo now':>8} {'worst mo':>8} "
          f"{'losing':>6} {'max DD':>6}")
    for name, g in picked:
        for frac in (0.10, 0.20, 0.30):
            r = sp.run(g, a.capital, frac, 10)
            m = [x[1] for x in r["months"]]
            geo = (r["final"] / a.capital) ** (1 / len(m)) - 1
            print(f"{name:50} {frac:>6.0%} | {r['final']:>8.0f} {geo:>+7.1%} {a.capital * geo:>8.1f} "
                  f"{min(m):>+8.1%} {sum(x < 0 for x in m):>3}/{len(m):<2} {r['max_dd']:>6.1%}")
        print()


if __name__ == "__main__":
    main()
