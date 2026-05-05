import csv
import os
import time

import httpx

LEADERBOARD_PATH = os.path.join("data", "leaderboard.csv")
OUTPUT_PATH      = os.path.join("data", "trades.csv")
THRESHOLDS_PATH  = os.path.join("data", "trade_thresholds.csv")
BASE_URL         = "https://data-api.polymarket.com"
PAGE_SIZE        = 500
MAX_OFFSET       = 3000   # API caps around 3500; stop one page early to be safe
DELAY_SECONDS    = 0.3
ESCALATION       = [1000, 5000, 10000, 25000, 50000]

FIELDS = [
    "proxy_wallet", "pseudonym", "name",
    "timestamp", "side", "title", "outcome",
    "price", "size", "usdc_size", "condition_id", "token_id",
]


def fetch_trades_at_threshold(client, proxy_wallet, threshold):
    rows = []
    offset = 0
    capped = False
    while True:
        params = {
            "user":         proxy_wallet,
            "limit":        PAGE_SIZE,
            "offset":       offset,
            "takerOnly":    False,
            "filterType":   "CASH",
            "filterAmount": threshold,
        }
        response = client.get(f"{BASE_URL}/trades", params=params)
        response.raise_for_status()
        page = response.json()
        rows.extend(page)

        if len(page) < PAGE_SIZE:
            break
        offset += PAGE_SIZE
        if offset >= MAX_OFFSET:
            capped = True
            break
    return rows, capped


def fetch_with_adaptive_threshold(client, proxy_wallet, name):
    for threshold in ESCALATION:
        rows, capped = fetch_trades_at_threshold(client, proxy_wallet, threshold)
        if not capped:
            return rows, threshold
        print(f"  -> ${threshold:,} threshold hit cap ({len(rows)} trades), escalating...")

    # Last threshold also capped — accept what we got and warn loudly
    print(
        f"\n  !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!\n"
        f"  !! UNRESOLVABLE: {name} ({proxy_wallet})\n"
        f"  !! Hit cap even at ${ESCALATION[-1]:,} threshold\n"
        f"  !! Data is INCOMPLETE — exclude this trader from backtest\n"
        f"  !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!\n"
    )
    return rows, ESCALATION[-1]


def load_leaderboard():
    with open(LEADERBOARD_PATH, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


client = httpx.Client(http2=True, timeout=30.0)
traders = load_leaderboard()

os.makedirs("data", exist_ok=True)

threshold_log = []

with open(OUTPUT_PATH, "w", newline="", encoding="utf-8") as out:
    writer = csv.DictWriter(out, fieldnames=FIELDS)
    writer.writeheader()

    for trader in traders:
        rank   = trader["rank"]
        name   = trader["name"] or trader["pseudonym"]
        wallet = trader["proxy_wallet"]

        print(f"[{rank}/50] {name}")
        rows, threshold_used = fetch_with_adaptive_threshold(client, wallet, name)
        print(f"  -> {len(rows)} trades at ${threshold_used:,}+ threshold")

        threshold_log.append({
            "rank":            rank,
            "name":            name,
            "proxy_wallet":    wallet,
            "threshold_usdc":  threshold_used,
            "trades_captured": len(rows),
        })

        for r in rows:
            usdc = r.get("size", 0) * r.get("price", 0)
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
                "usdc_size":    round(usdc, 2),
                "condition_id": r.get("conditionId", ""),
                "token_id":     r.get("asset", ""),
            })

        time.sleep(DELAY_SECONDS)

with open(THRESHOLDS_PATH, "w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=["rank", "name", "proxy_wallet", "threshold_usdc", "trades_captured"])
    w.writeheader()
    w.writerows(threshold_log)

client.close()
print(f"\nDone.")
print(f"  Trades:     {OUTPUT_PATH}")
print(f"  Thresholds: {THRESHOLDS_PATH}")
