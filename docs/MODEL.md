# Model specification

## 1. Simulation contract

This is a stochastic agent-based model (ABM), not a scripted price path. The same configuration and seed reproduce the same run; changing the seed changes participant traits, wallet capital, private noise, arrivals, order latency, block ordering, market shocks, and feed faults.

Each participant has:
- an independent wallet and inventory;
- a private pseudo-random stream;
- heterogeneous behavioral traits and a role-specific wealth distribution;
- an independent continuous-time activation clock;
- noisy observations of momentum, attention, sentiment, volatility, liquidity, and Dev supply risk.

The event engine processes participant activations and block settlements in timestamp order. A participant can react to trades that have already settled before its own wake time. There is no fixed sequence such as "snipers buy, KOL posts, retail FOMOs, then Dev sells."

## 2. Participants and incentives

| Agent | Main objective | Distinct behavior |
|---|---|---|
| Dev / treasury | Manage disclosed project inventory, liquidity commitments and treasury exit | Current simulator: optional unlocked/locked allocation, time-based vesting, configurable fixed-fraction treasury sales, LP commitment and risk-based withdrawal. Target research: beneficial-owner-aware adaptive partial exit and route selection; not yet implemented |
| Early sniper | Capture short-horizon launch opportunities | High early-curve activity, short heterogeneous holding horizons, probabilistic migration exits, profit/risk exits |
| KOL | Maximize audience response and credibility | Stochastic posts; individual credibility; noisy attention and sentiment impulses with decay |
| Arbitrageur | Capture cross-venue basis after costs | Inactive on the bonding curve; after graduation compares the local pool with a noisy external reference venue, subject to fees and finite depth |
| Retail | Make limited-information decisions | Heterogeneous momentum, social-proof, noise, FOMO, risk aversion, and loss aversion |
| Whale | Manage larger inventory and execution risk | Larger and less frequent orders, different entry thresholds, concentration sensitivity |
| LP provider | Earn fees while managing inventory exposure | May acquire inventory during the curve; adds liquidity after migration when fee opportunity compensates for risk; withdraws when its risk threshold is breached |
| MEV / sandwich-risk actor | Represent adverse execution pressure | Estimates execution-risk exposure from trade size and depth; abstract stress-test overlay, not a live sandwich bot |

The current Dev treasury sale behavior is a simple configured vesting-sale baseline, not an adaptive optimal-stopping policy. The target policy is specified in DEV_TREASURY_EXIT.md and remains research-only until implemented and validated.

The default Pump-style scenario has no pre-minted Dev allocation. Dev allocation, other locked supply, and external token inventory remain configurable for non-standard launches. Initial wallet capital is sampled from role-specific bounded log-normal distributions. Trait multipliers are also sampled multiplicatively, so a role is a population distribution rather than one fixed personality.

## 3. Behavior and disorder

### Behavioral utility

Trader agents use a noisy utility score:

\[
U_i = a_i M + b_i \log(A) + cS + q_i(F-0.5) - r_i V - d_i \max(0, D_f - 0.10) + \epsilon_i
\]

where:
- \(M\) is the latest log-return / momentum signal;
- \(A\) is attention;
- \(S\) is sentiment;
- \(V\) is realized volatility;
- \(F\) is a latent project-quality signal;
- \(D_f\) is Dev's unlocked token and LP-claim exposure as a share of circulating supply;
- \(a_i,b_i,q_i,r_i,d_i\) are heterogeneous traits;
- \(\epsilon_i\) is agent-specific noise.

Agents compare this score with their own thresholds. Order sizes are random fractions of available capital or inventory. Agents can remain inactive; the model does not force a trade each time they wake.

### Asynchronous arrivals

Each agent's next wake time is drawn from an independent exponential inter-arrival process:

\[
\Delta t_i \sim \operatorname{Exponential}(\lambda_i), \qquad P(\text{wake}_i\text{ within }\Delta t)=1-e^{-\lambda_i\Delta t}
\]

