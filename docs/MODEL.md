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
| Dev / treasury | Manage disclosed project inventory and liquidity commitments | Optional unlocked and locked allocation; time-based vesting and treasury sales only when explicitly configured; optional LP commitment and risk-based withdrawal |
| Early sniper | Capture short-horizon launch opportunities | High early-curve activity, short heterogeneous holding horizons, probabilistic migration exits, profit/risk exits |
| KOL | Maximize audience response and credibility | Stochastic posts; individual credibility; noisy attention and sentiment impulses with decay |
| Arbitrageur | Capture cross-venue basis after costs | Inactive on the bonding curve; after graduation compares the local pool with a noisy external reference venue, subject to fees and finite depth |
| Retail | Make limited-information decisions | Heterogeneous momentum, social-proof, noise, FOMO, risk aversion, and loss aversion |
| Whale | Manage larger inventory and execution risk | Larger and less frequent orders, different entry thresholds, concentration sensitivity |
| LP provider | Earn fees while managing inventory exposure | May acquire inventory during the curve; adds liquidity after migration when fee opportunity compensates for risk; withdraws when its risk threshold is breached |
| MEV / sandwich-risk actor | Represent adverse execution pressure | Estimates execution-risk exposure from trade size and depth; abstract stress-test overlay, not a live sandwich bot |

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

The curve uses virtual reserves \(x\) (token) and \(y\) (quote), with \(k=xy\). A buy of gross quote \(q\) pays a fee \(f\), so \(q_n=q(1-f)\), and receives:

\[
\Delta x = x - \frac{xy}{y+q_n}
\]

A sell of \(\Delta x\) returns gross quote:

\[
q_g = y - \frac{xy}{x+\Delta x}
\]

The sell is capped by accumulated real quote reserves. The model separately tracks:
- virtual token / quote reserves used for price calculation;
- real token reserves available to curve buyers;
- the full token-account balance, including tokens reserved for migration;
- real quote reserves accumulated by curve trades.

The expected real quote reserve at completion is approximately 85 SOL for the default reserve snapshot. This is a diagnostic target, **not** the graduation trigger.

### Graduation and migration

Graduation is triggered when `real_token_reserves` are exhausted, not when a quote-volume or quote-reserve threshold is crossed.

At migration:
- the remaining token-account balance becomes the PumpSwap base reserve;
- the real quote reserve, less the configured migration account-creation fee, becomes the pool quote reserve;
- the initial LP shares are marked locked/burned according to `initial_lp_lock_fraction`;
- the simulator records the price gap between the final curve price and the initial pool price.

The default migration fee is 0.015000001 quote units, based on the published SOL migration-fee field. The default reserve values are rounded public-documentation values, so a small migration price gap is expected. A test asserts that the default migration gap stays within 3 bps.

The simulator models the standard completion-and-migrate path. It does not yet implement the newer v3 synthetic-migration oversized-buy path, where the completing buy can also trade against the pool reserves before the pool is created. That path is documented separately in Pump's synthetic migration specification and is a future fidelity upgrade.

### Post-graduation pool

The pool is a configurable constant-product AMM. Buys and sells use fee-adjusted input/output. A configurable share of pool fees remains in reserves and accrues to LPs through pool share value; the remainder is tracked as protocol fees.

LP shares are proportional claims on pool reserves. Initial migration LP shares can be marked locked/burned. Additional Dev and LP-provider positions are separately accounted for. LP cost basis is tracked across deposits and withdrawals to prevent double-counting PnL.

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

## 8. Required interpretation

The Pump curve reserve structure and completion condition are protocol-grounded; agent arrival rates, capital distributions, behavior traits, external venue, pool fee split, and market regimes remain synthetic until calibrated against real launch cohorts.

Before interpreting outputs empirically:
1. fetch dated on-chain Global and BondingCurve state for each launch cohort;
2. use actual trade events and wallet balance deltas to calibrate arrivals, order sizes, and inventory;
3. include LP add/remove events and verified wallet labels where available;
4. validate on held-out launches;
5. run many independent seeds and report distributions, not a single path.

A seeded run is reproducible, not a forecast. The model is for research and risk analysis, not investment advice.
