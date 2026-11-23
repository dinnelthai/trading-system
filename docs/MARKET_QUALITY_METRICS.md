# R08–R19 — Market Quality Metrics, Risk, Lifecycle and Validation

**Document type:** Integrated mathematical and implementation specification  
**Version:** 0.1  
**Status:** Theoretical specification drafted; empirical calibration and implementation remain open  
**Scope:** Pump.fun Bonding Curve → graduation → fixed PumpSwap CPMM; genuine independent participation; spot inventory and proportional LP actions  
**Parent:** [Market Making & Market Quality System](MARKET_MAKING_MARKET_QUALITY.md)  
**Related:** [Pool Microstructure](POOL_MICROSTRUCTURE.md), [Pool Depth Elasticity](DEPTH_ELASTICITY.md), [Dev LP vs Treasury Allocation](DEV_LP_TREASURY_ALLOCATION.md), [Decision Orchestrator](DECISION_ORCHESTRATOR.md), [Dev Treasury & Exit Intelligence](DEV_TREASURY_EXIT.md)

> This document specifies a transparent market-quality and risk-control system. It does not authorize self-trading, wash trading, fabricated volume, artificial candle shaping, deceptive coordination, concealed beneficial ownership, or manipulation of reference prices. Only confirmed genuine swaps are market volume. LP deposits, withdrawals, transfers, failed transactions and feed duplicates are not swaps.

---

## 0. What is and is not being solved

R01–R07 establish tokenomics, bonding-curve execution, pool microstructure, participant simulation, capital allocation, execution/risk arbitration and validation foundations. R08–R19 close the remaining mathematical specification for market quality, inventory, price discovery, resilience, adverse selection, fairness, integrity, sustainability, control, participant behavior, lifecycle and empirical acceptance.

The system has three distinct objectives that must not be conflated:

1. **Market objective:** maintain transparent, executable and resilient liquidity for genuine independent traders.
2. **Owner objective:** maximize risk-adjusted net asset value under disclosed capital, inventory and operating constraints.
3. **Research objective:** identify causal effects using calibrated data, matched counterfactuals and held-out launches.

A higher owner return is not proof of better market quality. A larger TVL is not proof of better execution. Higher recorded volume is not proof of greater independent demand. A smooth candle is not proof of price efficiency.

## R08 — Unified Market Quality Objective

### 8.1 Quality vector

Use a vector rather than treating one scalar as the truth:

\[
MQ_t=(L_t,E_t,P_t,R_t,F_t,I_t,S_t)
\]

where:

- \(L\): two-sided executable liquidity;
- \(E\): execution quality;
- \(P\): price discovery against independent executable references;
- \(R\): resilience after genuine shocks;
- \(F\): fairness for comparable order intents;
- \(I\): data and market integrity;
- \(S\): liquidity sustainability.

Inventory health, Treasury exit quality and owner PnL are reported in the risk/owner ledger. They influence feasible actions, but must not be allowed to disguise poor execution for external traders.

### 8.2 Hard gates precede any score

The following are non-compensable constraints:

\[
\begin{aligned}
D_{buy}(\delta)&\ge D_{buy}^{min}(\delta)\\
D_{sell}(\delta)&\ge D_{sell}^{min}(\delta)\\
C_{exec,p95}(Q_k)&\le C_k^{max}\\
|b_t|_{p95}&\le b^{max}\quad\text{when reference data is valid}\\
T_{recovery,p95}&\le T^{max}\quad\text{for calibrated shock classes}\\
Completeness&\ge C^{min}\\
IntegrityViolations&=0
\end{aligned}
\]

Thresholds are launch-stage and market-regime specific. They must be estimated from real user order sizes, actual pool fees, protocol behavior and independent reference data. Do not invent universal thresholds.

If a hard gate fails, status is **DEGRADED** or **PAUSED**; a high score elsewhere cannot cancel the failure.

### 8.3 Normalization and optional dashboard score

For a higher-is-better metric \(x\):

\[
q(x)=\operatorname{clip}\left(
\frac{x-x_{bad}}{x_{good}-x_{bad}},0,1
\right)
\]

For a lower-is-better metric:

\[
q(x)=\operatorname{clip}\left(
\frac{x_{bad}-x}{x_{bad}-x_{good}},0,1
\right)
\]

Only after all hard gates pass may a diagnostic geometric score be displayed:

