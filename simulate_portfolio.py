#!/usr/bin/env python3
"""
Account simulation for the rule found in analyze_10d.py:
  first-24h pump < 20%  ->  short 24h after listing, 2x, SL 45%, close by day 10,
  optionally filtered to (24h change < -8% OR funding < 0 at entry).

Positions overlap in time; each new trade uses a fixed share of current equity
as margin, with a cap on simultaneous positions. Profits are compounded.

Usage:
    python simulate_portfolio.py new_listings_binance-archive.zip --capital 200
"""

import argparse
import statistics as st
import time
from types import SimpleNamespace

import analyze_10d as a10
import backtest as bt


def month(ms):
    return time.strftime("%Y-%m", time.gmtime(ms / 1000))


def run(trades, capital, frac, max_pos):
    events = sorted(trades, key=lambda t: t["et"])
    equity, open_pos, taken, skipped = capital, [], 0, 0
    curve = [(events[0]["et"], capital)]
    peak, max_dd = capital, 0.0

    def close_until(ts):
        nonlocal equity, peak, max_dd
        open_pos.sort(key=lambda p: p[0])
        while open_pos and open_pos[0][0] <= ts:
            xt, margin, ret = open_pos.pop(0)
            equity += margin * ret
            curve.append((xt, equity))
            peak = max(peak, equity)
            max_dd = max(max_dd, 1 - equity / peak)

    for t in events:
        close_until(t["et"])
        used = sum(p[1] for p in open_pos)
        margin = equity * frac
        if len(open_pos) >= max_pos or used + margin > equity or equity < 10:
            skipped += 1
            continue
        open_pos.append((t["xt"], margin, t["ret"]))
        taken += 1
    close_until(float("inf"))

    months = {}
    for ts, eq in curve:
        months[month(ts)] = eq
    keys = sorted(months)
    rets, prev = [], capital
    for k in keys:
        rets.append((k, months[k] / prev - 1, months[k]))
        prev = months[k]
    return {"final": equity, "max_dd": max_dd, "taken": taken, "skipped": skipped, "months": rets}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("data")
    ap.add_argument("--capital", type=float, default=200)
    ap.add_argument("--rule", choices=["base", "filtered"], default="filtered",
                    help="filtered = base rule plus (24h change < -8%% OR funding < 0 at entry)")
    ap.add_argument("--extra-slippage", type=float, default=0.0,
                    help="extra cost per side on top of fees (e.g. 0.005 = 0.5%%)")
    a = ap.parse_args()

    coins, _ = bt.load(a.data, min_bars=0)
    coins = [c for c in coins if c.t[-1] >= c.t0 + 10 * bt.DAY - 5 * bt.MIN]
    cfg = SimpleNamespace(leverage=2, fee=0.0005 + a.extra_slippage, slippage=0.002 + a.extra_slippage)
    a10.SLS, a10.TPS = [0.45], [None]
    import analyze_filters as af
    for c in coins:
        c.qv = []

    def keep(c):
        if a10.pump24(c) >= 0.2:
            return False
        if a.rule == "base":
            return True
        f = af.features(c, None)
        return f["chg24"] < -0.08 or f["funding"] < 0

    trades = [t for c in coins if keep(c) for t in a10.trades_for(c, ("delay", 24, None), 10, cfg)]
    span_m = (max(t["xt"] for t in trades) - min(t["et"] for t in trades)) / (30.4 * bt.DAY)
    print(f"rule={a.rule}: {len(trades)} signals over {span_m:.1f} months, starting capital ${a.capital:g}, "
          f"extra cost/side {a.extra_slippage:.2%}\n")

    print(f"{'margin/trade':>12} {'max pos':>7} | {'final $':>9} {'avg month':>9} {'median':>7} "
          f"{'worst':>7} {'best':>7} {'losing months':>13} {'max drawdown':>12} {'trades':>6}")
    results = {}
    for frac in (0.05, 0.10, 0.15, 0.20):
        for max_pos in (5, 10):
            r = run(trades, a.capital, frac, max_pos)
            m = [x[1] for x in r["months"]]
            geo = (r["final"] / a.capital) ** (1 / len(m)) - 1
            results[(frac, max_pos)] = r
            print(f"{frac:>12.0%} {max_pos:>7} | {r['final']:>9.0f} {geo:>+9.1%} {st.median(m):>+7.1%} "
                  f"{min(m):>+7.1%} {max(m):>+7.1%} {sum(x < 0 for x in m):>6}/{len(m):<6} "
                  f"{r['max_dd']:>12.1%} {r['taken']:>6}")

    r = results[(0.10, 10)]
    print("\nmonth by month, 10% margin per trade, max 10 positions:")
    for k, ret, eq in r["months"]:
        print(f"  {k}  {ret:>+7.1%}  equity ${eq:,.0f}")


if __name__ == "__main__":
    main()
