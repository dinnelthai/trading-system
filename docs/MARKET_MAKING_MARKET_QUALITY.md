# Market Making & Market Quality System

**Document type:** Product direction and research specification  
**Version:** 0.1  
**Status:** Direction locked; mathematical specification and simulation validation in progress  
**Repository:** `dinnelthai/trading-system`  
**Initial implementation scope:** Pump.fun Bonding Curve → graduation → PumpSwap CPMM fixed pool. Other AMM adapters may be researched later, but dynamic DLMM Bin and CLMM Tick positioning are out of the current core scope.

> This document defines the target system and its research boundaries. It is not a claim that all engines or strategies are already implemented, nor does it authorize live execution. The current simulator remains a research and stress-testing environment.

---

## 1. Product decision

The product is **not an LP Manager**.

The target product is a complete **Market Making & Market Quality System**. LP management is one execution capability inside a broader system that observes market state, understands participant flows, manages inventory and liquidity, evaluates execution quality, and controls risk over the full token lifecycle.

The system's purpose is to improve the quality and resilience of a real market under transparent rules and genuine independent participation. It should optimize executable liquidity, execution quality, inventory efficiency, and risk-adjusted market-making returns—not manufacture an attractive-looking chart.

### 1.1 Product objective

Continuously evaluate and improve:

1. **Two-sided executable depth** — how much can be bought or sold at defined price-impact budgets.
2. **Execution quality** — realized slippage, effective spread, transaction cost, failure rate, and execution latency.
3. **Price discovery** — relationship between pool price, execution price, and independent executable reference prices.
4. **Inventory health** — Token/SOL exposure, concentration, cost basis, and ability to rebalance.
5. **Liquidity efficiency** — capital utilization, fee income, withdrawability, and depth persistence.
6. **Market resilience** — how price basis and executable depth behave after shocks.
7. **Market integrity** — real independent participation, transparent ownership, and absence of fabricated activity.

A healthy market is not necessarily a low-volatility market. Genuine information, demand, and supply can produce sharp moves. The system should reduce avoidable execution failures and fragility, not suppress legitimate price discovery.

### 1.2 Explicit strategy constraints

- The core deployment model is a **fixed PumpSwap CPMM pool** with initial liquidity and proportional add/remove operations. Optimize the amount of committed liquidity and the timing/size of those operations; do not make dynamic Bin/Tick repositioning a core strategy.
- Keep spot inventory, LP claims, liquidity reserves and execution reserves in one reconciled capital ledger. LP underlying assets must not be double-counted as free inventory.
- Do **not** introduce perpetual futures or options as inventory hedges.
- Do not count LP deposits or withdrawals as swaps or trading volume.
- Do not use self-trades, wash trading, fabricated volume, deceptive coordination, artificial candles, or hidden treasury activity to create a false impression of demand or market health.
- Do not assume that an AMM LP position is equivalent to an order-book quote or a guaranteed limit order.
- Every action must be evaluated against protocol mechanics, fees, transaction costs, inventory limits, and execution risk.
- Keep research simulation, paper execution, and any future live execution as separate permissioned stages.
- Other AMM venues may be observed and modeled through adapters, but dynamic DLMM Bin or CLMM Tick optimization is outside the core strategy unless a future explicit product decision changes this scope.

---

## 2. System boundary and market lifecycle

The system spans the full launch lifecycle. Its active objectives and available actions change by phase.

| Phase | Market state | Primary responsibilities |
|---|---|---|
| 1. Launch preparation | Supply, allocations, wallets, launch parameters | Validate supply accounting, disclose treasury/vesting exposure, define risk budgets |
| 2. Bonding curve | Virtual/real reserves and curve trades | Observe curve state, participant arrivals, inventory distribution, completion probability |
| 3. Graduation / migration | Curve completion and pool initialization | Reconcile migration assets, initial pool price, pool depth, LP ownership and price gap |
| 4. Early market | Thin pool, concentrated holders, high uncertainty | Measure two-sided depth, inventory stress, toxic flow, execution quality and LP fragility |
| 5. Growth market | More independent participants and venues | Improve capital efficiency, depth persistence, routing and inventory turnover |
| 6. Mature / stress | Regime shifts, large holders, liquidity competition | Protect capital, maintain transparent liquidity policy, manage drawdown and resilience |

The system must not apply one fixed policy across all phases. Bonding-curve inventory, migrated pool inventory, LP claims, and freely transferable treasury holdings are different assets and must remain separate in the accounting model.

---

## 3. Eight core engines

The system is organized by responsibility. Engines share one canonical market-state snapshot and event stream; they do not independently submit conflicting actions.

### 3.1 Market Intelligence Engine

**Purpose:** Build the canonical view of what has happened and what the current market state is.

Inputs:

- Protocol accounts and reserve state.
- Successful and failed transactions, instruction order and inner instructions.
- Swaps, liquidity additions/removals, migration and fee events.
- Token and quote-token balances.
- LP ownership and lock/withdrawability state.
- Price, volume, executable depth and venue data.
- Wallet labels with provenance and confidence.
- External reference prices and executable venue depth, where available.

Outputs:

- Versioned market-state snapshots.
- Canonical event timeline.
- Data-quality and source-completeness indicators.
- Observed facts separated from inferred participant intent.