\[
MQS=100\prod_j q_j^{w_j},
\qquad w_j\ge0,\quad \sum_jw_j=1
\]

The dashboard must show all seven components, confidence intervals and missing-data flags beside MQS. If a required component is missing or the reference is invalid, mark MQS unavailable rather than imputing a score. The score is for comparison, not a standalone control target.

**Never include raw volume, price appreciation, low volatility or candle smoothness as direct positive score terms.** Volume is a diagnostic and a fee input only after independent-trade attribution. Low volatility can reflect a quiet market or stale pricing; high volatility can reflect genuine information.

---

## R09 — Two-Sided Depth, Asymmetry and Inventory

### 9.1 Executable depth

For target marginal price impact \(\delta\), define:

- \(D_b(\delta)\): gross quote input needed to move the pool's marginal price upward by \(\delta\);
- \(D_s(\delta)\): net quote proceeds available from a Token sale that moves the marginal price downward by \(\delta\).

Both must be computed from the version-correct PumpSwap effective reserves and actual fee split. Use the exact swap transition, not a fee-free approximation. R03 currently reports 1%, 5% and 10% depth bands; preserve those bands and add user-size percentiles when real order data is available.

### 9.2 Depth balance is a diagnostic, not an unconditional target

At a common impact budget:

\[
B_\delta=
\frac{2\min(D_b(\delta),D_s(\delta))}
{D_b(\delta)+D_s(\delta)+\varepsilon}
\in[0,1]
\]

\[
A_\delta=
\ln\frac{D_b(\delta)+\varepsilon}
{D_s(\delta)+\varepsilon}
\]

- \(B_\delta=1\) means equal quote-equivalent executable depth.
- \(A_\delta>0\) means buy-side quote capacity is larger.
- \(A_\delta<0\) means sell-side quote capacity is larger.

Do not force \(B_\delta=1\) at all times. A legitimate market can have directional flow and inventory risk. The controller should compare side-specific depth with demand, risk limits and the independent reference, rather than add liquidity merely to make the ratio look symmetric.

### 9.3 Pool reserve exposure versus owner inventory exposure

Pool reserve composition measured against an independent reference price \(P^*\), using redeemable underlying reserves rather than virtual pricing reserves:

\[
I_{pool}=
\frac{P^*X^{redeemable}-Y^{redeemable}}
{P^*X^{redeemable}+Y^{redeemable}}
\]

The effective quote reserve used to calculate PumpSwap spot price and executable depth is a separate protocol-pricing quantity. It must not be treated as an asset balance or LP redemption claim.

where \(X\) is Token reserve and \(Y\) is quote reserve. Positive values mean Token inventory is worth more than quote reserves at the independent reference; negative values mean quote-heavy exposure.

For owner \(o\), beneficial Token exposure must include free and LP-claim inventory without double counting:

\[
H_o^{beneficial}
=H_o^{free}+H_o^{locked}+\alpha_oX
\]

\[
\rho_o^{Token}=
\frac{P^*H_o^{beneficial}}{NLV_o}
\]

where \(\alpha_o\) is the owner's LP-share fraction. Report free, locked and LP-claim exposure separately. Locked assets count as economic risk exposure but are not deployable inventory.

The pool's 50/50 mark-to-market property under a pure CPMM is not a substitute for this beneficial-owner exposure ledger.

### 9.4 Depth persistence

For each side and impact band:

\[
Persistence_{side,\delta}=
\frac{\text{valid observation time with }D_{side}(\delta)\ge D^{min}_{side}(\delta)}
{\text{total valid observation time}}
\]

Report the percentage and the longest continuous breach. Do not hide brief but severe depth gaps inside a daily average.

---

## R10 — Price Discovery and Independent Reference

### 10.1 Independent reference construction

The reference must not be the target pool's own price. For valid independent venues \(v\), construct a robust log-price reference:

\[
\ln P_t^*=
\operatorname{WeightedMedian}
\left(\ln P_{v,t};w_{v,t}\right)
\]

Weights may use executable depth, freshness and data confidence, with a per-venue cap. Exclude stale, non-executable or integrity-flagged observations. If too few independent venues remain, mark the reference as low confidence; do not manufacture a precise benchmark.

The reference adapter must record source venue, timestamp, quote depth, fee assumptions, freshness and exclusion reason.

