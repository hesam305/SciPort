#!/usr/bin/env python3
"""
Collect data on new perpetual-futures listings for backtesting the
"initial pump -> dump -> short" pattern.

Pure standard library (Python 3.8+), no pip install needed.

Usage:
    python collect_new_listings.py --exchange binance
    python collect_new_listings.py --exchange bybit --months 12
    python collect_new_listings.py --exchange gate

Output:
    data/<exchange>/listings.csv
    data/<exchange>/<SYMBOL>/k5m.csv      5-minute candles from listing (default 14 days)
    data/<exchange>/<SYMBOL>/k1h.csv      1-hour candles from listing (default 60 days)
    data/<exchange>/<SYMBOL>/funding.csv  funding-rate history over the same window
    new_listings_<exchange>.zip           everything above, ready to upload

Resumable: files that already exist are skipped, so re-running after an
interruption continues where it stopped.

Candle CSV columns : open_time_ms,open,high,low,close,volume,quote_volume
Funding CSV columns: time_ms,rate
"""

import argparse
import csv
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import zipfile

MIN = 60_000
HOUR = 60 * MIN
DAY = 24 * HOUR


# ---------------------------------------------------------------- HTTP ----

def http_get(url, params=None, retries=6):
    if params:
        url = url + "?" + urllib.parse.urlencode(params)
    delay = 2
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "listing-research/1.0"})
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.loads(r.read().decode())
        except urllib.error.HTTPError as e:
            body = e.read().decode(errors="replace")[:300]
            if e.code == 451 or e.code == 403:
                sys.exit(f"\nHTTP {e.code} from {url}\n"
                         "The exchange is blocking your location/IP. Turn on a VPN "
                         "or try another --exchange.\n")
            if e.code in (418, 429):
                wait = int(e.headers.get("Retry-After", 60))
                print(f"  rate limited, sleeping {wait}s")
                time.sleep(wait)
                continue
            if 400 <= e.code < 500:
                raise RuntimeError(f"HTTP {e.code}: {body}")
            print(f"  HTTP {e.code}, retry in {delay}s")
        except (urllib.error.URLError, TimeoutError, ConnectionError, json.JSONDecodeError) as e:
            print(f"  network error ({e}), retry in {delay}s")
        time.sleep(delay)
        delay = min(delay * 2, 60)
    raise RuntimeError(f"giving up on {url}")


# ------------------------------------------------------------ Binance ----

class Binance:
    BASE = "https://fapi.binance.com"
    PAUSE = 0.15

    def listings(self):
        info = http_get(self.BASE + "/fapi/v1/exchangeInfo")
        out = []
        for s in info["symbols"]:
            if s.get("contractType") != "PERPETUAL" or s.get("quoteAsset") != "USDT":
                continue
            out.append({"symbol": s["symbol"], "listed_ms": int(s["onboardDate"]),
                        "status": s.get("status", "")})
        return out

    def klines(self, symbol, interval, start, end):
        rows, cur = [], start
        while cur < end:
            data = http_get(self.BASE + "/fapi/v1/klines", {
                "symbol": symbol, "interval": interval, "startTime": cur,
                "endTime": end - 1, "limit": 1500})
            time.sleep(self.PAUSE)
            if not data:
                break
            for k in data:
                rows.append([int(k[0]), k[1], k[2], k[3], k[4], k[5], k[7]])
            nxt = int(data[-1][0]) + 1
            if nxt <= cur or len(data) < 1500:
                break
            cur = nxt
        return rows

    def funding(self, symbol, start, end):
        rows, cur = [], start
        while cur < end:
            data = http_get(self.BASE + "/fapi/v1/fundingRate", {
                "symbol": symbol, "startTime": cur, "endTime": end, "limit": 1000})
            time.sleep(self.PAUSE)
            if not data:
                break
            rows += [[int(f["fundingTime"]), f["fundingRate"]] for f in data]
            if len(data) < 1000:
                break
            cur = int(data[-1]["fundingTime"]) + 1
        return rows


# -------------------------------------------------------------- Bybit ----

class Bybit:
    BASE = "https://api.bybit.com"
    PAUSE = 0.12
    IV = {"5m": "5", "1h": "60"}

    def listings(self):
        out, cursor = [], ""
        while True:
            p = {"category": "linear", "limit": 1000}
            if cursor:
                p["cursor"] = cursor
            r = http_get(self.BASE + "/v5/market/instruments-info", p)["result"]
            for s in r["list"]:
                if s.get("contractType") == "LinearPerpetual" and s.get("quoteCoin") == "USDT":
                    out.append({"symbol": s["symbol"], "listed_ms": int(s["launchTime"]),
                                "status": s.get("status", "")})
            cursor = r.get("nextPageCursor")
            if not cursor:
                return out

    def klines(self, symbol, interval, start, end):
        step = 5 * MIN if interval == "5m" else HOUR
        rows, cur = {}, start
        while cur < end:
            chunk_end = min(end - 1, cur + 1000 * step - 1)
            r = http_get(self.BASE + "/v5/market/kline", {
                "category": "linear", "symbol": symbol, "interval": self.IV[interval],
                "start": cur, "end": chunk_end, "limit": 1000})["result"]
            time.sleep(self.PAUSE)
            for k in r["list"]:  # newest first
                rows[int(k[0])] = [int(k[0]), k[1], k[2], k[3], k[4], k[5], k[6]]
            cur = chunk_end + 1
        return [rows[t] for t in sorted(rows)]

    def funding(self, symbol, start, end):
        rows, cur_end = {}, end
        while cur_end > start:
            r = http_get(self.BASE + "/v5/market/funding/history", {
                "category": "linear", "symbol": symbol, "startTime": start,
                "endTime": cur_end, "limit": 200})["result"]["list"]
            time.sleep(self.PAUSE)
            if not r:
                break
            for f in r:
                rows[int(f["fundingRateTimestamp"])] = f["fundingRate"]
            oldest = min(int(f["fundingRateTimestamp"]) for f in r)
            if len(r) < 200 or oldest - 1 >= cur_end:
                break
            cur_end = oldest - 1
        return [[t, rows[t]] for t in sorted(rows)]


