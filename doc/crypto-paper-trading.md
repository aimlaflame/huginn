# Coinbase spot monitoring and paper trading

This workflow uses Coinbase's **public** ticker API for one spot product (default `BTC-USD`) and Huginn to produce
threshold alerts and simulated trades. It does not need exchange credentials and **cannot place live orders**.
It does not find or copy another trader's wallet, positions, or leverage.

## Create the workflow

1. Deploy Huginn on a trusted host and keep the web process, scheduler, and background workers running. Use HTTPS and
   Huginn's normal user authentication; the Huginn web interface can be opened from a phone, tablet, or computer.
2. Create a **Coinbase Market Agent**. Keep `product_id` at `BTC-USD` to start, set a `signal_threshold_percent`
   (default `1.0`), and keep the `every_1m` schedule. The threshold is the percentage move from the previous
   successful poll: upward moves emit `buy`, downward moves emit `sell`, and smaller moves emit `hold`.
3. Create a **Crypto Paper Trading Agent** with matching `product_id`. Its defaults simulate a $1,000 balance,
   $25 orders, and a $100 maximum position. Adjust `daily_loss_limit_usd` to control when new simulated buys stop.
   Connect the Coinbase Market Agent to it.
4. Optionally connect the market or paper-trading agent to a notification agent such as Email, Telegram, or
   Pushover to receive signals and simulated trade outcomes. Check the market agent's Huginn logs for failed requests.
5. Review the paper-trading events and Huginn logs regularly. Check that the market monitor is working and that
   the simulated balance, position, and daily realized loss match the emitted events.

## Safety and limitations

- Start with public market monitoring and simulation only. The paper agent never calls Coinbase or Kraken order APIs.
- The percentage-change signal is a simple configurable example, not a proven strategy or financial advice. It
  compares adjacent poll prices and can miss price movement between polls.
- The simulation omits fees, spread, slippage, partial fills, and exchange outages; reported results may therefore
  be more favorable than real trading.
- `order_size_usd`, `max_position_usd`, `starting_balance_usd`, and `daily_loss_limit_usd` are USD simulation
  limits. A reached daily loss limit blocks new buys for the rest of the day; sell signals can still close a position.
  Setting `paused` to `true` blocks new buys but still permits exits.
- No live-trading feature is included. Before any future live-order work, it would require a separate exchange API
  key with trading permission only and withdrawals disabled, explicit per-order and daily loss caps, price/slippage
  checks, duplicate-order protection, and an emergency stop. Paper-trading success does not guarantee live results.