A wallet's role is not ground truth merely because a heuristic labels it as a sniper, whale, arbitrageur, or retail trader. Store role probabilities, evidence, and confidence.

### 3.2 Flow Intelligence Engine

**Purpose:** Estimate who is trading, why flow is changing, and what flow may arrive next.

Participant populations include:

- Dev / treasury.
- Early and late snipers.
- KOL-influenced participants.
- Retail participants with heterogeneous information and risk preferences.
- Whales and concentrated holders.
- Cross-venue arbitrageurs.
- LP providers.
- MEV / adverse-execution actors.

For each participant or cohort, estimate:

- Inventory and cost-basis distribution.
- Activity and holding-time distribution.
- Buy/sell intensity.
- Order-size distribution.
- Sensitivity to momentum, attention, volatility and drawdown.
- Probability of correlated exits under common shocks.
- Confidence and uncertainty of the estimate.

The model must preserve heterogeneous and asynchronous behavior. Participants must not all react to one shared deterministic buy/sell signal.

A candidate stochastic sell-arrival model is:

\[
Pr_i(\text{sell in }\Delta t)=1-e^{-\lambda_i(t)\Delta t}
\]

where \(\lambda_i(t)\) depends on individual inventory, unrealized PnL, holding horizon, volatility, attention, and common market stress. The model must distinguish a participant's decision to sell from the amount it can actually execute without breaching its own constraints.

### 3.3 Market Quality Engine

**Purpose:** Measure the quality of the market as executable outcomes, not just dashboard statistics.

Core measurements:

| Metric | Definition / interpretation |
|---|---|
| Buy-side depth | Quote input executable within a specified upward marginal-price-impact budget |
| Sell-side depth | Token input and net quote proceeds executable within a specified downward impact budget |
| Impact curve | Price impact as a function of order size, including fee effects |
| Execution slippage | Difference between pre-trade reference and realized VWAP |
| Effective spread | Round-trip execution cost relative to a defensible reference price |
| Depth imbalance | Difference between buy-side and sell-side executable depth |
| Price basis | Pool marginal price versus independent executable reference price |
| Flow toxicity | Evidence that incoming flow is systematically adverse to passive liquidity |
| Inventory concentration | Token and LP claims concentrated among wallets or ownership groups |
| Withdrawable liquidity | Liquidity that can actually leave, distinguished from locked/burned/unassigned claims |
| MEV exposure | Estimated adverse execution exposure under the observed transaction-ordering environment |
| Recovery time | Time for price basis and executable depth to recover after a defined shock |

For AMMs, "bid depth" and "ask depth" are derived executable buy/sell curves. They are not literal order-book bids and asks.

Recovery must be decomposed into separate measurements:

1. **Price-basis recovery:** pool price returns toward an independent executable reference.
2. **Depth recovery:** executable buy/sell depth returns toward its pre-shock level.
3. **Flow recovery:** independent two-sided participation resumes.
4. **Inventory recovery:** the market-making inventory returns to an acceptable risk range.

A price bounce alone is not proof of a healthy recovery.

### 3.4 Inventory Engine

**Purpose:** Manage the system's Token and quote-asset inventory, including ownership, location, cost basis, and risk.

Track separately:

- Free Token inventory.
- Free SOL / quote inventory.
- Token and quote assets deposited into each LP position.
- Current pro-rata LP claims and withdrawable amounts.
- Locked or burned LP claims.
- Treasury allocations, vesting and disclosed sale schedules.
- Realized and unrealized PnL by inventory bucket.
- Inventory acquired through actual swaps versus inventory received through launch/migration accounting.

Do not double-count LP underlying assets and the wallet's LP claim as two independent holdings.

The engine should estimate inventory risk under price, liquidity, and flow scenarios. It should support inventory caps, target ranges, and controlled rebalancing. A treasury holding is not automatically market-making inventory; ownership, mandate, and disclosure must be explicit.

### 3.5 Liquidity Engine

**Purpose:** Manage the size, timing and risk of liquidity committed to the fixed PumpSwap CPMM pool.

**Core policy decision:** The initial product uses a fixed pool and proportional liquidity additions/removals. It does not dynamically migrate liquidity across DLMM bins or CLMM ticks, and it does not chase price by repeatedly changing LP positions.

Responsibilities:

- Validate the Pump.fun bonding-curve state and graduation/migration accounting.
- Calculate initial pool funding from executable-depth requirements, authorized capital and inventory constraints.
- Calculate proportional add/remove amounts against the current CPMM reserve ratio.
- Evaluate ADD / HOLD / REMOVE proposals using expected real flow, fee economics, inventory exposure and risk budgets.
- Track LP ownership, underlying Token/SOL claims, withdrawability, fees and committed capital.
- Reconcile every confirmed liquidity instruction against pool reserves and the Dev's LP claim.
- Keep free inventory, LP underlying assets and treasury holdings in separate accounting buckets.

For an ideal fee-free CPMM with Token reserve X and quote reserve Y, a proportional addition satisfies:

\[
\frac{\Delta Y}{\Delta X}=\frac{Y}{X}
\]

and therefore:

\[
P'=\frac{Y+\Delta Y}{X+\Delta X}=\frac{Y}{X}=P
\]

A proportional addition increases depth without changing the spot-price ratio. A proportional removal reduces depth without changing the spot-price ratio. Actual execution must account for protocol fees, token transfer behavior, rounding, account state and instruction version.

