#!/usr/bin/env python3
import argparse
import json
import time

import yfinance as yf


def fetch_quotes(symbols, period="5d", interval="1d", retries=3, pause=1.5):
    rows = []
    errors = []
    for symbol in symbols:
        last_error = None
        for attempt in range(retries):
            try:
                ticker = yf.Ticker(symbol)
                hist = ticker.history(period=period, interval=interval, auto_adjust=False, actions=False)
                if hist is None or hist.empty:
                    raise RuntimeError("empty history")
                last = hist.iloc[-1]
                prev = None
                if len(hist) >= 2:
                    prev = hist.iloc[-2]["Close"]
                elif "Close" in last and "Open" in last:
                    prev = last["Open"]
                close = float(last["Close"])
                pct = None if prev in (None, 0) else (close - float(prev)) / float(prev) * 100
                volume = None if "Volume" not in last or last["Volume"] is None else int(last["Volume"])
                name = symbol
                try:
                    info = ticker.info or {}
                    name = info.get("shortName") or info.get("longName") or symbol
                except Exception:
                    pass
                rows.append(
                    {
                        "symbol": symbol,
                        "name": name,
                        "regular_market_price": f"{close:.2f}",
                        "change_pct": f"{pct:+.2f}" if pct is not None else None,
                        "volume": str(volume) if volume is not None else None,
                        "timestamp": hist.index[-1].isoformat(),
                    }
                )
                last_error = None
                break
            except Exception as exc:
                last_error = str(exc)
                if attempt < retries - 1:
                    time.sleep(pause * (attempt + 1))
        if last_error:
            errors.append({"symbol": symbol, "error": last_error})
    status = "ok" if rows else "error"
    error_message = None if not errors else "; ".join(f"{e['symbol']}: {e['error']}" for e in errors)
    return {"status": status, "error_message": error_message, "data": rows}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--symbols", nargs="+", required=True)
    parser.add_argument("--period", default="5d")
    parser.add_argument("--interval", default="1d")
    args = parser.parse_args()
    print(json.dumps(fetch_quotes(args.symbols, period=args.period, interval=args.interval), ensure_ascii=False))


if __name__ == "__main__":
    main()
