#!/usr/bin/env python3
"""
Extra entry filters for the 10-day short rule
(first-24h pump < 20% -> short at 24h, 2x, SL 45%, close by day 10).

Every feature uses only data available at entry time (24h after listing):
  vol24     : USDT volume traded in the first 24h
  chg24     : price at 24h vs first open
  from_peak : price at 24h vs the 24h high
  funding   : last funding rate before entry (negative = shorts are paying)
  btc7d     : BTC return over the 7 days before entry (needs _market/BTCUSDT_1h.csv)

Usage:
    python analyze_filters.py new_listings_binance-archive.zip
"""

import argparse
import bisect
import statistics as st
from types import SimpleNamespace

import analyze_10d as a10
import backtest as bt

DAY, HOUR = bt.DAY, bt.HOUR


def load_btc(path):
    src = bt.Source(path)
    rows = src.rows("_market/BTCUSDT_1h.csv")
    if not rows:
        return None
    return [int(r[0]) for r in rows], [float(r[4]) for r in rows]


def btc_ret(btc, ts, days):
    t, c = btc
    i = bisect.bisect_right(t, ts) - 1
    j = bisect.bisect_right(t, ts - days * DAY) - 1
    if i < 0 or j < 0:
        return None
    return c[i] / c[j] - 1


def features(c, btc):
    e = c.idx_at(c.t0 + DAY)
    et = c.t[e] if e < len(c.t) else c.t0 + DAY
    vol = 0.0
    src_q = getattr(c, "qv", None)
    if src_q:
        vol = sum(src_q[:e])
    fi = bisect.bisect_right(c.f_t, et) - 1
    f = {
        "vol24": vol,
        "chg24": c.c[e - 1] / c.o[0] - 1,
        "from_peak": c.c[e - 1] / max(c.h[:e]) - 1,
        "funding": c.f_rates[fi] if fi >= 0 else 0.0,
    }
    if btc:
        f["btc7d"] = btc_ret(btc, et, 7)
    return f


def summary(ts):
    if not ts:
        return "n=  0"
    r = [t["ret"] for t in ts]
    w, l = sum(x for x in r if x > 0), -sum(x for x in r if x < 0)
    return (f"n={len(r):>3} mean={st.mean(r) * 100:>+6.1f}% win={sum(x > 0 for x in r) / len(r):>4.0%} "
            f"PF={min(w / l if l else 99, 99):>5.2f}")


def by_period(ts, cuts):
    parts = [[t for t in ts if t["t0"] < cuts[0]],
             [t for t in ts if cuts[0] <= t["t0"] < cuts[1]],
             [t for t in ts if t["t0"] >= cuts[1]]]
    return " | ".join(f"{st.mean(t['ret'] for t in p) * 100:+5.1f}%({len(p)})" if p else "   -   " for p in parts)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("data")
    a = ap.parse_args()

    coins, _ = bt.load(a.data, min_bars=0)
    coins = [c for c in coins if c.t[-1] >= c.t0 + 10 * DAY - 5 * bt.MIN]
    # quote volume isn't kept by backtest.Coin; read it here
    src = bt.Source(a.data)
    for c in coins:
        rows = src.rows(f"{c.symbol}/k5m.csv")
        c.qv = [float(r[6] or 0) for r in rows]
    btc = load_btc(a.data)

    cfg = SimpleNamespace(leverage=2, fee=0.0005, slippage=0.002)
    a10.SLS, a10.TPS = [0.45], [None]
    trades = []
    for c in coins:
        if a10.pump24(c) >= 0.2:
            continue
        f = features(c, btc)
        for t in a10.trades_for(c, ("delay", 24, None), 10, cfg):
            t.update(f)
            trades.append(t)
    t0s = sorted(t["t0"] for t in trades)
    cuts = (t0s[len(t0s) // 3], t0s[2 * len(t0s) // 3])

    print(f"base rule: {summary(trades)}   periods: {by_period(trades, cuts)}")
    print(f"BTC data: {'yes' if btc else 'no (re-run collector for _market/BTCUSDT_1h.csv)'}\n")

    names = ["vol24", "chg24", "from_peak", "funding"] + (["btc7d"] if btc else [])
    for name in names:
        ts = [t for t in trades if t.get(name) is not None]
        vals = sorted(t[name] for t in ts)
        qs = [vals[int(len(vals) * k / 3)] for k in (1, 2)]
        print(f"--- {name} (split into thirds at {qs[0]:.4g} / {qs[1]:.4g})")
        for lab, lo, hi in (("low", -1e18, qs[0]), ("mid", qs[0], qs[1]), ("high", qs[1], 1e18)):
            g = [t for t in ts if lo <= t[name] < hi]
            print(f"   {lab:5} {summary(g)}   periods: {by_period(g, cuts)}")
        if name in ("btc7d", "funding", "chg24"):
            for lab, cond in (("< 0", lambda x: x < 0), (">= 0", lambda x: x >= 0)):
                g = [t for t in ts if cond(t[name])]
                print(f"   {lab:5} {summary(g)}   periods: {by_period(g, cuts)}")
        print()


if __name__ == "__main__":
    main()
