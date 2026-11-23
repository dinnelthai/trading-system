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

The current default config uses a standard Pump-style reserve snapshot:
- Total supply: 1B tokens.
- Dev pre-minted genesis allocation: 0%.
- Other locked supply: 0%.
- Bonding-curve real token inventory: 793.1M.
- Derived migration inventory: 206.9M.
- External reference-venue token inventory: 0%.
- Virtual curve reserves: 1.073B tokens and 30 SOL.
- Initial migration LP shares: 100% marked locked.

These values are model inputs inherited from the project specification, not a guarantee that every deployment version or launch uses identical parameters. A nonzero Dev genesis allocation is a custom supply layout and changes the residual migration inventory unless other reserve buckets are changed. A Dev curve purchase must be modeled as an executed curve trade, not as a free genesis allocation.

Curve reserves, fees, external venue depth, agent counts, and behavioral parameters remain illustrative until replaced with dated, verified on-chain parameters and calibrated participant distributions.

## Research docs

- [Tokenomics and supply accounting (R01)](docs/TOKENOMICS.md)
- [Bonding curve mathematics and execution (R02)](docs/BONDING_CURVE.md)
- [Pool microstructure and candle diagnostics (R03)](docs/POOL_MICROSTRUCTURE.md)
- [Model specification](docs/MODEL.md)
- [Experiment plan](docs/EXPERIMENTS.md)
- [Empirical calibration data contract](docs/CALIBRATION.md)
- [Technical R04 replay and calibration](docs/R04_REPLAY.md)
- [Solana raw archive export and decoder gate](docs/SOLANA_ARCHIVE.md)

The simulator reports distributions, participant-level outcomes, token and LP concentration, fee-aware pool depth, liquidity add/remove events, fees, drawdown, graduation, execution slippage, and true-versus-observed candle differences. Set `record_pool_event_trace=true` to include the detailed pool-state event trace in a run summary. Use `--csv-out results/runs.csv --summary-only` to export compact Monte Carlo results. A seed is reproducible, not predictive; use many seeds and report uncertainty.


## Empirical calibration

For descriptive swap-only statistics, normalize trades to the schema in `docs/CALIBRATION.md` and run:

    pump-calibrate --input data/swaps.csv --out results/calibration.json

To export raw finalized Solana blocks while preserving transaction order, set `SOLANA_RPC_URL` and run:

    solana-block-export --start-slot START_SLOT --end-slot END_SLOT --out data/raw_transactions.jsonl

See `docs/SOLANA_ARCHIVE.md` for archive requirements and the decoder gate.

For deterministic event replay, normalize swaps, liquidity changes, migration, and state snapshots to the v1.0 JSONL contract in `docs/R04_REPLAY.md`, then run:

    pump-replay --input data/normalized_events.jsonl --out results/replay.json

Smoke-test the installed command with the synthetic fixture:

    pump-replay --input examples/normalized_events.synthetic.jsonl --out results/example_replay.json

The replay checks event ordering, reserve continuity, LP position continuity, and snapshot drift. It validates only the supplied normalized event stream; it does not certify archive completeness or decode raw Solana instructions. Neither command overwrites the synthetic default configuration.
