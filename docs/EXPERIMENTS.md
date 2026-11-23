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

14. **Break-even ledgers:** vary cash capital contributed, LP quote principal, non-cash genesis allocation basis, operating obligations and owner distributions. Report cash-capital recovery ratio, economic surplus and operating-solvency coverage separately; distinguish total LP quote withdrawn from pro-rata LP basis released, and test for double counting of LP principal and fee receivables.
15. **Creator-fee economics:** vary active Pump fee tier, beneficiary mode (creator / Holder Rewards / charity), independent eligible trade volume, multi-hop route and interface fee. Measure settled Creator Fee revenue, receivable aging, claim costs and fee-tier transitions. Exclude controlled-wallet turnover from external fee-revenue forecasts.
16. **Optimal partial liquidation:** vary risk-adjusted continuation value (M_{hold}), Dev LP share, route fee split, reference-price uncertainty and impact cap. Compare the analytical marginal rule with a numerical state-transition optimizer on matched seeds. Report q_BE versus q_max, actual net owner quote recovery, NLV change, CVaR and post-sale depth.

17. **Dev LP versus Treasury allocation:** compare no-LP, fixed LP share, fee-turnover/LVR screening, marginal LP allocation with zero volume elasticity, calibrated depth-to-genuine-volume elasticity, and joint Treasury reserve policies. Vary Dev/external LP share, active LP fee tier, volatility, turnover and capital reserve. Report LP claim NLV, Delta/Gamma, cash runway and tail loss. Compare the closed-form (K_D^*) under zero volume elasticity with the numerical optimizer; vary the alternative-capital hurdle and verify that the marginal value declines with Dev LP share when volume is fixed.
18. **Fee income attribution:** separate LP Fee retained in pool reserves from Creator Fee accrued/swept/claimed. Vary creator beneficiary mode, fee tier, fee claim delay and eligible external volume. Test that LP fees are not counted twice and that sweep events are not counted as new fee income.
19. **LP fee/LVR threshold:** sweep daily volatility from 10% to 50%, LP Fee from 0.020% to 0.250%, and genuine daily turnover from 0.25x to 200x TVL. Compare the analytical one-eighth variance baseline with event-driven replay including jumps, latency and concentrated flow.
20. **Depth elasticity:** estimate the causal response of genuine eligible volume to pool TVL using matched cohorts and held-out launches. Compare (epsilon_V=0) with calibrated elasticity; do not treat correlation between TVL and volume as causation.

21. **Fixed-intent depth replay:** replay an identical external order-intent tape across proportional depth variants (0.50x, 0.75x, 1.00x, 1.25x, 1.50x, 2.00x). Keep opening spot, supply, fee tier, external reference path, competing venue state and participant budgets fixed. Measure execution cost, route share, fill rate and successful genuine pool volume.
22. **Adaptive route-choice response:** add heterogeneous trader venue choice among the local pool, a finite-depth competing venue and no-trade. Vary route-cost sensitivity, order-size response and slippage-tolerance distributions. Compare against fixed-intent results on matched seeds. Calibrate the pure route selector's freshness, execution-cost, latency and failure penalties on held-out intent/route/fill observations; do not treat synthetic settings as measured behavior.
23. **Flow composition elasticity:** report organic, arbitrage and informed-flow volume elasticity separately. Test cases where local pool capacity, external venue depth or arbitrage capital is the binding constraint.
24. **Demand-versus-capture decomposition:** vary attention/KOL/regime shocks separately from pool depth. Confirm that changes in external intent arrivals are not misattributed to depth elasticity.

25. **External LP supply response:** vary (chi=dE/dK_D) across crowd-in, fixed-supply and crowd-out scenarios. Compare Dev's marginal fee capture, total pool depth, route share, external LP concentration and minimum-depth violations. Do not treat an increase in Dev fee share caused by other LPs withdrawing as a market-quality gain.

26. **Two-sided depth and inventory:** compare buy/sell depth at 1%, 5% and 10% impact; vary directional order flow and reference basis. Report depth balance, asymmetry, beneficial-owner Token exposure and continuous minimum-depth breaches.
27. **Independent price discovery:** construct a robust reference from multiple executable venues; vary stale sources, venue concentration, fees and finite depth. Measure signed/p95 basis, no-arbitrage band violations and convergence after independent reference changes.
28. **Resilience:** replay observed and stochastic exogenous shocks. Measure basis recovery, buy-depth recovery and sell-depth recovery separately; include censored non-recovery and sustained-window requirements. Do not require reversion to the pre-shock price.
29. **Adverse selection and markout:** compute trade-side signed reference markout at multiple horizons. Compare LP-retained fees, adverse markout, LVR baseline and realized LP NLV without double-counting IL/LVR.
30. **Execution fairness:** match orders by side, quote size, pool state, fee tier, congestion, priority fee and quote freshness. Compare residual p50/p95, success rates and latency across cohorts.
31. **Market integrity:** test unique event identity, reorg/finality handling, duplicate suppression, true OHLCV reconciliation, LP-event exclusion and conservative beneficial-owner attribution. Verify unknown volume is not silently labeled independent.
32. **Lifecycle state machine:** test every state transition, hysteresis, persistence window, PAUSE/RECOVERY behavior and protocol-migration reconciliation.
33. **MQS hard-gate behavior:** verify that a failed integrity, data, depth or risk gate cannot be compensated by a high score in another dimension. Confirm raw volume, low volatility and candle smoothness do not increase the score directly.
34. **Participant heterogeneity:** vary correlated information shocks, heavy-tailed order sizes, finite inventory, route sensitivity, external LP response and beneficial-owner clusters. Report distributions and false-positive rates for anomaly flags.

## Stress scenarios

Use stochastic shocks rather than fixed price scripts. Preserve protocol reserve relationships when changing curve parameters; do not tune graduation by changing a quote threshold because Pump completion is based on real-token exhaustion:
- external reference-price jumps with random sign and magnitude;
- bursts of correlated holder selling;
- sudden attention decay after a KOL post;
- liquidity withdrawal by a subset of LP providers;
- delayed or missing market-data observations;
- large but legitimate treasury/vesting supply events when explicitly configured.

## Reporting rules

- Report LP-versus-Treasury marginal allocation value, fee/LVR surplus, volume elasticity and Delta/Gamma exposure.
- Report LP Fee accrual through reserve value separately from Creator Fee accrued, swept, claimed and distributed.
- Report intent, route selection, submission, settlement and failure separately; include route share and fill elasticity by participant class and flow type.
- Report the complete R08–R19 market-quality vector, hard-gate status, confidence and missing-data flags; do not report only one MQS scalar.

- Use at least 100 seeds for exploratory distributions and 500+ for more stable tail estimates.
- Report mean, median, p10, p90, and graduation rate.
- Include the exact config, seed range, and calibration status.
- Separate causal model assumptions from observed data.
- Do not select only favorable runs or present one seed as the expected outcome.
