# Pump Lifecycle Market Simulator

An agent-based, stochastic research simulator for studying token launch and market lifecycle dynamics across a bonding-curve phase and a post-graduation constant-product pool.

> Research simulator only. It does not connect to wallets, submit transactions, or provide a strategy for manipulating live markets. Manipulative conduct (wash trading, fabricated volume, deceptive coordination, artificial dumps, and sandwich execution playbooks) is not implemented. Adversarial behavior is represented as measurable risk and stress scenarios.

## Goals

- Model a complete lifecycle: launch, bonding-curve trading, graduation, pool trading, liquidity changes, and terminal outcomes.
- Give every participant an independent objective, balance sheet, information set, risk profile, decision cadence, and stochastic policy.
- Preserve heterogeneity and disorder: independent random streams, random arrival times, asynchronous decisions, noisy private signals, variable trade sizes, correlated shocks, and probabilistic regime changes.
- Separate latent market state from observed candles so sparse trading, latency, event ordering, and data-quality faults can be studied without fabricating trades.
- Run reproducible seeded experiments and multi-seed Monte Carlo batches.
- Report price impact, depth, concentration, inventory risk, fee income, drawdown, realized/unrealized PnL, graduation probability, survival, and participant-level outcomes.

## Participant types

1. **Dev / treasury** — disclosed inventory, vesting, treasury budget, liquidity commitments, and operational constraints. No covert price-support or dump-and-rebuy policy.
2. **Early snipers** — fast, short-horizon entrants with heterogeneous launch-signal sensitivity and exit horizons.
3. **KOLs** — stochastic publishing decisions, audience fit, credibility, disclosure status, and delayed attention effects.
4. **Arbitrageurs** — compare independent venues/reference prices and trade only when expected spread exceeds fees, impact, and risk.
5. **Retail traders** — heterogeneous momentum, social-proof, FOMO, loss-aversion, attention, and limited-information behavior.
6. **Whales** — larger inventories, stronger market-impact awareness, and portfolio/risk constraints.
7. **LP providers** — fee-versus-inventory-risk decisions, liquidity budgets, and withdrawal constraints.
8. **MEV / sandwich-risk actor** — abstract adverse-execution stress model that estimates victim slippage/extraction exposure; it does not implement a live sandwich bot or transaction-ordering instructions.

## Market lifecycle

- **Bonding curve:** configurable virtual/real reserves, fees, supply limits, and graduation threshold.
- **Graduation:** explicit migration event with configurable initial pool reserves and LP ownership/lock assumptions.
- **Post-graduation pool:** constant-product AMM by default, with configurable fees and liquidity changes.
- **Reference venue:** optional noisy external price process for cross-venue basis and arbitrage experiments.

Protocol parameters are configuration, not hard-coded claims about current Pump.fun / PumpSwap deployment values. Calibrate them against a dated, verified on-chain sample before interpreting results as empirical.

## Stochasticity and reproducibility

- Each agent receives a separate deterministic random-number stream derived from the master seed. Agent iteration order must not change another agent's random draws.
- Agent traits are sampled from configurable distributions, not assigned one fixed archetype.
- Decision arrivals use stochastic clocks; order size, latency, slippage tolerance, attention, sentiment, and private signals vary.
- Market regimes use probabilistic transitions and endogenous feedback; no scenario script dictates a fixed buy-then-dump path.
- A seed reproduces a run; changing the seed produces a different plausible path. Monte Carlo conclusions must be reported as distributions and confidence intervals, never as one deterministic forecast.

## Model integrity

- Keep true reserves, executable depth, latent reference price, executed trades, and observed candles as separate data objects.
- Never create OHLCV volume without an underlying simulated execution.
- Mark assumptions and calibration status on every experiment.
- Include unit tests for AMM invariants, fees, conservation of balances, supply accounting, migration, event ordering, and seeded reproducibility.

## Planned package layout

```
src/pump_sim/
  config.py
  random_streams.py
  domain.py
  engine.py
  market/
    bonding_curve.py
    constant_product.py
    lifecycle.py
    candles.py
  agents/
    base.py
    dev_treasury.py
    sniper.py
    kol.py
    arbitrageur.py
    retail.py
    whale.py
    lp_provider.py
    mev_risk.py
  experiments/
    scenarios.py
    monte_carlo.py
    metrics.py
tests/
```

## Status

Initial project specification. The executable engine and calibration data are not yet implemented.
