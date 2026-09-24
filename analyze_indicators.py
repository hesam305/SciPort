#!/usr/bin/env python3
"""
Technical indicators (moving averages, RSI, Bollinger Bands, MACD, VWAP, ATR)
applied to the new-listing short, within the first 10 days after listing.

Part A - indicators as FILTERS at the fixed 24h entry of the base rule
         (first-24h pump < 20%, short at 24h, 2x, SL 45%, close by day 10).
         Indicators are computed on 15m bars from the first 24h only.

Part B - indicators as ENTRY TIMING between hour 24 and day 9 (1h bars):
         the first indicator signal after 24h opens the short; exit at SL or day 10.

Usage:
    python analyze_indicators.py new_listings_binance-archive.zip
"""

import argparse
import statistics as st
from types import SimpleNamespace

import analyze_10d as a10
import backtest as bt

DAY, HOUR, MIN = bt.DAY, bt.HOUR, bt.MIN


# ----------------------------------------------------------- indicators ---

def ema(xs, n):
    out, k, e = [], 2 / (n + 1), None
    for x in xs:
        e = x if e is None else e + k * (x - e)
        out.append(e)
    return out


def sma(xs, n):
    out, s = [], 0.0
    for i, x in enumerate(xs):
        s += x
        if i >= n:
            s -= xs[i - n]
        out.append(s / n if i >= n - 1 else None)
    return out


def rsi(xs, n=14):
    out, g, l = [None] * len(xs), 0.0, 0.0
    for i in range(1, len(xs)):
        d = xs[i] - xs[i - 1]
        up, dn = max(d, 0), max(-d, 0)
        if i <= n:
            g += up / n
            l += dn / n
            if i < n:
                continue
        else:
            g = (g * (n - 1) + up) / n
            l = (l * (n - 1) + dn) / n
        out[i] = 100.0 if l == 0 else 100 - 100 / (1 + g / l)
    return out


def bollinger(xs, n=20, k=2.0):
    mid, up, lo = [], [], []
    for i in range(len(xs)):
        if i < n - 1:
            mid.append(None); up.append(None); lo.append(None)
            continue
        w = xs[i - n + 1:i + 1]
        m, sd = st.mean(w), st.pstdev(w)
        mid.append(m); up.append(m + k * sd); lo.append(m - k * sd)
    return mid, up, lo


def atr(h, l, c, n=14):
    tr = [h[0] - l[0]] + [max(h[i] - l[i], abs(h[i] - c[i - 1]), abs(l[i] - c[i - 1])) for i in range(1, len(c))]
    return ema(tr, n)


# ------------------------------------------------------------- resample ---

def bars(c, minutes, until_ms=None):
    """Resample 5m candles to `minutes` bars anchored at listing time.
    Each bar also carries the index of its last 5m candle (entry = next one)."""
    size = minutes * MIN
    out = []  # [t, o, h, l, c, v_quote, last_5m_idx]
    for i, t in enumerate(c.t):
        if until_ms is not None and t >= until_ms:
            break
        b = (t - c.t0) // size
        if out and out[-1][7] == b:
            r = out[-1]
            r[2] = max(r[2], c.h[i]); r[3] = min(r[3], c.l[i]); r[4] = c.c[i]
            r[5] += c.qv[i] if c.qv else 0.0
            r[6] = i
        else:
            out.append([c.t0 + b * size, c.o[i], c.h[i], c.l[i], c.c[i], c.qv[i] if c.qv else 0.0, i, b])
    return out


# ---------------------------------------------------------- simulation ----

def sim(c, ei, days, cfg, sl):
    """Short at open of 5m candle ei, exit at SL / liquidation / end of `days`."""
    end = c.idx_at(c.t0 + days * DAY) - 1
    if ei is None or ei >= end:
        return None
    entry, et, L = c.o[ei], c.t[ei], cfg.leverage
    liq = entry * (1 + 1 / L - 0.01)
    xi, xp, why = end, c.c[end], "time"
    for i in range(ei, end + 1):
        if sl is not None and c.h[i] >= entry * (1 + sl) and entry * (1 + sl) < liq:
            xi, xp, why = i, entry * (1 + sl) * (1 + cfg.slippage), "sl"
            break
        if c.h[i] >= liq:
            xi, xp, why = i, None, "liq"
            break
    if why == "liq":
        return {"ret": -1.0, "exit": why, "t0": c.t0}
    fund = L * c.funding_sum(et, c.t[xi]) / entry
    ret = max(-1.0, L * (entry - xp) / entry - cfg.fee * L * (1 + xp / entry) + fund)
    return {"ret": ret, "exit": why, "t0": c.t0, "entry_h": (et - c.t0) / HOUR}


