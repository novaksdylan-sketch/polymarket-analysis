import csv
import os
import time

import httpx
from polymarket_apis import PolymarketDataClient

LEADERBOARD_PATH = os.path.join("data", "leaderboard.csv")
OUTPUT_PATH = os.path.join("data", "trades.csv")
PAGE_SIZE = 500
DELAY_SECONDS = 0.5

FIELDS = [
    "proxy_wallet", "pseudonym", "name",
    "timestamp", "side", "title", "outcome",
    "price", "size", "condition_id", "token_id",
]


def fetch_all_trades(client, proxy_wallet):
    trades = []
    offset = 0
    while True:
        try:
            page = client.get_trades(
                user=proxy_wallet,
                limit=PAGE_SIZE,
                offset=offset,
                taker_only=False,
            )
        except httpx.HTTPStatusError:
            break
        trades.extend(page)
        if len(page) < PAGE_SIZE:
            break
        offset += PAGE_SIZE
    return trades


def load_leaderboard():
    with open(LEADERBOARD_PATH, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


client = PolymarketDataClient()
traders = load_leaderboard()

os.makedirs("data", exist_ok=True)

with open(OUTPUT_PATH, "w", newline="", encoding="utf-8") as out:
    writer = csv.DictWriter(out, fieldnames=FIELDS)
    writer.writeheader()

    for trader in traders:
        rank = trader["rank"]
        name = trader["name"] or trader["pseudonym"]
        wallet = trader["proxy_wallet"]

        print(f"[{rank}/50] {name} ...", end=" ", flush=True)
        trades = fetch_all_trades(client, wallet)
        print(f"{len(trades)} trades")

        for t in trades:
            writer.writerow({
                "proxy_wallet": t.proxy_wallet,
                "pseudonym":    t.pseudonym,
                "name":         t.name,
                "timestamp":    t.timestamp.isoformat(),
                "side":         t.side,
                "title":        t.title,
                "outcome":      t.outcome,
                "price":        t.price,
                "size":         t.size,
                "condition_id": t.condition_id,
                "token_id":     t.token_id,
            })

        time.sleep(DELAY_SECONDS)

print(f"\nDone. Saved all trades to {OUTPUT_PATH}")
