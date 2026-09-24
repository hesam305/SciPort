#!/usr/bin/env python3
"""
Backtest: short new perpetual-futures listings after the initial pump.

Pure standard library. Reads the output of collect_new_listings.py
(either the data/ folder or the zip file).

Usage:
    python backtest.py new_listings_binance.zip
    python backtest.py data/binance --leverage 2 --fee 0.0005

What it reports:
  0. Pump anatomy: how high listings pump and when they peak.
  1. Entry timing: which entry rule (fixed delay after listing, or X% drop
     from the running peak) gives the best raw short return.
  2. Funding: how much funding a short pays/receives while holding.
  3. Stop loss: max adverse excursion after entry (how often a secondary
     pump of 25-30%+ happens) and the full SL/TP/hold grid.
Parameters are ranked on the older listings (train) and checked on the
newer ones (test) to avoid fooling ourselves with curve fitting.

Conventions:
  - Returns are on margin: leverage * price move, minus fees and funding.
  - Positive funding rate => longs pay shorts => short RECEIVES it.
  - If SL and TP are touched in the same 5m bar, the SL is assumed first.
  - Stops fill at the stop price plus --slippage; a loss can't exceed the
    margin (liquidation = -100%).
"""

import argparse
import bisect
import csv
import io
import os
import statistics as st
import sys
import zipfile

MIN = 60_000
HOUR = 60 * MIN
DAY = 24 * HOUR

DELAYS_H = [0.5, 1, 2, 4, 8, 12, 24, 48]
DROP_RULES = [(d, w) for w in (1, 4) for d in (0.10, 0.15, 0.20, 0.30)]  # (drop from peak, min wait h)
SLS = [0.10, 0.15, 0.20, 0.30, 0.45, None]
TPS = [0.10, 0.20, 0.30, 0.50, None]
HOLDS_D = [1, 3, 7]


# ---------------------------------------------------------------- data ----

class Source:
    """Uniform reader over a directory or a zip produced by the collector."""

    def __init__(self, path):
        self.zip = zipfile.ZipFile(path) if zipfile.is_zipfile(path) else None
        self.path = path
        names = self.zip.namelist() if self.zip else [
            os.path.relpath(os.path.join(b, f), path) for b, _, fs in os.walk(path) for f in fs]
        lst = [n for n in names if n.replace("\\", "/").endswith("listings.csv")]
        if not lst:
            sys.exit("listings.csv not found in " + path)
        self.root = os.path.dirname(lst[0].replace("\\", "/"))
        self.names = set(n.replace("\\", "/") for n in names)

    def rows(self, rel):
        name = f"{self.root}/{rel}" if self.root else rel
        if name not in self.names:
            return None
        if self.zip:
            text = self.zip.read(name).decode()
        else:
            with open(os.path.join(self.path, name)) as f:
                text = f.read()
        r = csv.reader(io.StringIO(text))
        next(r, None)
        return list(r)


class Coin:
    def __init__(self, symbol, listed_ms, k5m, funding):
        self.symbol, self.t0 = symbol, listed_ms
        self.t = [int(k[0]) for k in k5m]
        self.o = [float(k[1]) for k in k5m]
        self.h = [float(k[2]) for k in k5m]
        self.l = [float(k[3]) for k in k5m]
        self.c = [float(k[4]) for k in k5m]
        # funding events with price at that moment; prefix sums of rate*price
        self.f_t, pref, acc = [], [0.0], 0.0
        self.f_rates = []
        for ts, rate in funding:
            ts, rate = int(ts), float(rate)
            i = bisect.bisect_right(self.t, ts) - 1
            if i < 0:
                continue
            acc += rate * self.c[i]
            self.f_t.append(ts)
            self.f_rates.append(rate)
            pref.append(acc)
        self.f_pref = pref

    def funding_sum(self, t_from, t_to):
        """Sum of rate*price for funding events in (t_from, t_to]."""
        a = bisect.bisect_right(self.f_t, t_from)
        b = bisect.bisect_right(self.f_t, t_to)
        return self.f_pref[b] - self.f_pref[a]

    def idx_at(self, ts):
        return bisect.bisect_left(self.t, ts)


