# Model specification

## 1. Simulation contract

This is an agent-based model (ABM), not a scripted price path. The same initial configuration and seed reproduce the same run; changing the seed changes agent traits, private noise, arrivals, order latency, block ordering, external-price shocks, and feed faults.

Each participant has:
- an independent wallet and inventory;
- a private pseudo-random stream, so one agent's decisions do not consume another agent's random draws;
- heterogeneous behavioral traits sampled at initialization;
- a stochastic activation clock;
- noisy observations of momentum, attention, sentiment, volatility, liquidity, and Dev supply risk.

At each simulation step, agents independently decide whether to wake up. Their orders receive random network latency, are assigned to a simulated block, and are ordered by a random priority score. There is no fixed sequence such as "snipers buy, KOL posts, retail FOMOs, then Dev sells."

## 2. Participants and incentives

| Agent | Main objective | Distinct behavior |
|---|---|---|
| Dev / treasury | Preserve disclosed project inventory and liquidity commitments | Holds unlocked and locked allocations separately; commits a configured quote budget to LP at migration; can withdraw its own LP under a volatility-risk rule; no covert price-support or dump policy |
| Early sniper | Capture short-horizon launch opportunities | High early-curve activity, short and heterogeneous holding horizons, probabilistic exit around migration, profit/risk exits |
| KOL | Maximize audience response and credibility | Posts stochastically; credibility differs by KOL; posts move attention and sentiment with noise and decay |
| Arbitrageur | Capture cross-venue basis after costs | Compares local AMM price with a noisy external reference venue, pays external fees, and is capped by external executable depth |
| Retail | Make limited-information decisions | Heterogeneous momentum, social-proof, FOMO, noise, risk aversion, and loss aversion |
| Whale | Manage larger inventory and execution risk | Larger order sizes, higher entry thresholds, lower activity, and greater sensitivity to concentration and market impact |
| LP provider | Earn fees while managing inventory exposure | May acquire inventory during the curve or pool phase; adds liquidity when a fee-yield proxy compensates for volatility risk; withdraws when its risk threshold is breached |
| MEV / sandwich-risk actor | Represent adverse execution pressure | Estimates potential extraction/slippage exposure from order size relative to depth; it is an abstract risk overlay, not a live sandwich bot |

The initial Dev allocation is 20% of total supply in the default synthetic configuration. 75% of that allocation is treated as locked, while the unlocked portion is held by the Dev account. The baseline also assigns 20% to other locked supply, 50% to the curve's real token inventory, and 10% to the external reference venue's token inventory. These are scenario defaults, not recommendations or Pump.fun protocol facts.

### Behavioral signal

Trader agents use a noisy utility score:

\[
U_i = a_i M + b_i \log(A) + cS + q_i(F-0.5) - r_i V - d_i \max(0, D_f - 0.10) + \epsilon_i
\]

where:
- \(M\) is the latest log return / momentum signal;
- \(A\) is attention;
- \(S\) is sentiment;
- \(V\) is realized volatility;
- \(F\) is the latent project-quality signal (agents observe it with noise);\n- \(D_f\) is Dev's unlocked token and LP-claim exposure as a share of circulating supply;
- \(a_i,b_i,r_i,d_i\) are heterogeneous traits;
- \(\epsilon_i\) is agent-specific noise.

Agents compare this score with their own thresholds. Order sizes are random fractions of available capital or inventory. The model does not force agents to trade.

### Arrival and disorder

An agent activates during a step of length \(\Delta t\) with probability:

\[
P(\text{wake}_i)=1-e^{-\lambda_i\Delta t}
\]

where \(\lambda_i\) is its individually sampled activity rate.

Order latency is exponentially distributed. Orders settle in simulated blocks and are ordered by a random priority score. This creates asynchronous, path-dependent order flow and prevents all participants from reacting to the same tick in a fixed order.

## 3. Market mechanics

### Bonding curve

The curve uses configurable virtual reserves \(x\) (token) and \(y\) (quote), with \(k=xy\). A buy of gross quote \(q\) pays a fee \(f\), so \(q_n=q(1-f)\), and receives:

\[
\Delta x = x - \frac{xy}{y+q_n}
\]

A sell of \(\Delta x\) returns gross quote:

\[
q_g = y - \frac{xy}{x+\Delta x}
\]

The sell is capped by accumulated real quote reserves. Fees are tracked separately. Graduation occurs when the configured real quote reserve threshold is reached. The remaining real token and quote reserves seed the post-graduation pool.

### Post-graduation pool

The pool is a configurable constant-product AMM. Buys and sells use the fee-adjusted input/output. A configurable share of pool fees remains in reserves and accrues to LPs through the pool share value; the remainder is tracked as protocol fees.

LP shares are proportional claims on pool reserves. Initial migration LP shares can be marked locked. Additional Dev and LP-provider positions are separately accounted for.

### Cross-venue arbitrage

The external venue is represented by a stochastic reference price, an external fee, finite quote depth, and a separately accounted initial token reserve. Local buys transferred to the reference venue increase its token inventory; local sells consume that inventory and replenish its quote reserve. This keeps token supply accounting explicit. The external venue is still a simplified reference process rather than a second fully calibrated AMM.

## 4. Endogenous attention and regimes

The external reference price follows a geometric Brownian process whose drift and volatility depend on a probabilistic regime: quiet, hype, stress, or recovery. Regime changes are random and mildly influenced by attention, sentiment, and recent returns; they are not scheduled.

Attention and sentiment mean-revert. KOL posts create small stochastic impulses. Retail agents react to these signals with different sensitivities and noise levels.

## 5. MEV and adverse execution

The MEV agents calculate an estimated risk cost based on trade notional relative to available depth. This is a stress-test overlay and a reporting metric. It does not construct transactions, simulate a real mempool, or implement front-run/back-run instructions. No wallet, RPC, or live trading connection exists.

## 6. Candles and data quality

Two tapes are maintained:

- **True tape:** one record for every simulated execution.
- **Observed tape:** a feed projection with configurable latency, dropped events, and duplicate deliveries.

Only true executions create true OHLCV volume. Duplicate or delayed observations can make a chart feed appear stale, out of order, or to have a different volume total, but those observations are not treated as extra on-chain trades.

## 7. Required interpretation

The defaults are deliberately synthetic and are not calibrated Pump.fun or PumpSwap parameters. Before using outputs as empirical estimates:
1. replace curve and migration parameters with dated, verified protocol values;
2. calibrate agent arrival rates and trade-size distributions from a representative on-chain sample;
3. validate the model against real launch cohorts;
4. run many independent seeds and report distributions, not a single path.

A seeded run is reproducible, not a forecast. The model is for research and risk analysis, not investment advice.
