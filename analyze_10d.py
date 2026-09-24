#!/usr/bin/env python3
"""
The first 10 days after listing: what the price path looks like, and how a
2x short performs when every trade must be closed by the end of day 10.

Usage:
    python analyze_10d.py new_listings_binance-archive.zip [--days 10]

Reuses the loader and conventions of backtest.py (returns on margin, fees,
funding, SL-before-TP within a bar, liquidation = -100%).
"""

import argparse
import statistics as st

import backtest as bt

HOUR, DAY = bt.HOUR, bt.DAY
DELAYS_H = [1, 4, 12, 24, 48, 72, 96, 120]
DROPS = [0.2, 0.3, 0.4]
SLS = [None, 0.2, 0.3, 0.45]
TPS = [None, 0.3, 0.5]
PUMP_BINS = [(-1, 0.2, "pump<20%"), (0.2, 0.5, "pump 20-50%"), (0.5, 1, "pump 50-100%"), (1, 1e9, "pump>100%")]


def q(xs, p):
    xs = sorted(xs)
    return xs[min(len(xs) - 1, int(p * len(xs)))]


def qline(xs):
    return "  ".join(f"p{int(p * 100)}={q(xs, p):+.0f}" for p in (0.1, 0.25, 0.5, 0.75, 0.9))


def pump24(c):
    w = c.idx_at(c.t0 + 24 * HOUR)
    return max(c.h[:w]) / c.o[0] - 1 if w else 0.0


# ------------------------------------------------------------- anatomy ----

def anatomy(coins, days):
    print(f"\n=== A. Price path over the first {days} days (% vs first open) ===")
    for d in (1, 2, 3, 5, 7, days):
        xs = [(c.c[c.idx_at(c.t0 + d * DAY) - 1] / c.o[0] - 1) * 100 for c in coins]
        print(f"  day {d:>2}: {qline(xs)}   below open: {sum(x < 0 for x in xs) / len(xs):.0%}")

    pk_t, pk_g, dd, tr_t = [], [], [], []
    for c in coins:
        end = c.idx_at(c.t0 + days * DAY)
        pi = max(range(end), key=lambda i: c.h[i])
        pk_t.append((c.t[pi] - c.t0) / DAY)
        pk_g.append((c.h[pi] / c.o[0] - 1) * 100)
        dd.append((c.c[end - 1] / c.h[pi] - 1) * 100)
        ti = min(range(end), key=lambda i: c.l[i])
        tr_t.append((c.t[ti] - c.t0) / DAY)
    print(f"\n  {days}-day peak gain %        : {qline(pk_g)}")
    print(f"  day of {days}-day peak        : " + "  ".join(
        f"{lab} {sum(lo <= x < hi for x in pk_t) / len(pk_t):.0%}"
        for lo, hi, lab in ((0, 1 / 24, "<1h"), (1 / 24, 1, "1h-1d"), (1, 3, "d1-3"), (3, 6, "d3-6"), (6, 99, "d6+"))))
    print(f"  day of {days}-day low         : " + "  ".join(
        f"{lab} {sum(lo <= x < hi for x in tr_t) / len(tr_t):.0%}"
        for lo, hi, lab in ((0, 1, "d0-1"), (1, 3, "d1-3"), (3, 6, "d3-6"), (6, 8, "d6-8"), (8, 99, "d8+"))))
    print(f"  day-{days} close vs peak %    : {qline(dd)}")

    print(f"\n  by first-24h pump:  {'n':>4} {'peak day med':>13} {'day-' + str(days) + ' vs open med':>17} {'vs 24h close med':>17}")
    for lo, hi, lab in PUMP_BINS:
        g = [c for c in coins if lo <= pump24(c) < hi]
        if not g:
            continue
        end = [c.idx_at(c.t0 + days * DAY) - 1 for c in g]
        pd = st.median((c.t[max(range(e + 1), key=lambda i: c.h[i])] - c.t0) / DAY for c, e in zip(g, end))
        vo = st.median((c.c[e] / c.o[0] - 1) * 100 for c, e in zip(g, end))
        v24 = st.median((c.c[e] / c.c[c.idx_at(c.t0 + DAY) - 1] - 1) * 100 for c, e in zip(g, end))
        print(f"  {lab:18} {len(g):>4} {pd:>13.1f} {vo:>+17.1f} {v24:>+17.1f}")


# ---------------------------------------------------------------- trades --

def entry_idx(c, rule, days):
    kind, a, wait_h = rule
    last = c.idx_at(c.t0 + (days - 1) * DAY)  # need at least a day to work
    if kind == "delay":
        i = c.idx_at(c.t0 + a * HOUR)
        return i if i < last else None
    peak, start = 0.0, c.idx_at(c.t0 + wait_h * HOUR)
    for i in range(last):
        peak = max(peak, c.h[i])
        if i >= start and c.c[i] <= peak * (1 - a):
            return i + 1
    return None