def summary(ts):
    if not ts:
        return f"{'n=  0':<44}"
    r = [t["ret"] for t in ts]
    w, l = sum(x for x in r if x > 0), -sum(x for x in r if x < 0)
    return (f"n={len(r):>3} mean={st.mean(r) * 100:>+6.1f}% win={sum(x > 0 for x in r) / len(r):>4.0%} "
            f"PF={min(w / l if l else 99, 99):>5.2f}")


def periods(ts, cuts):
    parts = [[t for t in ts if t["t0"] < cuts[0]], [t for t in ts if cuts[0] <= t["t0"] < cuts[1]],
             [t for t in ts if t["t0"] >= cuts[1]]]
    return " | ".join(f"{st.mean(x['ret'] for x in p) * 100:+5.1f}%({len(p)})" if p else "    -    " for p in parts)


def consistent(ts, cuts):
    parts = [[t for t in ts if t["t0"] < cuts[0]], [t for t in ts if cuts[0] <= t["t0"] < cuts[1]],
             [t for t in ts if t["t0"] >= cuts[1]]]
    return all(p and st.mean(x["ret"] for x in p) > 0 for p in parts)


# ---------------------------------------------------- part A: filters -----

def features_24h(c):
    b = bars(c, 15, c.t0 + DAY)
    if len(b) < 40:
        return None
    cl = [x[4] for x in b]
    hi, lo = [x[2] for x in b], [x[3] for x in b]
    r = rsi(cl)[-1]
    mid, up, dn = bollinger(cl)
    e9, e21, e50 = ema(cl, 9)[-1], ema(cl, 21)[-1], ema(cl, 50)[-1]
    macd = [a - b_ for a, b_ in zip(ema(cl, 12), ema(cl, 26))]
    hist = macd[-1] - ema(macd, 9)[-1]
    vq = [x[5] for x in b]
    vol_base = sum(vq)
    vwap = (sum(((x[2] + x[3] + x[4]) / 3) * x[5] for x in b) / vol_base) if vol_base else cl[-1]
    a = atr(hi, lo, cl)[-1]
    return {
        "RSI(14) 15m": r,
        "Bollinger %B": (cl[-1] - dn[-1]) / (up[-1] - dn[-1]) if up[-1] != dn[-1] else 0.5,
        "Bollinger width %": (up[-1] - dn[-1]) / mid[-1] * 100,
        "price vs EMA50 %": (cl[-1] / e50 - 1) * 100,
        "EMA9 vs EMA21 %": (e9 / e21 - 1) * 100,
        "MACD hist (sign)": 1 if hist > 0 else -1,
        "price vs VWAP %": (cl[-1] / vwap - 1) * 100,
        "ATR % of price": a / cl[-1] * 100,
    }


FIXED_BINS = {
    "RSI(14) 15m": [(0, 30, "<30 oversold"), (30, 50, "30-50"), (50, 70, "50-70"), (70, 101, ">70 overbought")],
    "Bollinger %B": [(-9, 0, "below lower band"), (0, 0.5, "lower half"), (0.5, 1, "upper half"),
                     (1, 9, "above upper band")],
    "MACD hist (sign)": [(-2, 0, "negative"), (0, 2, "positive")],
    "EMA9 vs EMA21 %": [(-1e9, 0, "EMA9 < EMA21 (down)"), (0, 1e9, "EMA9 > EMA21 (up)")],
    "price vs VWAP %": [(-1e9, 0, "below VWAP"), (0, 1e9, "above VWAP")],
    "price vs EMA50 %": [(-1e9, 0, "below EMA50"), (0, 1e9, "above EMA50")],
}


