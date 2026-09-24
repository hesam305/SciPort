#!/usr/bin/env python3
"""
Signal bot for the new-listing short rule (Binance USDT-M perpetuals).

Rule (from analyze_10d.py / analyze_filters.py):
  24h after listing, if
      high of first 24h < first price * 1.20             (no big pump)
  and (price at 24h < first price * 0.92  OR  funding rate < 0)
  -> SHORT, leverage 2, stop loss +45% above entry, close at day 10.

The bot only sends alerts; it never places orders.

Run it every 15-60 minutes (cron, Task Scheduler, or a loop):
    python signal_bot.py                 # one pass
    python signal_bot.py --loop 900      # run forever, every 15 min

Telegram (optional): set TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID env vars,
otherwise alerts are printed. State is kept in signal_state.json.

Needs access to fapi.binance.com (VPN from Iran; it is blocked from US servers).
"""

import argparse
import json
import os
import time
import urllib.parse
import urllib.request

BASE = "https://fapi.binance.com"
HOUR, DAY = 3_600_000, 86_400_000
PUMP_MAX, DROP_MIN, SL, LEVERAGE, HOLD_DAYS = 0.20, -0.08, 0.45, 2, 10
STATE = "signal_state.json"


def get(path, **params):
    url = BASE + path + ("?" + urllib.parse.urlencode(params) if params else "")
    req = urllib.request.Request(url, headers={"User-Agent": "listing-signal/1.0"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode())


def notify(text):
    print(time.strftime("%Y-%m-%d %H:%M UTC", time.gmtime()), "|", text.replace("\n", " | "), flush=True)
    token, chat = os.environ.get("TELEGRAM_BOT_TOKEN"), os.environ.get("TELEGRAM_CHAT_ID")
    if not (token and chat):
        return
    data = urllib.parse.urlencode({"chat_id": chat, "text": text}).encode()
    try:
        urllib.request.urlopen(f"https://api.telegram.org/bot{token}/sendMessage", data, timeout=20)
    except Exception as e:
        print("  telegram failed:", e)


def load_state():
    try:
        with open(STATE) as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def save_state(s):
    tmp = STATE + ".tmp"
    with open(tmp, "w") as f:
        json.dump(s, f, indent=1)
    os.replace(tmp, STATE)


def evaluate(sym, t0):
    """Returns (is_signal, info dict) using the first 24h after listing."""
    k = get("/fapi/v1/klines", symbol=sym, interval="5m", startTime=t0, endTime=t0 + DAY - 1, limit=300)
    if len(k) < 200:
        return False, {"reason": f"only {len(k)} candles in first 24h"}
    first, high = float(k[0][1]), max(float(x[2]) for x in k)
    price = float(get("/fapi/v1/ticker/price", symbol=sym)["price"])
    funding = float(get("/fapi/v1/premiumIndex", symbol=sym)["lastFundingRate"])
    pump, chg = high / first - 1, price / first - 1
    info = {"first": first, "price": price, "pump24": pump, "chg24": chg, "funding": funding}
    ok = pump < PUMP_MAX and (chg < DROP_MIN or funding < 0)
    if not ok:
        info["reason"] = ("pumped" if pump >= PUMP_MAX else "no drop and funding >= 0")
    return ok, info


def run_once(state):
    now = int(time.time() * 1000)
    info = get("/fapi/v1/exchangeInfo")
    for s in info["symbols"]:
        if s.get("contractType") != "PERPETUAL" or s.get("quoteAsset") != "USDT":
            continue
        sym, t0 = s["symbol"], int(s["onboardDate"])
        age = now - t0
        if age > (HOLD_DAYS + 1) * DAY or age < 0:
            continue
        st = state.setdefault(sym, {"listed": t0, "status": "watching"})
        if st["status"] == "watching" and age < DAY:
            continue
        if st["status"] == "watching":
            try:
                ok, d = evaluate(sym, t0)
            except Exception as e:
                print(f"  {sym}: {e}")
                continue
            st.update(d)
            if ok and age < DAY + 6 * HOUR:  # don't chase a signal that is hours stale
                st["status"] = "signaled"
                st["entry"] = d["price"]
                notify(
                    f"SHORT {sym}\n"
                    f"entry ~{d['price']:.6g}, leverage {LEVERAGE}x\n"
                    f"stop loss {d['price'] * (1 + SL):.6g} (+{SL:.0%})\n"
                    f"close by {time.strftime('%Y-%m-%d %H:%M UTC', time.gmtime((t0 + HOLD_DAYS * DAY) / 1000))}\n"
                    f"24h: high +{d['pump24']:.1%}, now {d['chg24']:+.1%} vs first price, "
                    f"funding {d['funding'] * 100:+.4f}%")
            else:
                st["status"] = "skipped"
                print(f"  {sym}: skip ({d.get('reason', 'signal too old')})")
        elif st["status"] == "signaled" and age >= HOLD_DAYS * DAY:
            st["status"] = "closed"
            notify(f"CLOSE {sym}: day {HOLD_DAYS} reached (entry ~{st['entry']:.6g}).")
    # forget symbols older than the window
    for sym in [k for k, v in state.items() if now - v["listed"] > (HOLD_DAYS + 2) * DAY]:
        del state[sym]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--loop", type=int, default=0, help="seconds between passes (0 = run once)")
    a = ap.parse_args()
    while True:
        state = load_state()
        try:
            run_once(state)
        except Exception as e:
            print("pass failed:", e)
        save_state(state)
        if not a.loop:
            break
        time.sleep(a.loop)


if __name__ == "__main__":
    main()
