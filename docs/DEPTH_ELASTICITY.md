# Pool Depth Elasticity — Genuine Volume, Routing Choice, and Experiment Design

**Document type:** Market-quality and demand-response research specification  
**Version:** 0.1  
**Status:** Mathematical model defined; multi-venue trader routing and causal calibration are not implemented  
**Parent specification:** [Market Making & Market Quality System](MARKET_MAKING_MARKET_QUALITY.md)  
**Related specifications:** [Dev LP vs Treasury — Dynamic Capital Allocation](DEV_LP_TREASURY_ALLOCATION.md), [Pool Microstructure](POOL_MICROSTRUCTURE.md), [Experiment Plan](EXPERIMENTS.md)  
**Scope:** Genuine independent swaps across PumpSwap CPMM and competing executable venues

> This specification models how improved execution conditions can affect venue choice and successful external trading. It does not target a desired candle, manufacture volume, coordinate deceptive trading, or count controlled-wallet turnover as demand.

---

## 1. Research question and estimand

The target quantity is the causal response of **genuine successful volume routed to the local pool** to a change in effective pool depth, holding the external order-intent process and other market conditions constant:

\[
\boxed{\epsilon_V=\frac{\partial\ln V_{pool}^{genuine}}{\partial\ln D}}
\]

where:

- \(V_{pool}^{genuine}\): quote notional of successful swaps from independent external beneficial owners;
- \(D\): effective one-sided quote reserve/depth of the pool;
- \(\epsilon_V\): local depth elasticity of genuine successful pool volume.

For a balanced CPMM, quote-denominated TVL is approximately \(T\approx2D\). Since \(\ln T=\ln D+\ln2\), elasticity with respect to TVL is the same as elasticity with respect to one-sided depth, provided the pool remains balanced and the same depth definition is used.

This elasticity is not a protocol constant. It changes with trade-size distribution, competing venues, fees, latency, volatility, route behavior, participant type and market regime. It may be close to zero, positive, or locally negative.

## 2. Separate external demand from local-pool capture

For participant class \(i\), define:

- \(\lambda_i\): arrival rate of genuine external trade intent;
- \(\bar N_i(D)\): mean quote notional conditional on an intent;
- \(s_{i,p}(D)\): probability the trader chooses the local pool rather than another venue or no-trade;
- \(p_{i,fill}(D)\): probability the chosen order executes successfully;
- \(V_{i,p}\): successful local-pool volume from that class.

Then:

\[
V_{i,p}(D)=\lambda_i\bar N_i(D)s_{i,p}(D)p_{i,fill}(D)
\]

and:

\[
\boxed{
V_p(D)=\sum_i V_{i,p}(D)
}
\]

The external arrival process \(\lambda_i\) is held fixed when estimating the pure execution-depth effect. In a full market model, attention and information can change \(\lambda_i\), but that is a separate demand-generation channel and must not be confused with depth elasticity.

Taking logarithmic derivatives gives:

\[
\boxed{
\epsilon_V
=\sum_i w_i
\left(
\epsilon_{N,i}+\epsilon_{s,i}+\epsilon_{fill,i}
\right)
}
\]

where \(w_i=V_{i,p}/V_p\), and each component is the corresponding logarithmic derivative with respect to \(D\). This decomposition identifies whether additional volume comes from larger orders, more routing share, or fewer failed/reverted orders.

A successful swap is counted once. An LP addition/removal, wallet transfer, internal accounting movement, failed transaction or feed duplicate is not swap volume.

## 3. Fee-aware CPMM execution cost

Let the pool have Token reserve \(X\), quote reserve \(Y=D\), spot price \(P=Y/X\), and total swap fee \(f\).

### 3.1 Quote-in buy

For gross quote input \(Q\):

\[
T_{out}=\frac{X(1-f)Q}{D+(1-f)Q}
\]

The buyer's all-in execution cost relative to the pre-trade pool spot is:

\[
\boxed{
c_{buy}(D,Q)=\frac{Q}{P T_{out}}-1
=\frac{f}{1-f}+\frac QD
}
\]

This separates the fee component from the depth-dependent impact component. It assumes the pre-trade pool spot equals the independent reference price; reference basis, route costs and settlement movement are separate terms.

### 3.2 Token-in sell

For Token input \(q\), define its pre-trade quote notional \(N=Pq\). The user receives:

\[
Q_{out}=(1-f)\frac{Dq}{X+q}
\]

The shortfall relative to selling at the pre-trade spot is:

\[
\boxed{
c_{sell}(D,N)=
1-\frac{Q_{out}}{Pq}
=1-\frac{1-f}{1+N/D}
}
\]

