import csv
import os

from polymarket_apis import PolymarketDataClient

LEADERBOARD_SIZE = 50
OUTPUT_PATH = os.path.join("data", "leaderboard.csv")

client = PolymarketDataClient()

print(f"Fetching top {LEADERBOARD_SIZE} traders by all-time profit...")
traders = client.get_leaderboard_top_users(
    metric="profit",
    window="all",
    limit=LEADERBOARD_SIZE,
)

os.makedirs("data", exist_ok=True)

with open(OUTPUT_PATH, "w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=["rank", "proxy_wallet", "name", "pseudonym", "profit_usd"])
    writer.writeheader()
    for rank, trader in enumerate(traders, start=1):
        writer.writerow({
            "rank":         rank,
            "proxy_wallet": trader.proxy_wallet,
            "name":         trader.name,
            "pseudonym":    trader.pseudonym,
            "profit_usd":   trader.amount,
        })

print(f"Saved {len(traders)} traders to {OUTPUT_PATH}")
