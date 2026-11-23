# Experiment plan

The purpose of experiments is to identify robust relationships across many stochastic paths, not to optimize a deceptive price path.

## Baseline

Run 100+ independent seeds with the default synthetic configuration. Record:
- graduation probability and time-to-graduation distribution under real-token-exhaustion completion;
- gross buys, gross sells, net quote flow, remaining real token inventory, and real quote reserve on the bonding curve;
- migration price gap and initial PumpSwap reserves;
- final return and maximum drawdown distributions;
- true volume, fees, LP fee accrual, and estimated adverse-execution exposure;
- top-1 / top-5 holder share, wallet HHI, and Dev unlocked / locked inventory;
- participant-level realized and unrealized PnL;
- true-versus-observed candle and volume differences.

## Sensitivity dimensions

1. **Launch capital:** vary initial capital scale and role-specific wealth dispersion. Compare graduation probability, time-to-graduation, holder concentration, drawdown, and net curve quote flow.
2. **Dev concentration:** vary Dev allocation and locked fraction independently. Keep total supply accounting valid. Compare Dev float share, top-holder concentration, buyer participation, drawdown, and graduation probability.
3. **Sniper population:** vary sniper count and activity rate. Measure early concentration, migration-period sell pressure, and post-migration volatility.
4. **KOL behavior:** vary audience credibility, posting rate, and attention decay. Compare attention spikes with sustained organic participation.
5. **Retail composition:** vary momentum sensitivity, social-proof sensitivity, loss aversion, and order-size dispersion.
6. **Whale concentration:** vary whale count, capital distribution, and market-impact sensitivity.
7. **Arbitrage capacity:** vary external fee and external executable depth. Measure basis persistence and local price dislocations.
8. **LP economics:** vary pool fee, LP fee share, initial LP lock fraction, and LP risk aversion. Measure depth, fee accrual, and inventory drawdown.
9. **Adverse execution:** vary abstract MEV-risk probability and maximum risk bps. Measure exposure by order size and depth; do not interpret this as a deployable attack model.
10. **Data quality:** vary feed latency, dropped-event rate, and duplicate-delivery rate. Compare observed candles with the true execution tape.
11. **Dev treasury exit:** compare no-sale, fixed vesting-sale, fixed tranche, risk-threshold, adaptive optimal-stopping and route-aware policies on matched seeds. Vary Dev LP ownership, unlocked overhang, independent executable depth, volatility, OTC capacity, future unlocks and treasury reserve requirements. Measure net realized proceeds, terminal liquidation value, beneficial exposure reduction, market impact, post-sale depth, treasury runway and tail outcomes.

12. **LP exit sequencing:** compare sell-before-remove, partial-remove-before-sell, remove-only and independent OTC routes at identical starting states. Vary Dev LP share, removal fraction, sell size, fee split and external LP share. Measure owner-level Token/SOL exposure, seller net proceeds, marginal price impact, remaining two-sided depth, external LP loss and post-action concentration. Reject policies that improve Dev proceeds only by breaching market-quality constraints or shifting excessive losses to remaining LPs.
13. **Fee accounting:** test buy and sell reserve deltas separately under multiple LP/protocol splits; include versioned Pump creator/protocol/LP fee tiers and verify that LP-retained fees are counted once.

14. **Break-even ledgers:** vary cash capital contributed, LP quote principal, non-cash genesis allocation basis, operating obligations and owner distributions. Report cash-capital recovery ratio, economic surplus and operating-solvency coverage separately; test for double counting of LP principal and fee receivables.
15. **Creator-fee economics:** vary active Pump fee tier, beneficiary mode (creator / Holder Rewards / charity), independent eligible trade volume, multi-hop route and interface fee. Measure settled Creator Fee revenue, receivable aging, claim costs and fee-tier transitions. Exclude controlled-wallet turnover from external fee-revenue forecasts.
16. **Optimal partial liquidation:** vary risk-adjusted continuation value (M_{hold}), Dev LP share, route fee split, reference-price uncertainty and impact cap. Compare the analytical marginal rule with a numerical state-transition optimizer on matched seeds. Report q_BE versus q_max, actual net owner quote recovery, NLV change, CVaR and post-sale depth.

## Stress scenarios

Use stochastic shocks rather than fixed price scripts. Preserve protocol reserve relationships when changing curve parameters; do not tune graduation by changing a quote threshold because Pump completion is based on real-token exhaustion:
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
