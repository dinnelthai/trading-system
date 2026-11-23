# Pump Lifecycle Market Simulator

A stochastic agent-based research simulator for studying a token launch from bonding curve through graduation and post-graduation pool trading.

> Research and stress-testing only. The project does not connect to wallets or submit transactions. It does not implement wash trading, fabricated volume, deceptive coordination, artificial dumps, or a live sandwich bot. Adverse MEV behavior is represented as an abstract execution-risk estimate.

## Implemented participant population

- **Dev / treasury:** explicit unlocked and locked allocation, LP commitment at migration, and risk-based withdrawal of its own LP position.
- **Early snipers:** fast launch participation, heterogeneous holding horizons, and probabilistic migration exits.
- **KOLs:** stochastic posts with individual credibility; posts affect attention and sentiment with noise and decay.
- **Arbitrageurs:** trade a finite-inventory external reference venue against the local market, accounting for external fees and depth.
- **Retail:** heterogeneous momentum, social-proof, noise, FOMO, risk aversion, and loss aversion.
- **Whales:** larger and less frequent orders with different risk thresholds.
- **LP providers:** acquire inventory, add liquidity when fee opportunity compensates for risk, and withdraw when risk thresholds are breached.
- **MEV / sandwich-risk agents:** estimate adverse-execution exposure as a function of trade size and depth; no transaction construction or attack execution.

Each agent has its own wallet, traits, private random stream, activity clock, latency, and decision policy. Participants do not share one deterministic buy/sell signal.

## Market and randomness

- Configurable virtual/real-reserve bonding curve with fees and a graduation threshold.
- Graduation migrates remaining curve reserves into a constant-product pool.
- Configurable pool fee split between LP accrual and protocol fees.
- Initial migration LP shares can be marked locked.
- External reference price follows a stochastic regime process; the external venue has finite token inventory and quote reserves.
- Continuous-time Poisson-style agent activation, independent private signals, role-specific heavy-tailed wallet capital, random order latency, simulated block settlement, and randomized priority.
- Quiet / hype / stress / recovery regimes transition probabilistically. No pre-scripted pump-and-dump sequence.
- True execution candles are separated from observed feed candles. Feed latency, drops, and duplicate deliveries can create chart-observation errors without creating fake true trades.

## Quick start

Python 3.10+; runtime uses only the standard library.

    python -m venv .venv
    source .venv/bin/activate
    pip install -e ".[dev]"
    pytest -q

Run one simulation:

    python -m pump_sim --config configs/default.json --out results/run.json

Run 100 independent seeds and export one CSV row per market path:

    python -m pump_sim --config configs/default.json --runs 100 --csv-out results/runs.csv --summary-only --out results/monte-carlo-summary.json

Run the 500-path baseline locally:

    python -m pump_sim --config configs/default.json --runs 500 --csv-out results/baseline-runs.csv --summary-only --out results/baseline-summary.json

A manual GitHub Actions workflow (`baseline-simulation`) also runs the 500-path baseline and uploads its JSON/CSV results as an artifact. It becomes manually triggerable after this workflow is merged into the default branch.

Sweep one parameter across scenarios, with 100 seeds per value:

    python -m pump_sim --config configs/default.json --sweep-field dev_allocation --sweep-values 50000000,100000000,150000000,200000000 --runs 100 --out results/dev-concentration.json

Any SimConfig field can be supplied in the JSON config. The Python API exposes SimulationEngine, run_monte_carlo, and run_parameter_sweep.

## Default scenario is synthetic

The baseline uses a 1B supply with:
- Dev allocation: 20% of total supply; 75% of that allocation is locked.
- Other locked supply: 20%.
- Bonding-curve real token inventory: 50%.
- External reference-venue token inventory: 10%.

Curve reserves, fees, graduation threshold, external venue depth, agent counts, and all behavioral parameters are illustrative defaults. They are **not** claims about current Pump.fun or PumpSwap protocol constants. Replace them with dated, verified on-chain parameters and calibrated participant distributions before interpreting outputs empirically.

## Research docs

- [Model specification](docs/MODEL.md)
- [Experiment plan](docs/EXPERIMENTS.md)
- [Empirical calibration data contract](docs/CALIBRATION.md)

The simulator reports distributions, participant-level outcomes, concentration, liquidity, fees, drawdown, graduation, MEV-risk exposure, and true-versus-observed candle differences. Use `--csv-out results/runs.csv --summary-only` to export compact Monte Carlo results. A seed is reproducible, not predictive; use many seeds and report uncertainty.


## Empirical calibration

Normalize on-chain swaps to the schema in `docs/CALIBRATION.md`, then run:

    pump-calibrate --input data/swaps.csv --out results/calibration.json

The report separates observable trade behavior from latent traits that swaps alone cannot identify. It does not overwrite the synthetic default configuration.