### 10.2 Basis and tracking error

\[
b_t=\ln\frac{P_{pool,t}}{P_t^*}
\]

Report:

- signed median basis;
- median and p95 absolute basis;
- basis by buy/sell pressure and volatility regime;
- time outside the calibrated no-arbitrage band;
- convergence time after independent reference changes.

A nonzero basis is not automatically an error: fees, latency, route costs and finite external depth create an executable no-arbitrage band. The tolerance band must be derived from actual costs, not set to zero.

### 10.3 Price discovery is not price suppression

The pool must be allowed to move when independent information changes fair value. The target is timely convergence to the current independent reference within executable costs—not reversion to an old price, a preferred price, or a visually smooth trajectory.

Simple price correlation is insufficient. Measure basis, response delay, executable arbitrage capacity and post-trade markouts together.

---

## R11 — Market Impact and Resilience

### 11.1 Separate permanent information from temporary impact

A genuine trade can reveal information and cause a lasting price change. Resilience must not require the market to return to its pre-trade price.

After a valid shock at \(t_0\), use the evolving independent reference \(P^*_{t}\). Measure whether the pool converges to the new reference and whether executable depth remains adequate.

### 11.2 Basis recovery time

Let \(b_t=\ln(P_{pool,t}/P_t^*)\). For tolerance \(\epsilon_b\) and persistence window \(H\):

\[
T_b=\inf\left\{u\ge0:
|b_{t_0+u+s}|\le\epsilon_b,\ \forall s\in[0,H]
\right\}
\]

If no recovery occurs within the observation horizon, record a right-censored observation rather than silently dropping the event.

### 11.3 Depth recovery time

Define \(D^{target,new}_{side,\delta}\) as the minimum depth appropriate to the post-shock reference price, market regime and risk mandate. It is not automatically the pre-shock numeric depth.

\[
T_D=\inf\left\{u\ge0:
D_{side,\delta}(t_0+u+s)\ge
\theta D^{target,new}_{side,\delta},\
\forall s\in[0,H]
\right\}
\]

Compute buy and sell recovery separately.

### 11.4 Joint resilience

\[
T_R=\max(T_b,T_{D,buy},T_{D,sell})
\]

Report the distribution of \(T_R\), not only its mean. Also report maximum basis excursion, minimum depth, failed-order burst, LP withdrawal and the amount of external liquidity replenishment.

Shock classes should come from observed reference jumps, genuine large orders, correlated holder flows, external LP withdrawals and protocol/data outages. Use stochastic or historical shocks, not a hand-authored price path designed to produce a preferred chart.

---

## R12 — Adverse Selection, Markout and LVR

### 12.1 Trade-level markout

For trade \(j\), define:

- \(s_j=+1\) for a trader buy from the pool;
- \(s_j=-1\) for a trader sell into the pool;
- \(P_{exec,j}\): actual execution/VWAP price;
- \(P^*_{t_j+h}\): independent reference price at horizon \(h\).

A positive LP adverse-selection markout is:

\[
A_{j,h}=s_j\ln\frac{P^*_{t_j+h}}{P_{exec,j}}
\]

For a buy, a subsequent rise in fair value means the LP sold too cheaply. For a sell, a subsequent fall means the LP bought too expensively.

Quote-notional weighted adverse markout:

\[
AS_h=
\frac{\sum_jN_j\max(0,A_{j,h})}
{\sum_jN_j}
\]

Also report signed markout so favorable flow is not hidden. Use several horizons appropriate to block time and observed market speed; do not select a single horizon after seeing which one looks favorable.

### 12.2 Fee-adjusted diagnostic

Let \(f_{LP,j}\) be the actual LP-retained fee in quote-equivalent units and \(c_j\) the attributable execution/operational cost:

\[
NetMarkout_{j,h}=
\frac{f_{LP,j}-c_j}{N_j}-A_{j,h}
\]

This is a diagnostic, not a substitute for the exact LP state transition or portfolio NLV. Creator Fee and protocol fees must not be counted as LP-retained fees.

### 12.3 IL and LVR are different benchmarks

- Impermanent loss compares LP inventory with holding the initial asset basket.
- LVR compares passive LP inventory changes with a strategy rebalancing at the independent efficient price.