def load(path, min_bars):
    src = Source(path)
    coins, skipped = [], 0
    for sym, listed_ms, *_ in src.rows("listings.csv"):
        k = src.rows(f"{sym}/k5m.csv")
        if not k or len(k) < min_bars:
            skipped += 1
            continue
        coins.append(Coin(sym, int(listed_ms), k, src.rows(f"{sym}/funding.csv") or []))
    coins.sort(key=lambda c: c.t0)
    return coins, skipped


# -------------------------------------------------------------- engine ----

def entry_index(c, rule):
    kind, a, b = rule
    if kind == "delay":
        i = c.idx_at(c.t0 + a * HOUR)
        return i if i < len(c.t) else None
    drop, wait_h = a, b
    peak = 0.0
    start = c.idx_at(c.t0 + wait_h * HOUR)
    limit = c.idx_at(c.t0 + 7 * DAY)
    for i in range(min(limit, len(c.t))):
        peak = max(peak, c.h[i])
        if i >= start and c.c[i] <= peak * (1 - drop):
            return i + 1 if i + 1 < len(c.t) else None  # enter at next bar's open
    return None


def rule_name(rule):
    kind, a, b = rule
    return f"delay {a:g}h" if kind == "delay" else f"drop {a:.0%} (after {b}h)"


def simulate_entry(c, rule, a):
    """Returns list of trade dicts for every (sl, tp, hold) combo for one entry."""
    ei = entry_index(c, rule)
    if ei is None:
        return []
    entry, et = c.o[ei], c.t[ei]
    L, fee, slip = a.leverage, a.fee, a.slippage
    liq = entry * (1 + 1 / L - 0.01)

    out = []
    for hold in HOLDS_D:
        end = min(c.idx_at(et + hold * DAY), len(c.t)) - 1
        if end <= ei or c.t[-1] < et + hold * DAY - 5 * MIN:
            continue  # not enough data for this hold
        # first bar index that crosses each SL/TP/liq level
        sl_levels = sorted(s for s in SLS if s is not None)
        tp_levels = sorted(t for t in TPS if t is not None)
        first_sl, first_tp, first_liq = {}, {}, None
        mae = 0.0
        si = ti = 0
        for i in range(ei, end + 1):
            up = c.h[i] / entry - 1
            dn = 1 - c.l[i] / entry
            mae = max(mae, up)
            while si < len(sl_levels) and up >= sl_levels[si]:
                first_sl[sl_levels[si]] = i
                si += 1
            while ti < len(tp_levels) and dn >= tp_levels[ti]:
                first_tp[tp_levels[ti]] = i
                ti += 1
            if first_liq is None and c.h[i] >= liq:
                first_liq = i
        for sl in SLS:
            for tp in TPS:
                cand = [(end, 3, c.c[end])]
                if sl is not None and sl in first_sl:
                    cand.append((first_sl[sl], 0, entry * (1 + sl) * (1 + slip)))
                if first_liq is not None:
                    cand.append((first_liq, 1, None))
                if tp is not None and tp in first_tp:
                    cand.append((first_tp[tp], 2, entry * (1 - tp)))
                xi, why, xp = min(cand)  # earliest; same bar -> SL/liq before TP
                if why == 1:
                    ret, fund = -1.0, 0.0
                else:
                    fund = L * c.funding_sum(et, c.t[xi]) / entry
                    ret = L * (entry - xp) / entry - fee * L * (1 + xp / entry) + fund
                    ret = max(ret, -1.0)
                out.append({"rule": rule, "sl": sl, "tp": tp, "hold": hold, "ret": ret,
                            "fund": fund, "mae": mae, "exit": "sl liq tp time".split()[why],
                            "sym": c.symbol, "t0": c.t0})
    return out


# ------------------------------------------------------------- reports ----

def pct(x):
    return f"{x * 100:+.1f}%" if x is not None else "   -  "