Order latency is also exponentially distributed. Orders settle in simulated blocks and are ordered by random priority. Exogenous price-regime updates remain on a market clock, while trader arrivals and order execution are asynchronous.

## 4. Pump-style market mechanics

The default curve parameters follow the published Pump program reserve snapshot for a standard SOL-paired launch:
- total token supply: 1,000,000,000;
- initial virtual token reserves: 1,073,000,000;
- initial virtual quote reserves: 30 SOL;
- initial real curve token reserves: 793,100,000;
- remaining migration token inventory: derived from total supply and configured allocations (206,900,000 in the default scenario).

The Pump public program documentation describes the bonding curve as a constant-product curve over virtual reserves. On buys, virtual quote reserves and real quote reserves increase while virtual token reserves and real token reserves decrease; sells reverse those movements. A curve is complete when its real token reserves reach zero. See:
- [Pump program reserve state and completion rule](https://github.com/pump-fun/pump-public-docs/blob/main/docs/PUMP_PROGRAM_README.md)
- [Synthetic migration and post-completion pool reserve calculations](https://github.com/pump-fun/pump-public-docs/blob/main/docs/SYNTHETIC_MIGRATION.md)

### Bonding curve

The curve uses virtual reserves \(x\) (token) and \(y\) (quote), with \(k=xy\). The simulator calculates protocol and creator fees separately, supports market-cap fee tiers, and keeps V3 protocol/creator fees in a separate pending-fee vault. For a continuous all-in quote budget \(G\) and combined rate \(r\), the reserve input is \(N=G/(1+r)\).

A buy receives:

\[
\Delta x = \frac{xN}{y+N}
\]

A sell of \(\Delta x\) removes gross quote from the real reserve:

\[
q_g = \frac{y\Delta x}{x+\Delta x}
\]

The seller receives gross quote less protocol and creator fees. The curve sell is capped by real quote reserves:

\[
\Delta x_{max}=\frac{R_Qx}{y-R_Q}
\]

The model separately tracks:
- virtual token / quote reserves used for price calculation;
- real token reserves available to curve buyers;
- the full token-account balance, including migration inventory;
- real quote reserves available to fund sells;
- pending protocol and creator fees, which are not LP liquidity;
- the immediate buyback-fee outflow.

The expected real quote reserve at curve completion is approximately 85 SOL for the default reserve snapshot. This is a diagnostic target, **not** the graduation trigger.

### Graduation and migration

Graduation is triggered when `real_token_reserves` are exhausted, not when a quote-volume or quote-reserve threshold is crossed.

At migration:
- the remaining token-account balance becomes the PumpSwap base reserve;
- the real quote reserve, less the configured migration account-creation fee, becomes the pool quote reserve;
- if a V3 completing buy includes a synthetic pool leg, its net quote input is added and its token output is removed before the pool is created;
- pending protocol and creator fees remain separate and are not included in pool liquidity;
- the initial LP shares are marked locked/burned according to `initial_lp_lock_fraction`;
- the simulator records the price gap between the final curve price and the initial pool price.

The default migration fee is 0.015000001 quote units, based on the published SOL migration-fee field. The default reserve values are rounded public-documentation values, so a small migration price gap is expected. A test asserts that the default migration gap stays within 3 bps.

The simulator supports the V3 synthetic-migration path. A completing buy can exhaust the remaining real curve inventory and spend its remaining budget against the pool-to-be using the bonding-curve fee schedule. The post-completion pool reserves are updated before migration, so the pool opens at the price where the synthetic buy stopped. The legacy/partial-fill path remains configurable through curve_synthetic_migration=false. See [R02 — Bonding Curve Mathematics and Execution](BONDING_CURVE.md) and Pump's [synthetic migration specification](https://github.com/pump-fun/pump-public-docs/blob/main/docs/SYNTHETIC_MIGRATION.md).

### Post-graduation pool

The pool is a configurable constant-product AMM. Buys and sells use fee-adjusted input/output. A configurable share of pool fees remains in reserves and accrues to LPs through pool share value; the remainder is tracked as protocol fees.

LP shares are proportional claims on pool reserves. Initial migration LP shares can be marked locked/burned. Additional Dev and LP-provider positions are separately accounted for. LP cost basis is tracked across deposits and withdrawals to prevent double-counting PnL.

PumpSwap pricing uses effective quote reserves: raw quote-vault balance plus the signed virtual quote reserve (i128), which may be negative. R03 currently models the net effective pricing reserve and does not keep those two on-chain components as independent state variables; R04 replay records both. Historical fee schedules and legacy/V2/V3 instruction variants must be selected by slot, not assumed constant.

R03 distinguishes pre-trade marginal spot price, swap execution/VWAP price, and post-trade marginal spot price. It solves buy and sell depth at 1%, 5%, and 10% marginal price impact using the actual LP/protocol fee split. The summary includes pool (k), quote-denominated TVL, depth, LP locked/agent/unassigned ownership, LP-share HHI, and liquidity add/remove totals.

Pool-state events can record migration, LP additions, LP removals, and swaps with before/after reserves, price, (k), and depth. The detailed trace is opt-in through `record_pool_event_trace=true`; aggregate metrics remain available by default. See [R03 — Pool Microstructure and Candle Diagnostics](POOL_MICROSTRUCTURE.md).

### Cross-venue arbitrage

The external venue is a simplified post-graduation reference venue with a stochastic reference price, external fee, finite quote depth, and separately accounted token inventory. Arbitrageurs do not trade against a fictitious second venue during the bonding-curve phase. The external venue is not yet a second fully calibrated AMM.

## 5. Endogenous attention and regimes

The external reference price follows a geometric Brownian process whose drift and volatility depend on a probabilistic regime: quiet, hype, stress, or recovery. Regime changes are random and mildly influenced by attention, sentiment, and recent returns; they are not scheduled.

Attention and sentiment mean-revert. KOL posts create stochastic impulses. Retail agents react with different sensitivities and private noise.

## 6. MEV and adverse execution

MEV-risk agents calculate an estimated risk cost based on trade notional relative to available depth. This is a stress-test overlay and reporting metric. It does not construct transactions, simulate a real mempool, or implement front-run/back-run instructions. No wallet, RPC, or live trading connection exists.

## 7. Candles and data quality

Two tapes are maintained:
- **True tape:** one record for every simulated execution.
- **Observed tape:** a feed projection with configurable latency, dropped events, and duplicate deliveries.

Only true executions create true OHLCV volume. Duplicate or delayed observations can make a chart feed appear stale, out of order, or have a different volume total, but those observations are not treated as extra on-chain trades.

Candles use executed swap VWAP, not the post-swap marginal spot price. Each bar also reports token volume, buy/sell quote volume, and buy/sell trade counts. R03 compares true and observed open/high/low/close, volume, side flow, trade counts, and buy/sell imbalance. LP additions and removals are recorded as pool-state events; they do not create swap volume or candles when deposits/withdrawals are ratio-matched.

## 8. Required interpretation

The Pump curve reserve structure and completion condition are protocol-grounded; agent arrival rates, capital distributions, behavior traits, external venue, pool fee split, and market regimes remain synthetic until calibrated against real launch cohorts.

Before interpreting outputs empirically:
1. fetch dated on-chain Global and BondingCurve state for each launch cohort;
2. use actual trade events and wallet balance deltas to calibrate arrivals, order sizes, and inventory;
3. include LP add/remove events and verified wallet labels where available;
4. validate on held-out launches;
5. run many independent seeds and report distributions, not a single path.

A seeded run is reproducible, not a forecast. The model is for research and risk analysis, not investment advice.
