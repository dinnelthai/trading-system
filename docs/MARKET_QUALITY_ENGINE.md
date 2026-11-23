# Market Quality Metrics Engine

**Status:** Implemented on `feat/pumpswap-state-adapter` as pure research metrics with unit tests. Historical adapters, calibrated thresholds and live monitoring are not implemented.

## Implemented primitives

### Independent reference price

`build_independent_reference`:
- accepts bid/ask and executable depth from each independent venue;
- uses only the latest quote per venue;
- rejects future, stale, non-executable and overly wide quotes;
- weights by two-sided executable depth and freshness;
- supports a per-venue weight cap;
- returns an explicit invalid result when fewer than the required number of venues remain.

The output includes included venue IDs and exclusion counts. It does not infer whether two venues are truly independent; that is an upstream configuration and provenance responsibility.

### Two-sided depth

`depth_balance` returns:

[
B=rac{2min(D_b,D_s)}{D_b+D_s}
]

and log asymmetry:

[
A=lnrac{D_b+epsilon}{D_s+epsilon}
]

These are diagnostics. The engine does not force a market to have symmetric depth.

### Basis and trade markout

`log_basis` computes (ln(P_{pool}/P^*)).

`trade_markout` computes the LP-side signed markout at a selected horizon. Positive values are adverse to the LP. LP-retained fees and attributable execution costs are kept separate; protocol/creator fees must not be passed as LP-retained fees.

### Recovery time

`measure_recovery_time` requires:
- a valid independent reference;
- basis within tolerance;
- both buy and sell depth above their thresholds;
- a continuous observation window with no excessive sampling gaps.

If recovery is not observed within the available horizon, the result is marked right-censored. Recovery does not mean returning to the pre-shock price; it means meeting the post-shock reference and depth conditions.

### Hard gates and diagnostic MQS

`evaluate_market_quality` applies non-compensable gates for:
- buy depth;
- sell depth;
- P95 execution cost;
- P95 absolute reference basis;
- P95 recovery time;
- data completeness;
- integrity violations.

Status is:
- `PAUSED` when integrity or data-completeness gates fail;
- `DEGRADED` when other market-quality gates fail;
- `PASS` when all gates pass.

Only a PASS result may display a diagnostic geometric MQS. The seven normalized dimensions are L/E/P/R/F/I/S. Raw volume, price appreciation, low volatility and candle smoothness are not inputs to the score.

## Important limitations

- The reference builder consumes venue quotes; it does not fetch them.
- Venue independence and quote authenticity must be established upstream.
- Thresholds must be calibrated per lifecycle phase and order-size cohort.
- P95 aggregation over historical observations is a caller responsibility.
- Fairness cohort matching and liquidity sustainability inputs still need their own calibrated data adapters.
- No strategy action, wallet connection or live transaction execution is implemented by this module.