Do not add IL and LVR as if they were independent realized losses. Use actual LP reserve NLV change for the optimizer. Show IL and LVR as separately labeled benchmark diagnostics. The diffusion \(1/8\) variance approximation is a screening baseline; jumps, stale prices, latency, fee tiers and discrete PumpSwap mechanics require event-driven replay.

A high swap volume can be toxic. The allocator must compare LP fees with markout/adverse selection, LVR, inventory risk, costs and capital lock-up—not volume alone.

---

## R13 — Fairness and Execution Quality

### 13.1 Comparable-intent matching

Fairness does not mean every order pays the same cost. Larger orders naturally have larger AMM impact. Compare orders with similar:

- quote-equivalent size and side;
- pool reserves and fee tier;
- reference basis and volatility;
- network congestion and block inclusion conditions;
- stated priority fee and route;
- quote freshness and submission-to-settlement latency.

For each order, calculate execution residual:

\[
r_j=C^{realized}_j-
\widehat C(Q_j,side_j,state_j,route_j,priority_j)
\]

The model \(\widehat C\) estimates expected cost under comparable conditions. Compare residual distributions across participant cohorts.

### 13.2 Fairness metrics

- matched p50/p95 execution residual by cohort;
- successful settlement rate by cohort;
- quote-to-settlement latency distribution;
- failed/reverted order rate and reason;
- unexplained cost and success-rate gaps after matching.

For cohorts \(a,b\):

\[
Gap_{a,b}=p95(r\mid a)-p95(r\mid b)
\]

Large unexplained gaps trigger investigation, not automatic accusations. Wallet identity must not be used to secretly discriminate. Verified protocol-level priority fees and public execution rules should be visible in the cost attribution.

### 13.3 MEV and sandwich-risk measurement

Treat MEV as a user-execution harm and risk-budget dimension. Record observable sandwich-like transaction patterns and estimate realized execution degradation. The simulator may stress-test generic adverse execution and latency, but this specification does not implement transaction-ordering exploits or instructions for extracting value from users.

---

## R14 — Market Integrity, True Volume and Candle Integrity

### 14.1 Canonical event identity

A swap event is uniquely identified by chain, transaction signature, instruction index and event/log index. The implemented [Canonical Market Event Ledger](MARKET_EVENT_LEDGER.md) deduplicates these identities, supports pending → confirmed → finalized progression and orphaning, and rejects conflicting payloads. Its default accepted-volume threshold is FINALIZED; CONFIRMED can be selected explicitly.

A true swap record includes:

- confirmed input/output mint and amount;
- quote-equivalent notional using actual execution amounts;
- trader and beneficial-owner attribution confidence;
- fee components and fee schedule version;
- execution/VWAP price;
- slot, timestamp and finality state.

### 14.2 Volume definition

\[
V^{true}_{quote}=\sum_{j\in confirmed\ swaps}N_{j,quote}
\]

Exclude:
- LP additions and withdrawals;
- wallet transfers;
- mint/burn events not representing a swap;
- failed/reverted transactions;
- duplicate feed events;
- internal accounting movements;
- unconfirmed or orphaned events.

True OHLCV is built from accepted unique swap executions. The event contract requires an explicit quote-notional basis (POOL_GROSS, USER_PAID or USER_RECEIVED); different bases are never mixed. Candle price is execution quote notional divided by base amount, not post-swap marginal spot. Buy/sell quote volume and counts are reported separately. The observed feed is a separate projection with explicit delay, drop, duplicate and completeness diagnostics. Raw transaction decoding, RPC ingestion and decoder-completeness proof remain open.

### 14.3 Beneficial-owner attribution

Classify activity conservatively:

- **verified_independent:** evidence supports an independent beneficial owner;
- **unknown:** ownership relationship is not established;
- **related_or_controlled:** a disclosed or high-confidence common beneficial owner/control relationship exists;
- **suspected_non_independent:** anomaly evidence warrants review but is not proof.

Do not silently classify unknown wallets as independent. Only the verified independent subset is used for a strict genuine-volume elasticity estimate; unknown volume is reported separately with sensitivity bounds.

### 14.4 Anomaly detection

Monitor patterns including repeated reciprocal flows among related accounts, circular movement, rapid round trips with little net exposure change, unusually concentrated turnover, repeated common-control participation and volume that is inconsistent with independent holder growth.

These are risk signals, not conclusive proof. Preserve evidence, confidence, false-positive review and appeal/audit records. Do not build a wallet-splitting or detection-evasion playbook.

