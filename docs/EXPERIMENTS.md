# Experiment plan

The purpose of experiments is to identify robust relationships across many stochastic paths, not to optimize a deceptive price path.

## Baseline

Run 100+ independent seeds with the default synthetic configuration. Record:
- graduation probability and time-to-graduation distribution;
- final return and maximum drawdown distributions;
- true volume, fees, LP fee accrual, and estimated adverse-execution exposure;
- holder concentration and Dev unlocked / locked inventory;
- participant-level realized and unrealized PnL;
- true-versus-observed candle and volume differences.

## Sensitivity dimensions

1. **Dev concentration:** vary Dev allocation and locked fraction independently. Keep total supply accounting valid. Compare Dev float share, top-holder concentration, buyer participation, drawdown, and graduation probability.
2. **Sniper population:** vary sniper count and activity rate. Measure early concentration, migration-period sell pressure, and post-migration volatility.
3. **KOL behavior:** vary audience credibility, posting rate, and attention decay. Compare attention spikes with sustained organic participation.
4. **Retail composition:** vary momentum sensitivity, social-proof sensitivity, loss aversion, and order-size dispersion.
5. **Whale concentration:** vary whale count, capital distribution, and market-impact sensitivity.
6. **Arbitrage capacity:** vary external fee and external executable depth. Measure basis persistence and local price dislocations.
7. **LP economics:** vary pool fee, LP fee share, initial LP lock fraction, and LP risk aversion. Measure depth, fee accrual, and inventory drawdown.
8. **Adverse execution:** vary abstract MEV-risk probability and maximum risk bps. Measure exposure by order size and depth; do not interpret this as a deployable attack model.
9. **Data quality:** vary feed latency, dropped-event rate, and duplicate-delivery rate. Compare observed candles with the true execution tape.

## Stress scenarios

Use stochastic shocks rather than fixed price scripts:
- external reference-price jumps with random sign and magnitude;
- bursts of correlated holder selling;
- sudden attention decay after a KOL post;
- liquidity withdrawal by a subset of LP providers;
- delayed or missing market-data observations;
- large but legitimate treasury/vesting supply events when explicitly configured.

## Reporting rules

- Use at least 100 seeds for exploratory distributions and 500+ for more stable tail estimates.
- Report mean, median, p10, p90, and graduation rate.
- Include the exact config, seed range, and calibration status.
- Separate causal model assumptions from observed data.
- Do not select only favorable runs or present one seed as the expected outcome.