def summarize(trades):
    r = [t["ret"] for t in trades]
    if not r:
        return None
    wins = [x for x in r if x > 0]
    losses = [-x for x in r if x < 0]
    return {"n": len(r), "mean": st.mean(r), "median": st.median(r),
            "win": len(wins) / len(r), "worst": min(r),
            "pf": (sum(wins) / sum(losses)) if losses else float("inf")}


def fmt_q(xs, qs=(0.1, 0.25, 0.5, 0.75, 0.9)):
    xs = sorted(xs)
    return "  ".join(f"p{int(q * 100)}={xs[min(len(xs) - 1, int(q * len(xs)))]:.1f}" for q in qs)


def report_pump(coins):
    print("\n=== 0. Pump anatomy (5m data, relative to first open) ===")
    gains, peak_h, d1, d3, d7 = [], [], [], [], []
    for c in coins:
        o0 = c.o[0]
        w = c.idx_at(c.t0 + 3 * DAY)
        if w == 0:
            continue
        pi = max(range(w), key=lambda i: c.h[i])
        gains.append((c.h[pi] / o0 - 1) * 100)
        peak_h.append((c.t[pi] - c.t0) / HOUR)
        for days, arr in ((1, d1), (3, d3), (7, d7)):
            j = c.idx_at(c.t0 + days * DAY)
            if j < len(c.t):
                arr.append((c.c[j] / o0 - 1) * 100)
    print(f"  listings: {len(gains)}")
    print(f"  peak gain in first 3d (%)      : {fmt_q(gains)}")
    print(f"  hours from listing to peak     : {fmt_q(peak_h)}")
    for name, arr in (("1d", d1), ("3d", d3), ("7d", d7)):
        if arr:
            print(f"  price after {name} vs first open (%): {fmt_q(arr)}")


def report_timing(trades):
    print("\n=== 1. Entry timing: raw short, no SL/TP, held to time exit (all listings) ===")
    print(f"  {'entry rule':22} {'hold':>4} {'n':>4} {'mean':>8} {'median':>8} {'win':>6} {'worst':>8}")
    for rule in all_rules():
        for hold in HOLDS_D:
            s = summarize([t for t in trades if t["rule"] == rule and t["hold"] == hold
                           and t["sl"] is None and t["tp"] is None])
            if s:
                print(f"  {rule_name(rule):22} {hold:>3}d {s['n']:>4} {pct(s['mean']):>8} "
                      f"{pct(s['median']):>8} {s['win']:>6.0%} {pct(s['worst']):>8}")


def report_funding(coins, trades):
    print("\n=== 2. Funding (positive = short receives) ===")
    early = [r for c in coins for ts, r in zip(c.f_t, c.f_rates) if ts < c.t0 + 3 * DAY]
    if early:
        neg = sum(1 for r in early if r < 0) / len(early)
        print(f"  funding rates in first 3 days: n={len(early)}  mean={st.mean(early) * 100:+.4f}%  "
              f"min={min(early) * 100:+.3f}%  negative (short pays) {neg:.0%}")
    print(f"  {'entry rule':22} {'hold':>4} {'avg funding on margin':>22} {'trades paying >1%':>18}")
    for rule in all_rules():
        for hold in HOLDS_D:
            ts = [t for t in trades if t["rule"] == rule and t["hold"] == hold
                  and t["sl"] is None and t["tp"] is None]
            if ts:
                f = [t["fund"] for t in ts]
                bad = sum(1 for x in f if x < -0.01) / len(f)
                print(f"  {rule_name(rule):22} {hold:>3}d {pct(st.mean(f)):>22} {bad:>18.0%}")


def report_mae(trades):
    print("\n=== 3a. Max adverse excursion after entry (7d hold): share of trades whose price rose ... ===")
    print(f"  {'entry rule':22} {'n':>4} {'>=10%':>6} {'>=20%':>6} {'>=25%':>6} {'>=30%':>6} {'>=50%':>6}")
    for rule in all_rules():
        m = [t["mae"] for t in trades if t["rule"] == rule and t["hold"] == 7
             and t["sl"] is None and t["tp"] is None]
        if m:
            cols = "".join(f"{sum(1 for x in m if x >= th) / len(m):>7.0%}" for th in (.1, .2, .25, .3, .5))
            print(f"  {rule_name(rule):22} {len(m):>4}{cols}")