### 14.5 Integrity gates

- duplicate true swap count = 0 after canonical deduplication;
- LP event contribution to swap volume = 0;
- failed transaction contribution to true volume = 0;
- every candle volume reconciles to underlying confirmed swap events;
- all unknown/related/suspected attribution remains visible;
- data gaps and parser-version uncertainty are never silently imputed as real activity.

---

## R15 — LP Sustainability, Inventory Greeks and Owner NLV

### 15.1 Beneficial-owner net asset value

For owner \(o\):

\[
NLV_o=
C_o+
P^*H_o^{free}+
P^*H_o^{locked}+
\alpha_o(Y_{pool}^{redeemable}+P^*X_{pool}^{redeemable})
+F_o^{receivable}
-L_o-C_o^{unsettled}
\]

where:
- \(C_o\): free quote Treasury;
- \(H_o^{free},H_o^{locked}\): free and locked Token inventory;
- \(\alpha_o\): beneficial LP-share fraction;
- \(F_o^{receivable}\): separately attributable settled/receivable fees, counted once;
- \(L_o\): liabilities and committed obligations;
- \(C_o^{unsettled}\): accrued operational/transaction costs.

For PumpSwap, redeemable quote/token balances must come from the version-correct LP redemption/accounting semantics. Do not substitute the effective pricing reserve or a signed virtual quote reserve for redeemable assets. If LP fees remain in pool reserves, their value is already inside the LP claim. Do not add them again as separate income. Creator Fee is separate from LP Fee and is recognized only for its actual beneficiary and receivable status.

### 15.2 CPMM LP Delta and Gamma baseline

For a fixed-invariant CPMM position with owner claim invariant \(k_o\), assuming instantaneous arbitrage to reference price \(P^*\):

\[
X_o(P^*)=\sqrt{\frac{k_o}{P^*}},
\qquad
Y_o(P^*)=\sqrt{k_oP^*}
\]

\[
V_o(P^*)=P^*X_o+Y_o=2\sqrt{k_oP^*}
\]

\[
\Delta_o=\frac{\partial V_o}{\partial P^*}
=\sqrt{\frac{k_o}{P^*}}=X_o
\]

\[
\Gamma_o=\frac{\partial^2V_o}{\partial(P^*)^2}
=-\frac12\sqrt{k_o}(P^*)^{-3/2}
=-\frac{X_o}{2P^*}
\]

This is an analytical baseline for a standard CPMM where the pricing invariant tracks redeemable LP inventory. It is not an exact forecast for PumpSwap with fees, virtual reserves and discrete transactions. If effective pricing reserves differ from redeemable balances, derive the Greeks from the deployed program's state transition. Use the exact state transition for actual NLV. Report total beneficial Token Delta across free inventory, locked inventory and LP claims; do not confuse a proportional LP withdrawal with a Token sale.

### 15.3 Risk-adjusted sustainability

Report:

- net LP NLV change and return;
- fee accrual split by LP, Creator and protocol beneficiary;
- adverse markout at multiple horizons;
- LVR and IL benchmark diagnostics separately;
- Token Delta/Gamma and concentration;
- cash runway and committed obligations;
- depth persistence and external LP response;
- CVaR, drawdown and capital lock-up;
- transaction, priority and failed-execution costs.

The capital allocator maximizes expected NLV subject to tail-loss, operating-reserve, inventory, depth, integrity and protocol constraints. Use \(\epsilon_V=0\) until depth elasticity is empirically validated. External LP response \(\chi=dE/dK_D\) must be separately estimated; Dev's higher fee share caused by external LP withdrawal is not a market-quality gain.

---

## R16 — Multi-Timescale Control and Risk Arbitration

### 16.1 Three control horizons

| Horizon | Responsibilities | Must not do |
|---|---|---|
| Execution / block | Confirm state, validate quote, enforce slippage and permissions, reconcile settlement | Reallocate strategic capital on a stale snapshot |
| Tactical / minutes | Observe depth, basis, flow concentration, inventory and LP add/remove proposals | React to one noisy trade with repeated liquidity churn |
| Strategic / hours-days | Capital allocation, reserve runway, risk limits, Treasury mandate and policy calibration | Override hard gates to chase fees or a preferred price |

All horizons consume the same canonical event-sourced state and state version.