The amount of liquidity is selected from executable-depth targets and stress scenarios. It is not selected to force a price path, smooth candles, or create artificial demand.

**Out of current core scope:**

- Dynamic DLMM Bin migration.
- Dynamic CLMM Tick/range migration.
- Price-following LP repositioning.
- Repeated range shifting as a substitute for inventory management.

These are not required for the fixed-pool Dev market-making design. Future protocol integrations require a separate product decision and research specification.

### 3.6 Execution Engine

**Purpose:** Execute permitted inventory and liquidity actions with controlled cost and reliable transaction handling.

Responsibilities:

- Select supported instruction paths and venue adapters.
- Estimate price impact, fees, priority fees, rent, and failure probability.
- Apply transaction-size and slippage limits.
- Schedule or split legitimate inventory rebalances when doing so improves execution.
- Monitor confirmation, retries, idempotency and reconciliation.
- Protect against stale state and transaction-ordering risk.
- Record intended action, submitted transaction, confirmed result and realized outcome separately.

Execution policy must not seek to create artificial candle shapes, fake volume, or deceptive price signals. A trade is justified by a legitimate inventory, liquidity, or execution objective and is recorded as such.

### 3.7 Risk Engine

**Purpose:** Enforce portfolio, liquidity, protocol, execution and integrity constraints. It has final veto authority.

Risk domains:

- Token and quote inventory limits.
- Treasury concentration and vesting exposure.
- LP withdrawal and liquidity concentration risk.
- Maximum price impact and slippage.
- Drawdown and tail loss.
- Correlated participant exits.
- External-reference and venue basis risk.
- Protocol version, instruction and token-extension risk.
- RPC/indexer incompleteness and stale state.
- Failed transactions, priority-fee spikes and MEV exposure.
- Market-integrity violations.

Risk actions can include reducing action size, pausing new liquidity, pausing rebalances, requiring a fresh state snapshot, or moving to observation-only mode. Risk controls must be deterministic, auditable and testable.

### 3.8 Simulation & Optimization Engine

**Purpose:** Evaluate policies before they can affect a real market.

Capabilities:

- Stochastic agent-based simulation.
- Deterministic event replay.
- Counterfactual policy evaluation.
- Monte Carlo and parameter sweeps.
- Historical cohort calibration and held-out validation.
- Stress tests for correlated selling, liquidity withdrawal, attention decay, external-price shocks and execution failures.
- Policy comparison under identical market paths and random seeds.
- Uncertainty intervals and tail-risk reporting.

The simulation must not optimize a single attractive price path. It should compare distributions across many independent seeds and held-out launches.

---

## 4. Shared state and closed-loop decision architecture

All engines consume one canonical market state. The system uses a proposal-and-arbitration model rather than allowing each agent to act independently.

### 4.1 State vector

A proposed high-level state is:

\[
S_t=(R_t,I_t,L_t,F_t,V_t,C_t,A_t,B_t,Q_t)
\]

where:

- \(R_t\): protocol reserves and pool/curve state.
- \(I_t\): Token and quote inventory by owner and location.
- \(L_t\): liquidity positions, bins/ranges, LP ownership and withdrawability.
- \(F_t\): observed and estimated participant flow.
- \(V_t\): volatility and regime state.
- \(C_t\): holder and LP concentration.
- \(A_t\): attention and sentiment estimates, with confidence.
- \(B_t\): pool/reference price basis and venue state.
- \(Q_t\): data quality, source completeness and state freshness.

### 4.2 Action vector

A proposed action vector is:

\[
U_t=(u_L,u_I,u_E,u_P,u_R)
\]

where:

- \(u_L\): liquidity allocation or withdrawal proposal.
- \(u_I\): inventory rebalance proposal.
- \(u_E\): execution parameters and scheduling.
- \(u_P\): protocol/venue selection and position parameters.
- \(u_R\): risk limits, pause and mode changes.

The market evolves according to:

\[
S_{t+1}=f(S_t,U_t,W_t,\epsilon_t)
\]

where \(W_t\) represents external participant behavior and \(\epsilon_t\) represents stochastic shocks, latency and execution uncertainty.

### 4.3 Decision cycle

1. Ingest confirmed events and update the canonical state.
2. Validate freshness, completeness and protocol-version assumptions.
3. Estimate participant flow and market regime.
4. Calculate market-quality and inventory-risk metrics.
5. Engines propose candidate actions with expected benefits, costs and uncertainty.
6. Risk Engine rejects any action that breaches a hard constraint.
7. Decision orchestrator selects among remaining actions.
8. Execution Engine acts only within its granted permissions.
9. Reconcile confirmed results against the expected state transition.
10. Record outcome and feed it into simulation/calibration.

No action should be based on an unconfirmed or stale state when the action could materially change inventory or liquidity risk.

---

## 5. Market-making objective and capital allocation

The system is a multi-objective controller. It should not maximize fee income or chart smoothness in isolation.

A candidate objective is:

\[
\max_{\pi}
\quad
\mathbb{E}[\Pi_{\mathrm{MM}}]
+\eta\,\mathbb{E}[MQ]
-\lambda\,CVaR_{\alpha}(L)
-\gamma\,C_{\mathrm{capital}}
\]

where:

- \(\Pi_{\mathrm{MM}}\): realized market-making PnL, including fees and execution PnL, net of transaction costs and inventory mark-to-market.
- \(MQ\): normalized market-quality vector or score.
- \(CVaR_{\alpha}(L)\): tail loss at confidence level \(\alpha\).
- \(C_{\mathrm{capital}}\): capital lock-up and opportunity cost.
- \(\eta,\lambda,\gamma\): policy weights selected and validated by experiment.

The market-quality term must not reward fake volume or artificial price movement. It should reward measurable executable depth, execution quality, resilient liquidity, transparent participation and reliable data.

### 5.1 Capital buckets

The capital allocator should distinguish:

1. **Operating inventory:** free Token and quote inventory available for legitimate rebalancing.
2. **Committed LP capital:** assets currently deployed in LP positions.
3. **Liquidity reserve:** uncommitted capital reserved for future liquidity actions or stress.
4. **Execution reserve:** fees, priority fees, rent and transaction-failure budget.
5. **Treasury / protected capital:** capital outside the market-making mandate.

These buckets are accounting and mandate categories. The same underlying asset must never be counted twice. LP capital is valued using the current withdrawable claim, not by adding the claim on top of the pool's assets.

### 5.2 Allocation constraints

For total authorized capital \(K\), proposed allocation \(k_j\) must satisfy:

\[
\sum_j k_j \leq K
\]

Subject to:

\[
\begin{aligned}
D_{\mathrm{buy}}(\delta)&\geq D_{\mathrm{buy}}^{min}\\
D_{\mathrm{sell}}(\delta)&\geq D_{\mathrm{sell}}^{min}\\
Impact(q)&\leq Impact^{max}\\
Risk_{\mathrm{inventory}}&\leq B_{\mathrm{inventory}}\\
Risk_{\mathrm{liquidity}}&\leq B_{\mathrm{liquidity}}\\
CVaR_{\alpha}(L)&\leq B_{\mathrm{tail}}
\end{aligned}
\]

These are policy constraints, not universal numeric constants. Thresholds must be selected for the token, venue, market phase and authorized capital, then validated under stress scenarios.

### 5.3 Key unresolved research question

The next mathematical workstream is **Optimal Market-Making Capital Allocation**:

Given finite authorized capital, how should the system allocate funds among free inventory, LP positions, liquidity reserves and execution reserves as market state changes?

This requires joint optimization of:

- expected fee income;
- inventory drift and adverse selection;
- buy/sell depth targets;
- capital lock-up;
- rebalance cost;
- correlated sell pressure;
- LP withdrawal risk;
- tail loss.

Perpetual futures and options hedging are out of scope. The research must focus on spot inventory, liquidity distribution, active LP changes, and controlled one-sided inventory transitions.

---

## 6. Market-quality metrics and interpretation

### 6.1 Depth and impact

For each venue, calculate executable buy and sell depth at multiple marginal-price-impact budgets (for example 1%, 5%, 10%). Use actual fee-aware venue mechanics.

For a fee-free constant-product pool with token reserve \(X\), quote reserve \(Y\), and \(P=Y/X\), a token sell of \(\Delta X\) gives:

\[
\frac{P'}{P}=\left(\frac{X}{X+\Delta X}\right)^2
\]

This is a useful analytical baseline only. Production analytics must use the actual venue's fee split, effective reserves, token transfer behavior and instruction version. For PumpSwap, raw quote-vault balance and signed virtual quote reserve must remain separately observable; do not mistake raw vault balance for effective pricing liquidity.

### 6.2 Price definitions

Always keep these distinct:

- **Pre-trade marginal spot:** pool marginal price before a swap.
- **Execution/VWAP price:** actual quote/token exchanged for the swap.
- **Post-trade marginal spot:** pool marginal price after the swap.
- **External executable reference:** price and depth available on another venue after its fees and impact.

Do not treat a chart close, aggregator mid-price, or last trade as a guaranteed executable reference.

### 6.3 Recovery metrics

After a defined shock, measure price-basis recovery and depth recovery independently. A market may recover its quoted price while remaining too thin to absorb normal orders. It may also regain depth without returning to its prior price.

### 6.4 Candle integrity

Candles are derived from successful, genuine swaps using execution prices and actual timestamps. LP additions/removals do not create trade volume. Feed delays, dropped events and duplicate deliveries belong in the observed-data layer and must never be confused with additional true executions.

The system may improve the conditions under which genuine trades execute, but it must not manufacture OHLC values or volume to make a chart appear healthy.

---

## 7. Market influence versus market integrity

The system can materially influence market conditions through legitimate controls:

- selecting the amount and location of committed liquidity;
- selecting supported DLMM bins or CLMM ranges;
- managing free Token and quote inventory;
- rebalancing inventory within explicit risk limits;
- selecting execution size and timing to reduce avoidable slippage;
- pausing actions when state is stale or risk is excessive.

However, influence is not the same as deterministic control over a market price or candle.

Important venue distinctions:

- In a CPMM, a proportional LP add/remove changes pool depth but preserves the spot-price ratio. Swaps move the price.
- In a DLMM, liquidity can be distributed across bins, shaping where executable liquidity is available. It is not a promise that an external trader will trade at a chosen price.
- In a CLMM, liquidity is active only in the configured price range and changes inventory exposure as price moves.
- A market maker cannot guarantee that external traders will provide demand, that arbitrage capital will appear, or that a price will recover.

The product should optimize real market quality, not visual appearance. It must never use self-trading, wash trading, fabricated volume, hidden coordinated wallets, or deceptive order/price behavior to simulate independent demand.

---

## 8. Roles, permissions and observability

The target system separates policy from execution.

| Component | May observe | May propose | May execute |
|---|---:|---:|---:|
| Intelligence | Yes | No | No |
| Flow Intelligence | Yes | No | No |
| Market Quality | Yes | No | No |
| Inventory | Yes | Inventory actions | No |
| Liquidity | Yes | LP actions | No |
| Execution | Yes | Execution plan | Only granted actions |
| Risk | Yes | Pause/limit | Veto and enforce limits |
| Simulation & Optimization | Historical/simulated | Policy candidates | No live execution |

Every action record should include:

- market-state snapshot ID and timestamp;
- data-quality status;
- triggering condition;
- proposed action and alternatives;
- expected impact, fees, capital usage and risk;
- risk approval or rejection reason;
- transaction signature if submitted;
- confirmed state change;
- realized outcome and attribution.

---

## 9. Research and validation roadmap

The system should be developed in the following order.

### R01 — Market state and accounting contract

- Canonical state schema for curve, pool, wallet inventory, LP positions and external venues.
- Separate facts, estimates and unknowns.
- No double-counting of LP claims or token supply buckets.
- Protocol/version-aware reserve semantics.

### R02 — Market-quality measurement

- Fee-aware buy/sell depth curves.
- Execution/VWAP versus marginal spot.
- Effective spread and price basis.
- Depth imbalance and withdrawable-liquidity concentration.
- Price-basis and depth recovery time.

### R03 — Participant-flow model

- Heterogeneous asynchronous participants.
- Role distributions rather than deterministic personas.
- Correlated exits and common information shocks.
- Observable behavior separated from inferred intent.
- Calibration on multiple launches and held-out samples.

### R04 — Inventory and capital allocation

- Dev/treasury exposure accounting.
- Free inventory versus LP claims.
- Target inventory bands and rebalance costs.
- Capital allocation under depth and tail-risk constraints.
- No derivative hedges.

### R05 — Liquidity policy

- CPMM, DLMM and CLMM adapters.
- Range/bin allocation and inventory transition.
- Add/remove/hold policy.
- Fee income versus adverse selection and capital lock-up.
- Stress tests for sudden withdrawals and one-sided flow.

### R06 — Execution and risk arbitration

- Proposal-and-arbitration architecture.
- Stale-state protection and transaction reconciliation.
- Slippage, priority-fee and failure budgets.
- Risk veto and observation-only mode.
- Audit trail and permissions.

### R07 — Simulation and empirical validation

- Historical replay and event-level reconciliation.
- Matched-seed counterfactual policy tests.
- Monte Carlo distributions and tail-risk reports.
- Held-out launch validation.
- Paper execution before any separately authorized live deployment.

### Acceptance principles

A research result is not accepted because one chart looks better. It must:

1. Preserve supply, reserve, inventory and LP accounting invariants.
2. Use protocol-accurate fees and executable depth.
3. Distinguish true trades from LP and feed events.
4. Compare multiple random seeds and market regimes.
5. Report median and tail outcomes, not only averages.
6. Include transaction costs, capital lock-up and inventory mark-to-market.
7. Show that market-quality improvements do not depend on fabricated volume or deceptive activity.
8. Clearly state what is measured, inferred, simulated or still unknown.

---

## 10. Current status and next decision

**Direction locked:** Build a complete Market Making & Market Quality System, not a standalone LP Manager.

**Initial market scope locked:** Pump.fun Bonding Curve → graduation → PumpSwap CPMM fixed pool. LP policy is initial funding plus proportional ADD / HOLD / REMOVE. Dynamic DLMM Bin and CLMM Tick positioning is not part of the current core design.

**Existing research foundation in this repository:**

- R01 tokenomics and supply accounting.
- R02 bonding-curve mathematics and execution.
- R03 pool microstructure, fee-aware depth, LP accounting and candle diagnostics.
- Technical R04 historical event replay and calibration.
- Agent-based stochastic participant simulation.
- Empirical calibration data contract.
- Initial capital-allocation, inventory-risk and multi-timescale control derivations in the product research discussion.

**Not yet complete:** A canonical state contract, calibrated optimal capital allocator, executable decision orchestrator, complete conflict-resolution policy, and held-out empirical validation across real historical cohorts.

**Next workstream:** Formalize the Market Making Decision Orchestrator and its risk-priority hierarchy, then implement the fixed-CPMM action evaluator. The orchestrator must compare HOLD, proportional ADD, proportional REMOVE and PAUSE under identical scenarios; hard safety and capital constraints must never be traded away for a market-quality score. Do not begin live execution until accounting, replay, simulation, risk controls and paper validation pass their acceptance gates.

---

## 11. Decision log

| Decision | Status |
|---|---|
| Product is a complete Market Making & Market Quality System | Locked |
| LP Manager is only one subsystem | Locked |
| Initial market scope is Pump.fun Bonding Curve → PumpSwap CPMM | Locked |
| Fixed pool with proportional LP additions/removals | Locked |
| Dynamic DLMM Bin / CLMM Tick positioning is out of current core scope | Locked |
| Full lifecycle from launch through mature/stress market | Locked |
| Shared state and centralized decision arbitration | Locked |
| Eight engines defined by responsibility | Proposed architecture |
| Spot inventory and dynamic capital allocation are primary tools | Locked |
| Perpetual futures and options hedging are excluded | Locked |
| Market quality is not equivalent to low volatility or smooth candles | Locked |
| True volume must come only from genuine successful swaps | Locked |
| Risk and integrity constraints have veto priority over quality and return objectives | Locked |
| LP action policy is proportional ADD / HOLD / REMOVE / PAUSE | Proposed policy |
| Next research priority is the Market Making Decision Orchestrator | Locked |

---


## 12. Market Making Decision Orchestrator

### 12.1 Purpose

The Market Making Decision Orchestrator (MDO) is the single policy arbitration layer for the system. It is not another independent trading agent and it does not replace the specialist engines. Specialist engines observe, estimate, measure or propose; the orchestrator selects one coherent action under a shared objective and hard constraints.

No specialist engine may independently authorize or submit a transaction.

### 12.2 Standard proposal contract

Every specialist proposal must use a common structure:

| Field | Meaning |
|---|---|
| State version | Exact canonical market-state snapshot used |
| Proposal type | ADD, HOLD, REMOVE, PAUSE, inventory action or no-op |
| Amount | SOL-equivalent capital or LP fraction, where relevant |
| Horizon | Period over which the proposal is evaluated |
| Trigger evidence | Observed events and metrics that caused the proposal |
| Expected effects | Change in depth, inventory, Delta/Gamma, fees and capital lock-up |
| Cost estimate | Swap, LP instruction, priority fee, rent, slippage and opportunity cost |
| Risk estimate | Scenario loss, CVaR, reserve impact and protocol exposure |
| Confidence | Forecast confidence and data-quality status |
| Expiry | Time or state change after which the proposal is invalid |

A proposal is not an execution instruction. The orchestrator must recompute its effects against the latest canonical state before approval.

### 12.3 Decision authority

| Layer | Responsibility | Authority |
|---|---|---|
| Market Intelligence | Confirmed facts, account state and event reconciliation | Publish canonical state; no trading authority |
| Flow Intelligence | Participant-flow estimates and scenario probabilities | Propose forecasts; no trading authority |
| Market Quality | Depth, impact, basis and recovery measurements | Propose service gaps; no trading authority |
| Inventory | Portfolio inventory, Delta/Gamma and stress exposure | Propose inventory limits/actions |
| Liquidity | PumpSwap proportional ADD/REMOVE calculations | Propose LP actions; no transaction authority |
| Execution | Build, simulate, submit and reconcile permitted instructions | Execute only an approved, unexpired action |
| Risk | Hard constraints, protocol safety and integrity checks | Veto, cap or pause |
| Orchestrator | Compare all proposals under one state and objective | Select one coherent action |

Risk has veto authority, not an independent mandate to trade. Execution has transaction capability, not policy authority.

### 12.4 Lexicographic priority hierarchy

The system must not use a single weighted score to trade safety against market quality. Decision priority is hierarchical:

**Priority 0 — Integrity and state validity (hard gate)**

- Confirmed protocol state and supported instruction version.
- Fresh, complete enough data for the proposed action.
- No duplicate or unresolved conflicting transaction.
- No self-trading, wash trading, fabricated volume, deceptive coordination or price/candle manipulation.
- Correct ownership, authorization and capital mandate.

If this gate fails, no new discretionary liquidity or inventory action is approved. The system enters a safe observation or pause mode. An uncertain state must not trigger an automatic LP withdrawal that could make the situation worse.

**Priority 1 — Capital and risk constraints (hard gate)**

- Authorized capital is not exceeded.
- Minimum execution and liquidity reserves are preserved.
- Inventory stress loss remains within the approved budget.
- LP exposure and concentration remain within limits.
- Transaction size, slippage and protocol-risk limits are respected.
- No action relies on unconfirmed inventory or double-counted LP assets.

A candidate that violates a hard constraint is rejected even if it would improve depth or expected fees.

**Priority 2 — Market-quality service objective**

Within the safe feasible set, evaluate real executable buy/sell depth, price impact, execution reliability and recovery. Depth targets are service objectives derived from observed independent demand and stress distributions, not guarantees and not reasons to breach capital limits.

If available capital cannot satisfy a depth target within risk limits, report the shortfall. Do not manufacture volume or force additional capital into the pool.

**Priority 3 — Risk-adjusted economic value**

Among feasible actions, compare expected net market-making return, inventory risk, capital lock-up, transaction cost and tail loss.

**Priority 4 — Operational stability**

Prefer the least disruptive action when two candidates have materially similar expected value. Account for action churn, cooldown, pending transactions and operational complexity.

### 12.5 Candidate action set

For the initial fixed PumpSwap CPMM design:

\[
A_t=\{HOLD,\ ADD(a),\ REMOVE(r),\ PAUSE\}
\]

where:

- HOLD: make no liquidity change.
- ADD(a): add a proportional amount of liquidity, with a bounded SOL-equivalent budget.
- REMOVE(r): withdraw a proportional fraction of the existing LP claim.
- PAUSE: block new discretionary LP actions while continuing safe observation and reconciliation.

The initial policy does not combine ADD and REMOVE in the same decision cycle. It does not move bins, ticks or price ranges. Inventory actions are evaluated as a separate portfolio decision and must not be disguised as LP operations.

### 12.6 Unified action evaluation

For each candidate action \(a\), simulate the post-action state over a common horizon and common scenario set \(\Omega\):

\[
S_{t+h}^{\omega}=F(S_t,a,\omega),\quad \omega\in\Omega
\]

Calculate:

\[
U(a)=
E[\Pi_{\mathrm{net}}(a)]
-\lambda CVaR_{\alpha}(L(a))
-\kappa C_{\mathrm{switch}}(a)
-\eta_D \xi_D(a)
-\eta_E \xi_E(a)
\]

where:

- \(\Pi_{\mathrm{net}}\): fees and legitimate inventory PnL net of adverse selection, transaction costs and capital cost, with no double counting.
- \(CVaR_{\alpha}\): tail loss under the action.
- \(C_{\mathrm{switch}}\): action churn and operational cost.
- \(\xi_D\): shortfall against the approved executable-depth service target.
- \(\xi_E\): execution-quality shortfall against the approved service target.
- \(\lambda,\kappa,\eta_D,\eta_E\): mandate parameters calibrated through simulation and empirical validation.

Do not reward raw trading volume, price appreciation, candle smoothness or the number of transactions. Market-quality utility is based on executable service and resilience.

Candidate actions must first pass all hard gates. The utility function only ranks feasible actions; it cannot override a veto.

### 12.7 Hard constraints

A candidate action is feasible only if all applicable constraints hold after the action and under required stress scenarios:

\[
K_I+K_L+K_R+K_E\leq K_{\mathrm{authorized}}
\]

\[
K_R\geq K_R^{min},\qquad K_E\geq K_E^{min}
\]

\[
\max_{\omega\in\Omega_{stress}}L_{\mathrm{inventory}}^\omega(a)
\leq B_I
\]

\[
CVaR_{\alpha}(L(a))\leq B_{\mathrm{tail}}
\]

\[
Impact(q;S_{t+h}^{\omega})\leq Impact^{max}
\]

In addition:

- Data freshness and completeness must exceed action-specific minimums.
- LP position and pool reserves must reconcile.
- A pending LP instruction must be resolved before another conflicting LP action.
- The post-action state must preserve the minimum authorized capital reserve.
- The transaction must pass simulation and instruction-level validation.

Depth targets may be unmet if no safe feasible action can satisfy them. The orchestrator must report this explicitly rather than silently relaxing a risk limit.

### 12.8 Conflict-resolution examples

| Conflict | Orchestrator decision |
|---|---|
| Market Quality requests ADD, but inventory stress limit would be breached | Reject ADD; report depth shortfall and inventory constraint |
| Flow model predicts heavy selling, but data is stale | Do not act on the forecast; enter degraded-data mode and refresh state |
| Fee APR is high, but expected adverse selection/LVR exceeds fee income | Do not add LP |
| Current depth is adequate, but fee income is positive | Do not add solely because fees are positive; compare marginal net return and capital cost |
| LP withdrawal reduces future LP exposure but releases Token into free inventory | Recompute total portfolio risk before approving REMOVE |
| Protocol or transaction state is uncertain | Pause discretionary actions; reconcile before resuming |
| Emergency risk condition occurs during cooldown | Safety pause may override cooldown; no automatic price-directed trade |

### 12.9 Operating modes

The orchestrator maintains an explicit system mode:

| Mode | Entry condition | Permitted behavior |
|---|---|---|
| NORMAL | Data and protocol state valid; risk within limits | Evaluate HOLD / ADD / REMOVE |
| DEGRADED_DATA | Stale, incomplete or conflicting observations | Observe, reconcile and block discretionary actions |
| INVENTORY_DEFENSE | Inventory approaches or exceeds warning band | Block risk-increasing actions; evaluate independent risk-reduction options |
| CAPITAL_CONSERVATION | Reserve or tail-risk budget approaches limit | Block discretionary capital deployment |
| EMERGENCY_PAUSE | Protocol, authorization or critical safety failure | Stop new discretionary execution and reconcile exposure |
| RECOVERY | Failure condition resolved but stability not yet demonstrated | Resume gradually after validation and dwell period |

Mode transitions use separate entry and exit thresholds to prevent oscillation. Recovery requires fresh state, reconciled transactions and a stable observation period.

### 12.10 Transaction lifecycle and state consistency

Every approved action must be bound to:

- canonical state version;
- action ID and idempotency key;
- maximum amount and slippage;
- expiry condition;
- risk approval;
- exact instruction parameters.

Execution sequence:

1. Orchestrator approves a bounded action.
2. Execution rechecks the state version and account balances.
3. Transaction is simulated and validated.
4. Transaction is submitted once using an idempotency key.
5. Confirmation and finality are observed.
6. Pool reserves, LP claims and wallet balances are reconciled.
7. Only then is the canonical state advanced and the action marked complete.

If state changes materially before submission, the approval expires and must be recomputed. A failed or unresolved transaction must not be treated as a completed state transition.

### 12.11 Required decision output

Every decision cycle must produce an auditable record:

- current mode and state version;
- candidate actions considered;
- proposals accepted and rejected;
- hard-gate results and veto reasons;
- scenario assumptions and forecast confidence;
- expected depth and execution-quality changes;
- expected net return, tail risk and capital usage;
- selected action or explicit NO_ACTION;
- post-action reconciliation and realized outcome.

A valid decision may be NO_ACTION. The system must not invent an action simply because an evaluation cycle ran.

---

## 13. Multi-timescale control policy

### 13.1 Control layers

| Layer | Initial cadence | Primary responsibility | Transaction authority |
|---|---|---|---|
| L0 — Event safety | Event-driven; seconds-scale observation | Confirm swaps, reserves, transaction status, protocol and data anomalies | May trigger a safety pause; no discretionary LP sizing |
| L1 — Inventory and flow | Rolling minutes-scale | Aggregate flow, update inventory exposure, forecast uncertainty and risk bands | Propose inventory/risk changes; no independent LP transaction |
| L2 — Liquidity and capital | Periodic hours-scale evaluation plus risk-triggered re-evaluation | Evaluate proportional ADD / HOLD / REMOVE and reserve allocation | Orchestrator approval required |
| L3 — Lifecycle capital | Launch, graduation and material mandate changes | Set authorized capital, initial supply/accounting policy, initial LP budget and phase limits | Requires explicit capital authorization |

Cadences are initial design windows, not hard-coded universal constants. Calibration must account for block time, event rate, pool liquidity, transaction latency and observed market regime.

### 13.2 Event-driven safety versus periodic strategy

L0 is event-driven because protocol and transaction safety cannot wait for an hourly evaluation. However, an event does not automatically authorize a liquidity action.

L1 updates flow and inventory estimates on rolling windows. It may request an immediate L2 re-evaluation when a hard risk boundary or a material state change occurs.

L2 performs slower capital decisions. It should not resize LP merely because one swap changed the spot price.

L3 changes only when lifecycle conditions or explicit capital authorization change. It must not chase short-term price movement.

### 13.3 Hysteresis, persistence and cooldown

For any discretionary action trigger, define:

- Entry threshold \(\theta_{on}\).
- Exit threshold \(\theta_{off}\), with \(\theta_{off}<\theta_{on}\).
- Persistence window \(T_{persist}\).
- Cooldown \(T_{cooldown}\).
- Emergency override conditions.

A trigger is eligible only when the condition persists for the required observation window and the data-quality gate passes.

Cooldown reduces repeated discretionary changes. It must never block a safety pause or required reconciliation. Cooldown expiry does not imply that an action should occur; the full decision must be recomputed.

### 13.4 Forecast uncertainty

For a predicted flow quantity \(Q_{pred}\) and forecast residual distribution \(\epsilon_Q\), construct scenario demand from the empirical residual distribution:

\[
Q_{stress}=Q_{pred}+Quantile_{\alpha}(\epsilon_Q)
\]

Do not assume normal residuals without evidence. Meme-token flows may be heavy-tailed, clustered and regime-dependent. Calibrate uncertainty by token cohort, lifecycle phase and forecast horizon, and preserve an explicit unknown/low-confidence state.

### 13.5 Shared state, different aggregation windows

All layers use the same canonical event ledger and state version. They may derive different rolling windows, but must not maintain contradictory copies of balances or LP claims.

- L0 consumes confirmed events and protocol account updates.
- L1 aggregates event flow and inventory over rolling windows.
- L2 consumes L1 forecasts plus current executable depth and capital constraints.
- L3 supplies authorization and lifecycle policy bounds.

Every derived metric records its source window, timestamp, state version and confidence.

### 13.6 Multi-timescale acceptance tests

- A single large swap does not automatically trigger an LP resize.
- Persistent depth shortfall can request an L2 evaluation.
- An inventory hard-limit breach blocks risk-increasing LP actions.
- A stale or conflicting state blocks discretionary actions.
- Emergency pause overrides cooldown.
- A pending LP transaction prevents a conflicting second transaction.
- L2 cannot exceed L3 authorized capital.
- L0 event reconciliation and L1/L2 aggregates agree on balances and event counts.
- Replaying the same event sequence and policy version produces the same decision, except where explicitly modeled stochastic inputs differ.

---

## 14. Next research sequence

The next derivations and implementation work should follow this dependency order:

1. **Canonical state and accounting contract:** define exact Pump.fun curve, PumpSwap reserve, LP claim, free inventory and treasury fields.
2. **Fixed-CPMM action transition model:** calculate exact post-action state for proportional ADD / REMOVE, including protocol fees, rounding and account semantics.
3. **Inventory conversion policy:** compare HOLD, LP withdrawal and independently authorized spot inventory reduction without double-counting assets or assuming that withdrawal removes Token exposure.
4. **Capital allocator:** solve for free inventory, LP capital, liquidity reserve and execution reserve under stress constraints.
5. **Decision orchestrator:** implement proposal contract, hard-gate hierarchy, action scoring, state machine and audit record.
6. **Multi-timescale replay:** test event-driven safety, rolling flow estimates, cooldown and lifecycle authorization against historical sequences.
7. **Paper validation:** run matched-seed simulations and historical replay; report net PnL, tail loss, depth service, action count, failed transactions and inventory paths.

No live execution should be enabled merely because the orchestrator can produce an action. Accounting, protocol adapters, replay, simulation, risk controls and paper validation must pass independently.