def trades_for(c, rule, days, a):
    ei = entry_idx(c, rule, days)
    if ei is None:
        return []
    end = c.idx_at(c.t0 + days * DAY) - 1
    entry, et, L = c.o[ei], c.t[ei], a.leverage
    liq = entry * (1 + 1 / L - 0.01)
    out = []
    for sl in SLS:
        for tp in TPS:
            xi, xp, why = end, c.c[end], "time"
            for i in range(ei, end + 1):
                if c.h[i] >= liq and (sl is None or entry * (1 + sl) >= liq):
                    xi, xp, why = i, None, "liq"
                    break
                if sl is not None and c.h[i] >= entry * (1 + sl):
                    xi, xp, why = i, entry * (1 + sl) * (1 + a.slippage), "sl"
                    break
                if tp is not None and c.l[i] <= entry * (1 - tp):
                    xi, xp, why = i, entry * (1 - tp), "tp"
                    break
            if why == "liq":
                ret, fund = -1.0, 0.0
            else:
                fund = L * c.funding_sum(et, c.t[xi]) / entry
                ret = max(-1.0, L * (entry - xp) / entry - a.fee * L * (1 + xp / entry) + fund)
            out.append({"rule": rule, "sl": sl, "tp": tp, "ret": ret, "fund": fund, "exit": why,
                        "t0": c.t0, "pump": pump24(c), "entry_h": (et - c.t0) / HOUR,
                        "sym": c.symbol, "et": et, "xt": c.t[xi]})
    return out


def rname(rule):
    kind, a, w = rule
    return f"delay {a:g}h" if kind == "delay" else f"drop {a:.0%} from peak (>{w}h)"


def stats(ts):
    r = [t["ret"] for t in ts]
    if not r:
        return None
    w = sum(x for x in r if x > 0)
    l = -sum(x for x in r if x < 0)
    return {"n": len(r), "mean": st.mean(r), "med": st.median(r), "win": sum(x > 0 for x in r) / len(r),
            "pf": w / l if l else 99.0, "fund": st.mean(t["fund"] for t in ts),
            "liq": sum(t["exit"] == "liq" for t in ts)}


def fmt(s):
    if not s:
        return f"{'-':>44}"
    return (f"n={s['n']:>3} mean={s['mean'] * 100:>+6.1f}% med={s['med'] * 100:>+6.1f}% "
            f"win={s['win']:>4.0%} PF={min(s['pf'], 99):>4.2f}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("data")
    ap.add_argument("--days", type=int, default=10)
    ap.add_argument("--leverage", type=float, default=2)
    ap.add_argument("--fee", type=float, default=0.0005)
    ap.add_argument("--slippage", type=float, default=0.002)
    a = ap.parse_args()

    coins, _ = bt.load(a.data, min_bars=0)
    coins = [c for c in coins if c.t[-1] >= c.t0 + a.days * DAY - 5 * bt.MIN]
    print(f"{len(coins)} listings with a full {a.days}-day window, leverage {a.leverage:g}x, "
          f"all trades closed by day {a.days}")
    anatomy(coins, a.days)

    rules = ([("delay", d, None) for d in DELAYS_H] + [("drop", d, 4) for d in DROPS]
             + [("drop", d, 24) for d in DROPS])
    trades = [t for c in coins for r in rules for t in trades_for(c, r, a.days, a)]
    thirds = sorted({c.t0 for c in coins})
    cut1, cut2 = thirds[len(thirds) // 3], thirds[2 * len(thirds) // 3]

    print(f"\n=== B. Short, held until SL/TP or end of day {a.days} (no filter) ===")
    for r in rules[:len(DELAYS_H) + len(DROPS)]:
        for sl, tp in ((None, None), (0.3, None), (0.45, 0.5)):
            s = stats([t for t in trades if t["rule"] == r and t["sl"] == sl and t["tp"] == tp])
            print(f"  {rname(r):24} SL={str(sl):4} TP={str(tp):4} {fmt(s)} fund={s['fund'] * 100:+.1f}% liq={s['liq']}")

    print(f"\n=== C. By first-24h pump (entries at/after 24h so the filter is known) ===")
    late = [r for r in rules if r[1] >= 24 if r[0] == "delay"] + [r for r in rules if r[0] == "drop" and r[2] == 24]
    best = []
    for lo, hi, lab in PUMP_BINS:
        print(f"  -- {lab}")
        for r in late:
            for sl in SLS:
                for tp in TPS:
                    ts = [t for t in trades if t["rule"] == r and t["sl"] == sl and t["tp"] == tp
                          and lo <= t["pump"] < hi]
                    s = stats(ts)
                    if not s or s["n"] < 15:
                        continue
                    parts = [stats([t for t in ts if t["t0"] < cut1]),
                             stats([t for t in ts if cut1 <= t["t0"] < cut2]),
                             stats([t for t in ts if t["t0"] >= cut2])]
                    best.append((lab, r, sl, tp, s, parts))
                    if sl in (None, 0.3) and tp in (None, 0.5):
                        print(f"    {rname(r):24} SL={str(sl):4} TP={str(tp):4} {fmt(s)} liq={s['liq']}")

    print(f"\n=== D. Most robust setups: positive in all three time periods, ranked by worst period ===")
    robust = [b for b in best if all(p and p["mean"] > 0 for p in b[5])]
    robust.sort(key=lambda b: min(p["mean"] for p in b[5]), reverse=True)
    for lab, r, sl, tp, s, parts in robust[:15]:
        per = " | ".join(f"{p['mean'] * 100:+5.1f}% (n={p['n']})" for p in parts)
        print(f"  {lab:13} {rname(r):24} SL={str(sl):4} TP={str(tp):4} all: {s['mean'] * 100:+5.1f}% "
              f"win {s['win']:.0%} PF {min(s['pf'], 99):.2f} | periods: {per}")
    if not robust:
        print("  none")


if __name__ == "__main__":
    main()