For small orders relative to depth:

\[
c_{sell}\approx f+\frac ND
\]

The exact pool implementation, including LP-retained and protocol-removed fee portions, is authoritative for production calculations. These equations are analytical CPMM baselines.

## 4. Trader route choice: a multinomial-logit baseline

A trader compares generalized execution costs across the local pool, competing venues and a no-trade option.

Let \(c_{i,v}\) be participant \(i\)'s generalized cost at venue \(v\), and \(c_{i,0}\) the reservation cost of not trading. A useful stochastic choice model is:

\[
\boxed{
s_{i,p}(D)=
\frac{\exp(-\beta_i c_{i,p}(D))}
{\exp(-\beta_i c_{i,0})+
\sum_{v\in\mathcal V}\exp(-\beta_i c_{i,v}(D))}
}
\]

where \(\beta_i>0\) is the participant's sensitivity to execution cost. Heterogeneous \(\beta_i\) values preserve different trader preferences; not every trader chooses the numerically cheapest route.

If only the local pool's cost changes with its depth, the local route-share elasticity is:

\[
\boxed{
\epsilon_{s,i}
=\frac{\partial\ln s_{i,p}}{\partial\ln D}
=-\beta_i(1-s_{i,p})
\frac{\partial c_{i,p}}{\partial\ln D}
}
\]

Since greater depth reduces price impact, the cost derivative is normally negative and route-share elasticity is positive.

For small quote-equivalent order size \(N_i\), using \(c_{i,p}\approx f+N_i/D\):

\[
\boxed{
\epsilon_{s,i}\approx
\beta_i(1-s_{i,p})\frac{N_i}{D}
}
\]

This predicts diminishing marginal benefit as the local pool already captures most routeable flow (\(s_{i,p}\to1\)). It also predicts stronger depth sensitivity for larger orders, provided those orders are not already constrained by capital or other venue limits.

The model must include a no-trade option. Otherwise, it forces every intent to execute somewhere and overstates realized volume when execution is unattractive.

## 5. Fill probability and slippage tolerance

Route selection alone is insufficient. An order can choose the local pool and still fail because its quoted output is stale or its slippage tolerance is exceeded.

Let:

- \(I_i(D)\): expected depth-related execution slippage at the time of execution;
- \(L_i\): adverse price movement between quote and settlement;
- \(\tau_i\): trader's maximum tolerated slippage;
- \(F_{\tau_i}\): distribution of trader slippage tolerance.

Then:

\[
p_{i,fill}(D)=
\Pr(\tau_i\geq I_i(D)+L_i)
\]

If \(L_i\) is held fixed in a matched counterfactual and \(z_i(D)=I_i(D)+L_i\), then:

\[
\boxed{
\epsilon_{fill,i}
=
-\frac{f_{\tau_i}(z_i)}
{1-F_{\tau_i}(z_i)}
\frac{\partial z_i}{\partial\ln D}
}
\]

where \(f_{\tau_i}\) is the tolerance density. As depth rises and expected impact falls, fill probability generally increases. The effect is largest near the population's slippage-tolerance boundary; it is small when almost all orders already fill or almost all still fail.

The simulator must distinguish:
- intent generated;
- venue selected;
- order submitted;
- order settled;
- order failed/reverted;
- successful quote notional.

Do not infer demand from successful swaps alone without tracking the attempted-order denominator.

## 6. Arbitrage flow is a separate depth-response channel

Arbitrage is genuine external trading when independent participants trade against a real price discrepancy. It must be separated from discretionary organic flow because its arrival process and economic role differ.

For a fee-free CPMM, let \(P\) be local pool spot and \(P_{ref}\) an independent reference price.

If \(P_{ref}>P\), an arbitrageur buys from the local pool. The quote amount that moves the local marginal price to the reference is:

\[
\boxed{
Q_{arb}^{*}=D\left(\sqrt{\frac{P_{ref}}P}-1\right)
}
\]

If \(P_{ref}<P\), a seller supplies Token to the local pool. The quote-equivalent Token notional required to move the marginal price to the reference is:

\[
\boxed{
N_{arb}^{*}=D\left(\sqrt{\frac P{P_{ref}}}-1\right)
}
\]

These are fee-free pool-capacity identities, not guaranteed arbitrage volume. Actual arbitrage requires the basis to exceed the pool fee, external venue fee, route costs, latency and risk premium. The fee-aware adapter must solve the executable no-arbitrage band.

A practical capacity model is:

