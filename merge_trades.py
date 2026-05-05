"""
Build a hybrid trades.csv:
  - 'complete' data for traders that had no API caps in the activity fetch
  - 'filtered_$X' data (cash-filtered) for traders that hit caps
A data_quality column flags which is which on every row.
"""

import csv
import os
import re
import time
from datetime import datetime, timedelta, timezone

import httpx

ACTIVITY_LOG = (
    r"C:/Users/Dylan/AppData/Local/Temp/claude/"
    r"C--Users-Dylan-Projects-polymarket-analysis/"
    r"5aa3e950-f339-40f1-bcbd-13496389ba78/tasks/bdqsr1nkd.output"
)
LEADERBOARD_PATH = os.path.join("data", "leaderboard.csv")
CASH_TRADES_PATH = os.path.join("data", "trades.csv")             # cash-filtered source
THRESHOLDS_PATH  = os.path.join("data", "trade_thresholds.csv")
OUTPUT_TRADES    = os.path.join("data", "trades.csv")             # final output
TEMP_OUTPUT      = os.path.join("data", "trades.csv.tmp")         # write here first, swap on success
QUALITY_PATH     = os.path.join("data", "data_quality.csv")
BASE_URL         = "https://data-api.polymarket.com"
PAGE_SIZE        = 500
WINDOW_DAYS      = 7
DELAY_SECONDS    = 0.3
START_DATE = datetime(2024, 10, 1, tzinfo=timezone.utc)
END_DATE   = datetime(2026, 6,  1, tzinfo=timezone.utc)

FIELDS = [
    "proxy_wallet", "pseudonym", "name",
    "timestamp", "side", "title", "outcome",
    "price", "size", "usdc_size", "condition_id", "token_id",
    "data_quality",
]


def find_clean_wallets():
    """A trader is 'clean' if they appear in the activity log with no CRITICAL DATA GAP line."""
    with open(ACTIVITY_LOG, encoding="utf-8", errors="replace") as f:
        log = f.read()
    chunks = re.split(r"(\[\d+/50\][^\n]+)", log)
    clean_ranks = []
    for i in range(1, len(chunks), 2):
        header = chunks[i]
        body   = chunks[i + 1] if i + 1 < len(chunks) else ""
        rank   = int(re.match(r"\[(\d+)/50\]", header).group(1))
        if "CRITICAL DATA GAP" not in body:
            clean_ranks.append(rank)
    return set(clean_ranks)


def week_windows(start, end):
    cursor = start
    while cursor < end:
        yield cursor, min(cursor + timedelta(days=WINDOW_DAYS), end)
        cursor += timedelta(days=WINDOW_DAYS)


def get_with_retry(client, url, params, max_attempts=4):
    for attempt in range(max_attempts):
        try:
            r = client.get(url, params=params)
            r.raise_for_status()
            return r.json()
        except (httpx.ReadTimeout, httpx.ConnectTimeout, httpx.RemoteProtocolError) as e:
            if attempt == max_attempts - 1:
                raise
            wait = 2 ** attempt
            print(f"\n  (timeout on attempt {attempt + 1}, retrying in {wait}s...)", flush=True)
            time.sleep(wait)


def fetch_full_activity(client, proxy_wallet):
    rows = []
    for window_start, window_end in week_windows(START_DATE, END_DATE):
        offset = 0
        while True:
            params = {
                "user":          proxy_wallet,
                "limit":         PAGE_SIZE,
                "offset":        offset,
                "start":         int(window_start.timestamp()),
                "end":           int(window_end.timestamp()),
                "sortBy":        "TIMESTAMP",
                "sortDirection": "ASC",
            }
            page = get_with_retry(client, f"{BASE_URL}/activity", params)
            rows.extend(page)
            if len(page) < PAGE_SIZE:
                break
            offset += PAGE_SIZE
    return [r for r in rows if r.get("type") == "TRADE"]


