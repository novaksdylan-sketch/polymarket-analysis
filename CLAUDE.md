# Polymarket Analysis — Project Context

## What This Project Is

A backtesting study to answer one question: **does copying the top traders on Polymarket actually work as a strategy?**

Polymarket is a prediction market platform where traders bet on real-world events (elections, sports, crypto prices, etc.). The platform publishes a public leaderboard of top-performing traders. This project pulls that historical data and simulates what would have happened if someone had blindly copied those top traders' positions.

**This is pure data analysis — no live trading, no real money, no broker integration.** The output is a research report, not a trading bot.

## Who Is Working on This

Dylan Novaks — first coding project, learning Python from scratch. Claude Code is the co-pilot. The approach is: Claude writes code, Dylan reads it, asks questions, and builds understanding over time.

Dylan has zero prior coding experience and is using this project to learn Python; explanations should err toward more rather than less, and the python-learning-coach skill should be invoked when introducing new concepts.

## Repository

GitHub: https://github.com/novaksdylan-sketch/polymarket-analysis

## Tech Stack (Planned)

- **Language:** Python
- **Data source:** Polymarket public API via the `polymarket-apis` package (no authentication required for read-only endpoints)
- **Data storage:** Local files (CSV or JSON) during development; no database required initially
- **Analysis:** pandas for data manipulation, matplotlib or plotly for charts

---

## Project Phases

### Phase 1 — Data Collection

Pull and persist the raw data needed for analysis:

- Fetch the Polymarket leaderboard (top traders by PnL or volume)
- For each top trader, pull their full trade history via the public API
- Save everything locally so we don't need to re-fetch constantly
- Explore the data structure: what fields exist, what time ranges are available, what markets do top traders participate in

Deliverable: a local dataset of top-trader trade histories, ready for analysis.

### Phase 2 — Backtest Engine

Simulate the "copy trading" strategy on historical data:

- Define the strategy: when trader X opens a position, we open the same position with a configurable lag (to simulate realistic detection delay)
- Account for slippage: our simulated entry price should be worse than the trader's observed entry price
- Implement position sizing: decide how much of a notional portfolio to allocate per copied trade
- Compute PnL, win rate, Sharpe ratio, and max drawdown for the simulated portfolio
- Compare against a naive baseline (e.g., random trader, or equal weighting across all markets)

Critical constraints: must avoid look-ahead bias and survivorship bias (see Methodology Warnings below).

### Phase 3 — Deeper Analysis

Answer more nuanced questions once the core backtest works:

- Which traders have the most durable edge? (Does their win rate hold across out-of-sample periods?)
- Are certain traders specialists in specific market categories (politics vs. sports vs. crypto)?
- Does copying a trader's edge decay over time — i.e., does their strategy stop working after you start following them?
- How sensitive is the strategy's profitability to lag and slippage assumptions?
- Is the leaderboard itself a useful signal, or is it noise dominated by a few lucky large positions?

---

## Methodology Warnings

These are the backtesting pitfalls we must actively guard against. Violating any of these would make the results meaningless.

### 1. Look-Ahead Bias
**What it is:** Using information in the simulation that would not have been available at the moment the decision was made.

**How it can sneak in here:**
- Using a trader's *final* resolved PnL to decide whether to copy them, when at copy time you only knew their *running* PnL
- Selecting which traders to copy based on their full historical record, including trades made *after* the copy start date
- Using market resolution prices in entry-price calculations

**How to avoid it:** At every point in the simulation timeline `t`, only use data with timestamps strictly less than `t`. The leaderboard snapshot used to select traders must come from before the first copy trade.

### 2. Survivorship Bias
**What it is:** Only analyzing traders who appear on the leaderboard *today*, ignoring traders who were once at the top but later blew up or left.

**How it can sneak in here:**
- If the API only exposes current top traders, we miss everyone who ranked highly in the past but no longer does
- This makes the strategy look better than it really is, because we're implicitly selecting winners in hindsight

**How to avoid it:** Ideally, collect leaderboard snapshots at multiple points in time. At minimum, document clearly that our dataset is survivorship-biased and adjust conclusions accordingly (treat results as an upper bound on real performance).

### 3. Slippage Assumptions
**What it is:** In real markets, you cannot trade at exactly the price the person you're copying traded at. By the time you see their trade and act, the price has moved.

**How it can sneak in here:**
- Assuming zero slippage makes the strategy look more profitable than it would be in practice
- Prediction market spreads can be wide, especially for low-liquidity events

**How to avoid it:** Apply a conservative slippage model — e.g., assume our entry is X% worse than the observed trade price. Run sensitivity analysis across different slippage values (0%, 0.5%, 1%, 2%) to see how robust results are.

### 4. Detection Lag
**What it is:** Polymarket trade data is public, but there is a delay between when a trader executes a trade and when we would realistically observe it and act on it.

**How it can sneak in here:**
- Treating "trade observed at time T" as "we could have copied at time T" ignores the polling interval and reaction time
- In fast-moving markets (e.g., election night), a 5-minute lag could mean a completely different price

**How to avoid it:** Parameterize the lag explicitly in the backtest. Default to a conservative assumption (e.g., 15–30 minutes). Report how results change as lag increases.

### 5. Overfitting / Data Dredging
**What it is:** Running many variations of the strategy until one looks good, then reporting only that one.

**How to avoid it:** Define the strategy parameters (which traders to copy, lag, slippage, position sizing) *before* looking at PnL results. Reserve the most recent portion of the dataset as a holdout period that we only evaluate once at the very end.
