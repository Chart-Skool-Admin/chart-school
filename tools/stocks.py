"""Real stock candles for Chart School's Stocks track (Yahoo Finance chart API, no key).

  python tools/stocks.py history   -> stocks-data.js  (baked-in history, like rw-data.js)
  python tools/stocks.py live      -> live/stocks-live.json (recent candles for the live chart)

Times: daily candles sit at 00:00 UTC of their date. Intraday candles are stored in
New York wall-clock time written as if it were UTC, so 09:30 means the US open all year.
"""
import json, sys, time, urllib.request, datetime as dt
from zoneinfo import ZoneInfo

NY = ZoneInfo("America/New_York")
TICKERS = ["SPY", "QQQ", "AAPL", "NVDA", "TSLA", "MSFT", "AMZN", "META"]
H1 = ["SPY", "AAPL", "NVDA"]          # 1-hour sets (like BTC/ETH/SOL 1-hour)
M30 = ["SPY", "QQQ", "AAPL"]          # 30-minute sessions for Market Profile
UA = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15"}


def fetch(t, interval, days):
    now = int(time.time())
    p1 = now - days * 86400
    last = None
    for host in ("query1", "query2"):
        for attempt in range(4):
            url = (f"https://{host}.finance.yahoo.com/v8/finance/chart/{t}?period1={p1}&period2={now}"
                   f"&interval={interval}&includePrePost=false&events=div%2Csplits")
            try:
                with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=30) as r:
                    j = json.load(r)
                res = j["chart"]["result"][0]
                q = res["indicators"]["quote"][0]
                out = []
                for i, ts in enumerate(res.get("timestamp") or []):
                    o, h, l, c, v = (q[k][i] for k in ("open", "high", "low", "close", "volume"))
                    if None in (o, h, l, c) or not (h >= l > 0):
                        continue
                    out.append((ts, o, h, l, c, v or 0))
                if out:
                    return out
            except Exception as e:  # noqa
                last = e
            time.sleep(2 + attempt * 3)
    raise SystemExit(f"{t} {interval}: {last}")


def wall_ms(ts):
    d = dt.datetime.fromtimestamp(ts, NY)
    return int(dt.datetime(d.year, d.month, d.day, d.hour, d.minute, tzinfo=dt.timezone.utc).timestamp() * 1000)


def daily(rows):
    out = {}
    for ts, o, h, l, c, v in rows:
        d = dt.datetime.fromtimestamp(ts, NY)
        k = int(dt.datetime(d.year, d.month, d.day, tzinfo=dt.timezone.utc).timestamp() * 1000)
        out[k] = (k, o, h, l, c, v)
    return [out[k] for k in sorted(out)]


def intraday(rows):
    out = {}
    for ts, o, h, l, c, v in rows:
        k = wall_ms(ts)
        mins = (k // 60000) % 1440
        if 570 <= mins < 960:  # 09:30-16:00 regular session only
            out[k] = (k, o, h, l, c, v)
    return [out[k] for k in sorted(out)]


def four_hour(h1):
    """TradingView-style session 4-hour candles: 09:30-13:30 and 13:30-16:00."""
    out = []
    for k, o, h, l, c, v in h1:
        day = k - k % 86400000
        mins = (k // 60000) % 1440
        start = day + (570 if mins < 810 else 810) * 60000
        if out and out[-1][0] == start:
            p = out[-1]
            out[-1] = (start, p[1], max(p[2], h), min(p[3], l), c, p[5] + v)
        else:
            out.append((start, o, h, l, c, v))
    return out


def pack(sym, iv, bars, st):
    t0 = bars[0][0]
    r = lambda x: round(x, 2) if x >= 10 else round(x, 4)
    b = []
    for k, o, h, l, c, v in bars:
        idx = (k - t0) / st
        if idx != int(idx):
            continue
        b.append([int(idx), r(o), r(h), r(l), r(c), int(v)])
    return {"s": sym, "iv": iv, "t0": t0, "st": st, "b": b}


def build(days_d, days_h, days_h1, days_30, h4_all=True):
    sets = []
    for t in TICKERS:
        sets.append(pack(t, "D", daily(fetch(t, "1d", days_d)), 86400000))
        time.sleep(1)
        h1 = intraday(fetch(t, "60m", days_h))
        sets.append(pack(t, "240", four_hour(h1), 4 * 3600000))
        cut = h1[-1][0] - days_h1 * 86400000 if h1 else 0
        if t in H1:
            sets.append(pack(t, "60", [x for x in h1 if x[0] >= cut], 3600000))
        if t in M30:
            sets.append(pack(t, "30", intraday(fetch(t, "30m", days_30)), 1800000))
        time.sleep(1)
    return sets


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "history"
    today = dt.date.today().isoformat()
    if mode == "history":
        sets = build(days_d=1190, days_h=725, days_h1=365, days_30=58)
        body = json.dumps({"built": today, "market": "stocks", "sets": sets}, separators=(",", ":"))
        with open("stocks-data.js", "w") as f:
            f.write(f"/* Real US stock candles (Yahoo Finance): {', '.join(TICKERS)}. Regular hours, New York time. Built {today} */\n")
            f.write("window.RW_STOCKS=" + body + ";\n")
        print("stocks-data.js", len(body), "bytes", [(s["s"], s["iv"], len(s["b"])) for s in sets])
    else:
        sets = build(days_d=420, days_h=40, days_h1=40, days_30=10)
        import os
        os.makedirs("live", exist_ok=True)
        with open("live/stocks-live.json", "w") as f:
            json.dump({"t": int(time.time() * 1000), "sets": sets}, f, separators=(",", ":"))
        print("live", [(s["s"], s["iv"], len(s["b"])) for s in sets])