### 16.2 Risk-priority hierarchy

1. Market integrity and legal/authorization boundary.
2. Data freshness, completeness and protocol-version correctness.
3. Beneficial-owner and capital-accounting reconciliation.
4. Operating obligations and reserve minimums.
5. Tail-risk, inventory and execution safety.
6. Minimum market-quality constraints.
7. Expected risk-adjusted economics.
8. Optional score improvements.

A lower-priority objective cannot override a higher-priority veto.

### 16.3 Candidate actions

The policy evaluates only feasible, auditable actions:

- **OBSERVE:** collect more information; no state-changing transaction;
- **HOLD:** preserve current position;
- **ADD:** proportional LP addition using authorized free inventory;
- **REMOVE:** proportional LP withdrawal, recorded as a pool-state event, not a sale;
- **PAUSE:** stop new system-originated actions while continuing market/data monitoring;
- **RECONCILE:** resolve state discrepancy before resuming.

Treasury sale is a separate mandate and action family under the Treasury Exit specification. It must use disclosed beneficial ownership, authorized inventory, execution limits and complete audit records. No hidden-wallet or wash-volume mechanism is permitted.

### 16.4 Hysteresis and action stability

Use separate entry and exit thresholds for WATCH, DEFENSIVE and RECOVERY states. Require a minimum valid observation count and persistence window before leaving a state. Cooldowns must prevent repeated ADD/REMOVE churn caused by noisy measurements, but must never block an emergency risk veto.

When data confidence is low, the correct action is observation/reconciliation or pause—not a more aggressive estimate.

---

## R17 — Participant Heterogeneity and Integrity-Aware Agent Model

### 17.1 Participant classes

Maintain separate stochastic populations for:

- retail / discretionary traders;
- whales / large inventory holders;
- launch snipers and early holders;
- independent informed traders;
- KOL / information publishers;
- arbitrageurs;
- external LP providers;
- aggregators / routers;
- project Treasury and disclosed insiders;
- generic adverse-execution / MEV-risk stress actors.

Each population has distributions, not a single deterministic persona.

### 17.2 Behavioral state

For participant \(i\), model:

\[
\Theta_i=(capital_i,inventory_i,activity_i,
latency_i,slippage_i,risk_i,horizon_i,
signal_i,routeSensitivity_i)
\]

Use empirically calibrated heavy-tailed capital and order-size distributions, asynchronous arrivals, finite inventory, heterogeneous slippage tolerance and correlated information shocks. A participant's order must be constrained by its available Token/quote balance.

KOL attention is an information/attention process, not a guaranteed buy order. Arbitrage requires an executable post-fee edge and finite external capacity. LP providers respond to fee opportunity, adverse selection, lock-up and withdrawal risk.

### 17.3 Separate intent, route and execution

Every simulated or observed order should have distinct states:

\[
Intent\rightarrow RouteChoice\rightarrow Submission
\rightarrow Settlement\rightarrow Reconciliation
\]

The intent process is exogenous in fixed-intent causal experiments. In adaptive simulations, behavior may respond to prior execution outcomes, but this response is reported separately.

### 17.4 Related-party and anomaly model

Beneficial ownership is a graph with evidence and confidence, not a guess based on address similarity alone. Simulations may include disclosed related accounts to test whether the integrity layer correctly excludes controlled activity from independent volume. Do not use the simulator to optimize concealment or detection evasion.

---

## R18 — Full Lifecycle State Machine

The lifecycle is event-driven. Time since launch is a feature, not the sole transition condition.

| State | Entry evidence | System posture |
|---|---|---|
| **CURVE** | Bonding curve is active | Track supply, curve reserves, participant intent and migration readiness |
| **MIGRATION_PENDING** | Completion detected but pool state not fully reconciled | Freeze state-changing policy actions; reconcile program state, reserves, fees and LP shares |
| **EARLY_POOL** | PumpSwap pool confirmed | Conservative capital, high uncertainty; do not claim calibrated depth elasticity from a tiny sample |
| **DISCOVERY** | Multiple valid observations and independent reference available | Measure basis, route share, execution and resilience; preserve uncertainty |
| **MATURE** | Stable data and sufficient validated observations | Normal risk-gated capital and liquidity policy |
| **STRESS** | Tail-risk, basis, depth, flow or data thresholds breached | Stop new risk-increasing allocation; evaluate risk reduction under hard constraints |
| **RECOVERY** | Stress triggers clear but persistence is not yet established | Observe and reconcile; require sustained valid observations before normal actions |
| **PAUSED** | Integrity, protocol, accounting or critical data gate fails | No new system-originated state changes; continue monitoring and incident records |
| **TERMINAL** | Strategy mandate ends or pool becomes non-operational | Reconcile all claims, liabilities, fees and remaining obligations |