def main():
    clean_ranks = find_clean_wallets()
    print(f"Found {len(clean_ranks)} clean traders to re-fetch in full.\n")

    # Load leaderboard for rank → wallet → name mapping
    with open(LEADERBOARD_PATH, encoding="utf-8") as f:
        leaderboard = list(csv.DictReader(f))

    # Load thresholds for cash-filtered traders
    with open(THRESHOLDS_PATH, encoding="utf-8") as f:
        thresholds = {r["proxy_wallet"]: r for r in csv.DictReader(f)}

    # Load existing cash-filtered trades.csv into memory (for the non-clean traders)
    with open(CASH_TRADES_PATH, encoding="utf-8") as f:
        cash_rows = list(csv.DictReader(f))

    quality_records = []
    client = httpx.Client(http2=True, timeout=30.0)

    # Write to temp file first; only swap into place if we finish successfully.
    # Prevents corrupting the source cash-filtered trades.csv if this run fails mid-way.
    with open(TEMP_OUTPUT, "w", newline="", encoding="utf-8") as out:
        writer = csv.DictWriter(out, fieldnames=FIELDS)
        writer.writeheader()

        for trader in leaderboard:
            rank   = int(trader["rank"])
            wallet = trader["proxy_wallet"]
            name   = trader["name"] or trader["pseudonym"]

            if rank in clean_ranks:
                print(f"[{rank}/50] {name} -> fetching full activity...", end=" ", flush=True)
                trades = fetch_full_activity(client, wallet)
                print(f"{len(trades)} trades (complete)")

                for r in trades:
                    writer.writerow({
                        "proxy_wallet": r.get("proxyWallet", ""),
                        "pseudonym":    r.get("pseudonym", ""),
                        "name":         r.get("name", ""),
                        "timestamp":    r.get("timestamp", ""),
                        "side":         r.get("side", ""),
                        "title":        r.get("title", ""),
                        "outcome":      r.get("outcome", ""),
                        "price":        r.get("price", ""),
                        "size":         r.get("size", ""),
                        "usdc_size":    r.get("usdcSize", ""),
                        "condition_id": r.get("conditionId", ""),
                        "token_id":     r.get("asset", ""),
                        "data_quality": "complete",
                    })

                quality_records.append({
                    "rank": rank, "name": name, "proxy_wallet": wallet,
                    "data_quality": "complete",
                    "threshold_usdc": 0,
                    "trades_captured": len(trades),
                    "fit_for_backtest": "YES — full history",
                })
                time.sleep(DELAY_SECONDS)

            else:
                # Use existing cash-filtered rows
                wallet_rows = [r for r in cash_rows if r["proxy_wallet"] == wallet]
                threshold = int(thresholds[wallet]["threshold_usdc"]) if wallet in thresholds else 1000
                quality_label = f"filtered_${threshold}"
                print(f"[{rank}/50] {name} -> keeping cash-filtered ({len(wallet_rows)} trades, ${threshold:,}+)")

                for r in wallet_rows:
                    r_out = {k: r.get(k, "") for k in FIELDS if k != "data_quality"}
                    r_out["data_quality"] = quality_label
                    writer.writerow(r_out)

                fit = "PARTIAL — small trades missing" if threshold <= 1000 else \
                      "LIMITED — only large trades captured" if threshold <= 10000 else \
                      "POOR — only whale-size trades captured"
                quality_records.append({
                    "rank": rank, "name": name, "proxy_wallet": wallet,
                    "data_quality": quality_label,
                    "threshold_usdc": threshold,
                    "trades_captured": len(wallet_rows),
                    "fit_for_backtest": fit,
                })

    client.close()

    # Atomically swap temp file into place
    os.replace(TEMP_OUTPUT, OUTPUT_TRADES)

    # Write data quality manifest
    with open(QUALITY_PATH, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=[
            "rank", "name", "proxy_wallet", "data_quality",
            "threshold_usdc", "trades_captured", "fit_for_backtest",
        ])
        w.writeheader()
        w.writerows(quality_records)

    # Print summary
    print(f"\n{'=' * 75}")
    print(f"DATA QUALITY SUMMARY")
    print(f"{'=' * 75}")
    by_quality = {}
    for q in quality_records:
        by_quality.setdefault(q["data_quality"], []).append(q)

    for label in sorted(by_quality):
        print(f"\n  {label}: {len(by_quality[label])} traders")
        for q in by_quality[label]:
            print(f"    #{q['rank']:>2} {q['name'][:30]:<30} {q['trades_captured']:>7,} trades")

    print(f"\n  Manifest written to: {QUALITY_PATH}\n")


if __name__ == "__main__":
    main()