def part_a(coins, cfg, cuts):
    print("=== A. Indicators at the 24h entry (base rule: pump<20%, short at 24h, SL 45%, day 10) ===")
    rows = []
    for c in coins:
        if a10.pump24(c) >= 0.2:
            continue
        f = features_24h(c)
        t = sim(c, c.idx_at(c.t0 + DAY), 10, cfg, 0.45)
        if f and t:
            t.update(f)
            rows.append(t)
    print(f"  all            {summary(rows)}   periods: {periods(rows, cuts)}\n")
    for name in rows[0]:
        if name in ("ret", "exit", "t0", "entry_h"):
            continue
        print(f"  --- {name}")
        bins = FIXED_BINS.get(name)
        if not bins:
            v = sorted(r[name] for r in rows)
            q1, q2 = v[len(v) // 3], v[2 * len(v) // 3]
            bins = [(-1e9, q1, f"low (<{q1:.3g})"), (q1, q2, "mid"), (q2, 1e9, f"high (>{q2:.3g})")]
        for lo, hi, lab in bins:
            g = [r for r in rows if lo <= r[name] < hi]
            mark = "  <== consistent" if len(g) >= 20 and consistent(g, cuts) and st.mean(
                x["ret"] for x in g) > st.mean(x["ret"] for x in rows) else ""
            print(f"     {lab:22} {summary(g)}   periods: {periods(g, cuts)}{mark}")
    return rows


# ----------------------------------------------- part B: entry timing -----

def signals_1h(c):
    """Yield (name, 5m entry index) for the first time each signal fires after 24h."""
    b = bars(c, 60, c.t0 + 9 * DAY)
    if len(b) < 30:
        return {}
    cl = [x[4] for x in b]
    hi = [x[2] for x in b]
    r = rsi(cl)
    mid, up, dn = bollinger(cl)
    e9, e21 = ema(cl, 9), ema(cl, 21)
    s20 = sma(cl, 20)
    macd = [x - y for x, y in zip(ema(cl, 12), ema(cl, 26))]
    sig = ema(macd, 9)
    first = {}

    def hit(name, k):
        if name not in first and b[k][0] >= c.t0 + 23 * HOUR:  # bar closing at/after 24h
            first[name] = b[k][6] + 1

    for k in range(1, len(b)):
        if r[k] is not None and r[k - 1] is not None:
            if r[k - 1] >= 70 > r[k]:
                hit("RSI falls back below 70", k)
            if r[k - 1] >= 60 > r[k]:
                hit("RSI falls back below 60", k)
            if r[k - 1] >= 50 > r[k]:
                hit("RSI crosses below 50", k)
        if up[k] is not None and up[k - 1] is not None:
            if hi[k - 1] >= up[k - 1] and cl[k] < up[k]:
                hit("Bollinger: upper band rejection", k)
            if cl[k - 1] >= mid[k - 1] and cl[k] < mid[k]:
                hit("Bollinger: close below middle", k)
            if cl[k] < dn[k]:
                hit("Bollinger: close below lower band", k)
        if e9[k - 1] >= e21[k - 1] and e9[k] < e21[k] and k >= 21:
            hit("EMA9 crosses below EMA21", k)
        if s20[k] is not None and s20[k - 1] is not None and cl[k - 1] >= s20[k - 1] and cl[k] < s20[k]:
            hit("close crosses below SMA20", k)
        if k >= 34 and macd[k - 1] >= sig[k - 1] and macd[k] < sig[k]:
            hit("MACD crosses below signal", k)
        if (r[k] is not None and r[k] < 50 and e9[k] < e21[k] and k >= 21
                and s20[k] is not None and cl[k] < s20[k]):
            hit("combo: RSI<50 & EMA9<EMA21 & close<SMA20", k)
    return first


def part_b(coins, cfg, cuts):
    print("\n=== B. Indicator-timed entries (1h bars, first signal after 24h, exit SL or day 10) ===")
    res = {}
    for c in coins:
        pump = a10.pump24(c)
        for name, ei in signals_1h(c).items():
            for sl in (0.3, 0.45):
                t = sim(c, ei, 10, cfg, sl)
                if t:
                    t["pump"] = pump
                    res.setdefault((name, sl), []).append(t)
    for universe, keep in (("all listings", lambda t: True), ("pump<20% only", lambda t: t["pump"] < 0.2)):
        print(f"\n  -- {universe}")
        ranked = []
        for (name, sl), ts in res.items():
            g = [t for t in ts if keep(t)]
            if len(g) >= 20:
                ranked.append((st.mean(t["ret"] for t in g), name, sl, g))
        ranked.sort(reverse=True)
        for m, name, sl, g in ranked:
            mark = "  <== consistent" if consistent(g, cuts) else ""
            print(f"     {name:42} SL={sl:<4} {summary(g)}  periods: {periods(g, cuts)}{mark}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("data")
    a = ap.parse_args()
    coins, _ = bt.load(a.data, min_bars=0)
    coins = [c for c in coins if c.t[-1] >= c.t0 + 10 * DAY - 5 * MIN]
    src = bt.Source(a.data)
    for c in coins:
        c.qv = [float(r[6] or 0) for r in src.rows(f"{c.symbol}/k5m.csv")]
    t0s = sorted(c.t0 for c in coins)
    cuts = (t0s[len(t0s) // 3], t0s[2 * len(t0s) // 3])
    cfg = SimpleNamespace(leverage=2, fee=0.0005, slippage=0.002)
    print(f"{len(coins)} listings, 2x short, all trades closed by day 10\n")
    part_a(coins, cfg, cuts)
    part_b(coins, cfg, cuts)


if __name__ == "__main__":
    main()