Transition rules require confirmed on-chain events, data-quality checks, hysteresis and explicit audit reasons. A pause applies to the system's own actions; it does not imply the protocol or public market is halted.

---

## R19 — Historical Replay, Calibration and Acceptance

### 19.1 Required data contract

At minimum, each historical launch cohort requires:

- slot-ordered confirmed swaps and instruction/event indices;
- exact token/quote amounts, fees and versioned fee schedule;
- effective PumpSwap reserves, including virtual-reserve semantics;
- LP add/remove events and LP-share ownership;
- independent venue prices and executable depth where available;
- transaction success/failure and priority fee;
- wallet labels and beneficial-owner confidence;
- data freshness, missing intervals and parser version.

If order intent, abandoned quote or route alternatives are unavailable, route-choice elasticity is only partially identified. Report bounds or scenario ranges; do not present a fabricated point estimate.

### 19.2 Calibration split

Split by launch/cohort and time, not random rows from the same launch:

1. calibration/training launches;
2. validation launches for threshold and model selection;
3. held-out launches for final evaluation.

Prevent future data leakage into historical features. Version all source data, parser logic, model parameters and fee adapters.

### 19.3 Counterfactual policy baselines

Compare on matched seeds and the same exogenous shock tapes:

1. no Dev LP / Treasury-only;
2. fixed proportional LP allocation;
3. fee/LVR screen with zero depth elasticity;
4. calibrated depth-elasticity allocator;
5. joint LP/Treasury allocator with external LP response;
6. risk-gated market-quality controller.

Report owner NLV and external market-quality outcomes separately.

### 19.4 Required report

For each policy and launch cohort, report:

- mean, median, p10, p90 and CVaR;
- true independent, unknown and related/controlled volume separately;
- two-sided depth at each impact band;
- route share, fill rate, failed-order reasons and execution cost;
- reference basis and recovery distributions;
- adverse markout and LP fee net of attributable costs;
- LP NLV, Token Delta/Gamma, cash runway and drawdown;
- external LP crowd-in/crowd-out response;
- integrity flags, data completeness and reconciliation errors.

Use at least 100 independent seeds for exploratory distributions and 500+ for more stable tail estimates. Keep all runs, including unfavorable ones.

### 19.5 Acceptance gates

The research is not accepted until:

1. supply, reserves, LP shares, owner balances and Treasury obligations reconcile;
2. PumpSwap fee and effective-reserve logic matches the relevant deployed program version;
3. true OHLCV reconciles exactly to confirmed unique swaps;
4. LP events, transfers and failed transactions never inflate swap volume;
5. buy/sell depth reproduces actual fee-aware pool transitions;
6. reference prices are independent, executable, fresh and confidence-scored;
7. route choice includes competing venues and a no-trade option;
8. fixed-intent experiments isolate depth mechanics from demand changes;
9. adverse markout, IL and LVR use distinct labels and no duplicate loss accounting;
10. fairness comparisons use matched intents and disclose uncertainty;
11. hard risk and integrity gates veto economic optimization;
12. results reproduce across seeds and generalize to held-out launches;
13. paper execution and reconciliation pass before any separately authorized live deployment.

No live execution is authorized by this specification.

---

## Final Research Closure

The mathematical research sequence R08–R19 is now specified. This closes the current theory backlog at the specification level, not the implementation or empirical-validation backlog.

The remaining unknowns are empirical and protocol-specific:

- exact versioned PumpSwap state/fee semantics;
- executable independent reference venues and their depth;
- real trader intent and route-choice observations;
- verified beneficial-owner attribution;
- calibrated thresholds for each launch stage;
- held-out estimates of depth elasticity, LP supply response and adverse markout.

Until those inputs are available, uncertain parameters must remain explicitly synthetic or conservative. In particular, use zero depth-volume elasticity for capital allocation until validated. The system must prefer an honest unknown over a precise but unsupported estimate.