# --------------------------------------------------------------- Gate ----

class Gate:
    BASE = "https://api.gateio.ws/api/v4/futures/usdt"
    PAUSE = 0.25

    def listings(self):
        out = []
        for c in http_get(self.BASE + "/contracts"):
            if c.get("in_delisting"):
                status = "DELISTING"
            else:
                status = "TRADING"
            created = c.get("create_time") or c.get("launch_time")
            if not created:
                continue
            out.append({"symbol": c["name"], "listed_ms": int(float(created) * 1000),
                        "status": status})
        return out

    def klines(self, symbol, interval, start, end):
        step = 5 * MIN if interval == "5m" else HOUR
        rows, cur = {}, start
        while cur < end:
            chunk_end = min(end - step, cur + 1999 * step)
            data = http_get(self.BASE + "/candlesticks", {
                "contract": symbol, "interval": interval,
                "from": cur // 1000, "to": chunk_end // 1000})
            time.sleep(self.PAUSE)
            for k in data:
                t = int(k["t"]) * 1000
                rows[t] = [t, k["o"], k["h"], k["l"], k["c"], k.get("v", 0), k.get("sum", 0)]
            cur = chunk_end + step
        return [rows[t] for t in sorted(rows)]

    def funding(self, symbol, start, end):
        data = http_get(self.BASE + "/funding_rate", {
            "contract": symbol, "limit": 1000,
            "from": start // 1000, "to": end // 1000})
        time.sleep(self.PAUSE)
        rows = {int(f["t"]) * 1000: f["r"] for f in data}
        return [[t, rows[t]] for t in sorted(rows) if start <= t < end]


EXCHANGES = {"binance": Binance, "bybit": Bybit, "gate": Gate}


# ---------------------------------------------------------------- main ----

def write_csv(path, header, rows):
    tmp = path + ".tmp"
    with open(tmp, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(header)
        w.writerows(rows)
    os.replace(tmp, path)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--exchange", choices=EXCHANGES, default="binance")
    ap.add_argument("--months", type=float, default=18, help="how far back to look for listings")
    ap.add_argument("--days-5m", type=int, default=14, help="days of 5m candles after listing")
    ap.add_argument("--days-1h", type=int, default=60, help="days of 1h candles after listing")
    ap.add_argument("--out", default="data")
    ap.add_argument("--no-zip", action="store_true")
    args = ap.parse_args()

    ex = EXCHANGES[args.exchange]()
    root = os.path.join(args.out, args.exchange)
    os.makedirs(root, exist_ok=True)

    now = int(time.time() * 1000)
    since = now - int(args.months * 30 * DAY)

    print(f"[{args.exchange}] fetching contract list ...")
    listings = sorted((l for l in ex.listings() if l["listed_ms"] >= since),
                      key=lambda l: l["listed_ms"])
    write_csv(os.path.join(root, "listings.csv"), ["symbol", "listed_ms", "listed_utc", "status"],
              [[l["symbol"], l["listed_ms"],
                time.strftime("%Y-%m-%d %H:%M", time.gmtime(l["listed_ms"] / 1000)), l["status"]]
               for l in listings])
    print(f"  {len(listings)} USDT perpetuals listed in the last {args.months:g} months")

    failed = []
    for i, l in enumerate(listings, 1):
        sym, t0 = l["symbol"], l["listed_ms"]
        d = os.path.join(root, sym)
        os.makedirs(d, exist_ok=True)
        jobs = [
            ("k5m.csv", lambda: ex.klines(sym, "5m", t0, min(now, t0 + args.days_5m * DAY)), "k"),
            ("k1h.csv", lambda: ex.klines(sym, "1h", t0, min(now, t0 + args.days_1h * DAY)), "k"),
            ("funding.csv", lambda: ex.funding(sym, t0, min(now, t0 + args.days_1h * DAY)), "f"),
        ]
        todo = [j for j in jobs if not os.path.exists(os.path.join(d, j[0]))]
        if not todo:
            continue
        print(f"[{i}/{len(listings)}] {sym}  listed {time.strftime('%Y-%m-%d', time.gmtime(t0 / 1000))}")
        for name, fn, kind in todo:
            try:
                rows = fn()
            except RuntimeError as e:
                print(f"  {name}: {e}")
                failed.append(f"{sym}/{name}")
                continue
            header = (["open_time_ms", "open", "high", "low", "close", "volume", "quote_volume"]
                      if kind == "k" else ["time_ms", "rate"])
            write_csv(os.path.join(d, name), header, rows)
            print(f"  {name}: {len(rows)} rows")

    if failed:
        print(f"\n{len(failed)} downloads failed (re-run to retry): {', '.join(failed[:10])}")

    if not args.no_zip:
        zpath = f"new_listings_{args.exchange}.zip"
        with zipfile.ZipFile(zpath, "w", zipfile.ZIP_DEFLATED) as z:
            for base, _, files in os.walk(root):
                for fn in files:
                    if not fn.endswith(".tmp"):
                        full = os.path.join(base, fn)
                        z.write(full, os.path.relpath(full, args.out))
        print(f"\nDone -> {zpath} ({os.path.getsize(zpath) / 1e6:.1f} MB)")


if __name__ == "__main__":
    main()