\[
V_{arb}(D,\Delta P)=
\lambda_{basis}
\mathbb E\left[
\min\left(
Q_{pool}^{*}(D,\Delta P),
Q_{external},
Q_{capital},
Q_{risk}
\right)
p_{arb,fill}
\right]
\]

At a fixed price basis, if local pool capacity is the binding limit, arbitrage capacity scales approximately linearly with \(D\), so its local elasticity can approach 1. If external venue depth, arbitrage capital or risk limits bind, its elasticity approaches 0. Basis arrival frequency \(\lambda_{basis}\) remains a separate stochastic input.

Arbitrage volume is not automatically profitable LP volume. It can correct stale pool prices and contribute to LVR/adverse selection. Do not add a separate arbitrage loss to LVR unless it is demonstrably outside the LVR benchmark and is not already included in realized scenario PnL.

## 7. Aggregate elasticity by flow type

Keep at least three external flow classes:

1. **Discretionary organic flow:** retail, whales and snipers choosing whether, when and where to trade.
2. **Arbitrage flow:** cross-venue price correction after fees and capacity constraints.
3. **Other informed directional flow:** participants trading on independent information or inventory needs.

Then:

\[
V_p=V_{organic}+V_{arb}+V_{informed}
\]

and:

\[
\boxed{
\epsilon_V=
w_o\epsilon_o+w_a\epsilon_a+w_i\epsilon_i
}
\]

where each weight is that flow class's share of successful genuine pool volume. Report both total elasticity and each component. The same elasticity can have very different LP risk depending on whether incremental volume comes from uninformed discretionary flow or informed price-correcting flow.

KOL attention and market-wide demand shocks primarily affect arrival rates and order intent. Hold them constant in the pure depth experiment; vary them separately in the full market-regime experiment.

## 8. Numerical route-choice illustration

This example isolates route choice and is not a calibrated estimate.

Assume:

- local CPMM total fee \(f=0.30\%\);
- one quote-in buy order \(Q=1\) SOL;
- initial quote reserve \(D=50\) SOL;
- competing route generalized cost \(c_{out}=2.20\%\);
- trader cost sensitivity \(\beta=80\);
- one local pool and one aggregated outside option.

Initial local-pool execution cost:

\[
c_{pool}(50)=\frac{0.003}{0.997}+\frac1{50}
=2.3009\%
\]

Increase depth by 20%, from 50 to 60 SOL, without changing spot price or external demand:

\[
c_{pool}(60)=\frac{0.003}{0.997}+\frac1{60}
=1.9676\%
\]

The logit route share changes:

| Measure | Depth 50 SOL | Depth 60 SOL |
|---|---:|---:|
| Local-pool cost | 2.3009% | 1.9676% |
| Local-pool route share | 47.98% | 54.64% |

Finite-change elasticity:

\[
\frac{\ln(54.64\%/47.98\%)}{\ln(60/50)}
\approx0.712
\]

Local analytical elasticity at the initial depth:

\[
\epsilon_s\approx
80(1-0.4798)\frac1{50}
\approx0.832
\]

The difference between 0.712 and 0.832 is expected: one is a finite 20% change, the other is a local derivative at the starting state.

The example demonstrates a possible mechanism: deeper liquidity lowers execution cost, which can increase the fraction of independently generated orders choosing the pool. It does not prove that a real PumpSwap pool has this elasticity. Real values require observed route alternatives, order sizes, trader choice and failed-order data.

## 9. What the current simulator does and does not identify

Current main-branch behavior:

- Heterogeneous participants generate asynchronous buy/sell decisions.
- Ordinary participant buys and sells execute against the local curve/pool.
- Slippage tolerance and block settlement can cause failed orders.
- Arbitrageurs compare the local pool with a stochastic external reference and finite external quote reserve.
- The external venue is not yet a fully executable competing AMM with its own side-specific quotes and route choice for retail/whale/sniper agents.
- Non-arbitrageur agents do not currently choose among multiple venues and a no-trade option based on generalized execution cost.

Therefore, the current simulator can measure pool depth, execution slippage, failed orders and arbitrage capacity, but it cannot yet identify a complete behavioral multi-venue \(\epsilon_V\). Any volume change caused by price-path feedback or execution failures must not be mislabeled as a calibrated route-choice elasticity.

## 10. Causal experiment design

Use two stages so that mechanical execution effects are not confused with behavioral feedback.

### Stage A — Fixed intent replay

Generate or record an exogenous tape of participant intents before changing pool depth. Each intent contains:

- stable pseudonymous participant ID and participant class;
- arrival timestamp;
- buy/sell direction;
- desired quote-equivalent notional;
- slippage tolerance;
- latency and settlement assumptions;
- independent information/flow category.