def report_grid(trades, split_t, top, min_n, out_csv):
    print(f"\n=== 3b. Full grid ranked on TRAIN (older listings), checked on TEST (newer) ===")
    groups = {}
    for t in trades:
        groups.setdefault((t["rule"], t["sl"], t["tp"], t["hold"]), []).append(t)
    rows = []
    for key, ts in groups.items():
        tr = summarize([t for t in ts if t["t0"] < split_t])
        te = summarize([t for t in ts if t["t0"] >= split_t])
        if tr and tr["n"] >= min_n:
            rows.append((key, tr, te))
    rows.sort(key=lambda r: r[1]["mean"], reverse=True)

    print(f"  {'entry rule':22} {'SL':>5} {'TP':>5} {'hold':>4} | {'n':>3} {'mean':>7} {'win':>5} {'PF':>5}"
          f" | {'n':>3} {'mean':>7} {'win':>5} {'PF':>5}")
    print(f"  {'':22} {'':>5} {'':>5} {'':>4} | {'----- train -----':^23} | {'------ test -----':^23}")
    for (rule, sl, tp, hold), tr, te in rows[:top]:
        tes = (f"{te['n']:>3} {pct(te['mean']):>7} {te['win']:>5.0%} {min(te['pf'], 99):>5.2f}"
               if te else "   no test trades")
        print(f"  {rule_name(rule):22} {('-' if sl is None else f'{sl:.0%}'):>5} "
              f"{('-' if tp is None else f'{tp:.0%}'):>5} {hold:>3}d | {tr['n']:>3} {pct(tr['mean']):>7} "
              f"{tr['win']:>5.0%} {min(tr['pf'], 99):>5.2f} | {tes}")

    with open(out_csv, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["entry_rule", "sl", "tp", "hold_d", "train_n", "train_mean", "train_median",
                    "train_win", "train_pf", "train_worst", "test_n", "test_mean", "test_median",
                    "test_win", "test_pf", "test_worst"])
        for (rule, sl, tp, hold), tr, te in rows:
            te = te or {k: "" for k in tr}
            w.writerow([rule_name(rule), sl or "", tp or "", hold,
                        tr["n"], tr["mean"], tr["median"], tr["win"], tr["pf"], tr["worst"],
                        te["n"], te["mean"], te["median"], te["win"], te["pf"], te["worst"]])
    print(f"\n  full grid written to {out_csv}")


def all_rules():
    return [("delay", d, None) for d in DELAYS_H] + [("drop", d, w) for d, w in DROP_RULES]


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("data", help="zip from collect_new_listings.py or data/<exchange> folder")
    ap.add_argument("--leverage", type=float, default=2)
    ap.add_argument("--fee", type=float, default=0.0005, help="taker fee per side (0.05%%)")
    ap.add_argument("--slippage", type=float, default=0.002, help="extra adverse fill on stops")
    ap.add_argument("--train-frac", type=float, default=0.6)
    ap.add_argument("--top", type=int, default=25)
    ap.add_argument("--min-trades", type=int, default=15)
    ap.add_argument("--out", default="grid_results.csv")
    a = ap.parse_args()

    coins, skipped = load(a.data, min_bars=12 * 24)
    if not coins:
        sys.exit("no usable listings found")
    split_t = coins[int(len(coins) * a.train_frac)].t0 if len(coins) > 1 else coins[0].t0 + 1
    print(f"loaded {len(coins)} listings ({skipped} skipped: <1 day of data)")
    print(f"leverage {a.leverage:g}x, fee {a.fee:.3%}/side, stop slippage {a.slippage:.2%}")

    trades = []
    for c in coins:
        for rule in all_rules():
            trades += simulate_entry(c, rule, a)

    report_pump(coins)
    report_timing(trades)
    report_funding(coins, trades)
    report_mae(trades)
    report_grid(trades, split_t, a.top, a.min_trades, a.out)


if __name__ == "__main__":
    main()