Replay the same tape across proportional depth variants:

\[
D/D_0\in\{0.50,0.75,1.00,1.25,1.50,2.00\}
\]

Preserve opening spot price, total supply, external reference path, fee schedule, participant inventory budgets and alternative venue state. Any additional LP capital must be funded by an explicitly modeled independent LP endowment and reconciled to token supply and quote balances.

Measure the mechanical change in execution cost, route share, fill rate, successful local volume, arbitrage capacity and price divergence.

### Stage B — Adaptive agent response

Run the full ABM with matched seeds and identical exogenous regime/attention shocks. Let participants update route choice and order size after observing their own prior execution outcomes. This estimates behavioral feedback but must be reported separately from Stage A.

Use multiple independent seeds and retain all runs. Do not select a favorable path or optimize for a desired candle shape.

### Required controls

- Same starting spot and external reference basis.
- Same token supply and beneficial-owner inventory.
- Same external venue fees, reserves and market-data quality.
- Same participant count, wallet capital distribution and exogenous arrival process.
- Same KOL event tape and attention shocks for matched comparisons.
- Same fee tier within each paired comparison; test tier transitions separately.
- No Dev self-trading, controlled-wallet turnover, fabricated volume or hidden beneficial-owner aggregation.
- LP additions/removals are pool-state events, not swap volume.

### Required outputs

- intent count and requested notional;
- venue-choice share by participant class and side;
- fill/revert probability and failure reason;
- genuine successful quote volume by venue and flow type;
- trade-size and inter-arrival distributions;
- execution cost, VWAP slippage and marginal price impact;
- buy/sell depth at 1%, 5% and 10% impact;
- external/local price basis and convergence time;
- LP Fee accrual, LVR baseline and realized LP NLV change;
- unique external beneficial owners, wallet-volume concentration and volume HHI;
- route-choice and fill elasticities with confidence intervals.

## 11. Empirical identification and calibration

Historical TVL-volume correlation is not a causal estimate. Attention, price appreciation, token quality, pool age, KOL events, exchange listings and market-wide volatility can raise both TVL and volume.

Use:
- event-level swap and LP add/remove data;
- timestamps and reserve snapshots before and after liquidity events;
- route/aggregator quote data where available;
- participant class and independent beneficial-owner labels where verified;
- matched cohorts and held-out launches;
- event studies or difference-in-differences only where the liquidity change is plausibly exogenous and pre-trends are checked.

Swaps alone cannot reveal unsubmitted order intent, abandoned trades or the route a trader would have chosen elsewhere. If route-choice telemetry is unavailable, report an interval or scenario range, not a point estimate presented as fact.

Until validated, use \(\epsilon_V=0\) for the conservative LP capital-allocation baseline. Do not assume the pool earns more volume merely because its TVL is higher.

## 12. Implementation requirements

1. Add a venue-quote interface with side, input notional, expected output, fee, impact, latency estimate, failure probability and state watermark.
2. Model at least one competing executable venue with finite reserves and its own fee/depth; a reference price alone is not a route.
3. Add a no-trade option and heterogeneous route-cost sensitivity to trader decisions.
4. Keep external order-intent arrivals separate from route choice and successful execution.
5. Record attempted, selected, submitted, settled and failed order states with stable IDs.
6. Keep organic, arbitrage and informed flow attribution separate.
7. Add side-aware local and competing venue depth to the shared snapshot.
8. Preserve token supply, wallet balances, pool reserves and LP ownership through all counterfactuals.
9. Calibrate route sensitivity and slippage-tolerance distributions only from appropriate observations; mark synthetic parameters clearly.
10. Feed measured elasticity and uncertainty into the LP-versus-Treasury allocator as a proposal input, never as authority to override risk or market-integrity gates.

## 13. Acceptance criteria

The depth-elasticity model is not accepted until:

1. The same exogenous intent tape can be replayed across depth variants.
2. Proportional liquidity changes preserve opening spot price.
3. Token supply, quote capital and LP ownership reconcile exactly within numerical tolerance.
4. Venue choice includes competing execution costs and a no-trade option.
5. Failed and reverted orders are separated from successful volume.
6. Only genuine independent successful swaps count toward volume and fee estimates.
7. Organic, arbitrage and informed flow elasticities are reported separately.
8. Route-choice and fill effects are separated from changes in exogenous demand.
9. Results include matched-seed uncertainty and held-out validation.
10. No acceptance criterion rewards artificial volume, wash trading, deceptive coordination or engineered candle patterns.

No live execution is authorized by this document.
