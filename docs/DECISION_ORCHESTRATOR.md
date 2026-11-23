# Market Making Decision Orchestrator

**Document type:** Decision architecture and mathematical research specification  
**Version:** 0.1  
**Status:** Architecture defined; solver design and simulation validation remain open  
**Parent specification:** [Market Making & Market Quality System](MARKET_MAKING_MARKET_QUALITY.md)  
**Primary venue:** Fixed PumpSwap CPMM pool  
**Strategy scope:** Initial liquidity, proportional LP add/remove, spot inventory and capital-risk management

---

## 1. Purpose

The Market Making Decision Orchestrator (MMDO) is the single decision-coordination layer for the Market Making & Market Quality System.

It resolves conflicting proposals from Market Intelligence, Flow Intelligence, Market Quality, Inventory, Liquidity, Execution and Risk. It does not use majority voting, allow each engine to execute independently, or let a market-quality target override capital and integrity constraints.

The governing principle is:

**Hard constraints first; then feasible market-quality service; then risk-adjusted economics; then operational simplicity.**

The orchestrator selects a compatible action bundle against one canonical state snapshot, runs pre-trade simulation, obtains risk authorization, executes only within permission, and reconciles the confirmed result.

It is a research architecture, not a claim that an autonomous live trading system is implemented.

## 2. Design principles

1. **One canonical state:** All engines read the same versioned state and accounting ledger.
2. **Proposals, not independent execution:** Engines produce typed proposals; only the orchestrator can authorize an action.
3. **No voting:** A proposal is evaluated by its expected state transition, resource use, costs and risk—not by the number of engines supporting it.
4. **Hard constraints are non-negotiable:** Data integrity, accounting, permissions, market integrity and hard risk budgets cannot be overridden by a weighted score.
5. **Quality targets are service objectives:** Buy/sell depth and execution-quality targets are pursued only within authorized capital and risk limits.
6. **Joint evaluation:** Actions that affect the same pool, inventory or capital bucket are evaluated as a combined bundle.
7. **Uncertainty is explicit:** Forecasts carry distributions and confidence; a point estimate is not treated as certainty.
8. **No action is a valid action:** HOLD / OBSERVE is always a candidate when acting is not justified.
9. **Execution is conditional:** A proposal is bound to a state version and expires when its preconditions are no longer true.
10. **Auditability:** Every proposal, rejection, authorization, transaction and reconciliation result is recorded.

## 3. Engine contract: proposals

Each engine may emit one or more proposals. A proposal must contain:

| Field | Meaning |
|---|---|
| proposal_id | Unique proposal identifier |
| engine_id | Originating engine |
| state_version | Canonical state version used for analysis |
| created_at / expires_at | Proposal time-to-live |
| action_type | HOLD, OBSERVE, ADD_LP_PRO_RATA, REMOVE_LP_PRO_RATA, PAUSE_NEW_ACTIONS, or another explicitly authorized action |
| target_pool | Pool identifier, when relevant |
| quantity | Proposed capital/token amount and units |
| preconditions | Required balances, protocol state, price/impact bounds and state predicates |
| expected_state_delta | Distribution of expected reserve, inventory, LP and quality changes |
| cost_estimate | Protocol fees, priority fee, rent, slippage, operational and capital costs |
| risk_vector | Inventory, liquidity, tail, execution and protocol risks |
| scenario_results | Outcomes under named baseline and stress scenarios |
| confidence | Calibrated confidence and uncertainty interval |
| dependencies | Actions or observations required first |
| compatibility_key | Resource/pool key used to detect conflicting proposals |
| rationale | Evidence and calculation references, not unsupported intent labels |

Proposals without a state version, explicit units, expiry, cost estimate or risk vector are invalid.

Engines may recommend actions, but none except the authorized Execution Engine may submit transactions. Risk controls are enforced by the orchestrator and cannot be bypassed by a proposal.

## 4. Canonical state and state-version control

Let the canonical state at decision time t be:

\[
S_t=(R_t,I_t,L_t,F_t,V_t,C_t,B_t,Q_t,A_t)
\]

where:

- \(R_t\): protocol reserves and pool state.
- \(I_t\): free Token and quote inventory by owner and location.
- \(L_t\): LP positions, withdrawable claims and ownership.
- \(F_t\): observed and estimated participant flow.
- \(V_t\): volatility and regime estimates.
- \(C_t\): holder and LP concentration.
- \(B_t\): pool/reference price basis and venue state.
- \(Q_t\): data quality, completeness and freshness.
- \(A_t\): authorized capital, mandates and action limits.

Every state snapshot has a monotonically increasing version or event watermark. A proposal is valid only for the state version on which it was calculated, subject to an explicit tolerance policy for immaterial events.

Before transaction submission:

1. Read the latest confirmed pool and wallet state.
2. Verify the proposal's state version and expiry.
3. Recalculate balances, proportional deposit amounts, expected impact and risk.
4. Invalidate and recompute if any material precondition changed.
5. Use an idempotency key to prevent duplicate submission.
6. Reconcile the confirmed transaction against the predicted state transition.

If data is stale, incomplete, contradictory or from an unverified protocol version, the default is OBSERVE / PAUSE_NEW_ACTIONS. Do not use stale data to add liquidity, trade inventory or perform a discretionary withdrawal. A pre-authorized emergency action may proceed only after its own on-chain preconditions are freshly verified.

## 5. Action space and compatibility

For the current fixed-pool strategy, the core action set is:

- **HOLD:** Keep current LP and inventory configuration.
- **OBSERVE:** Wait for more reliable information; do not change capital.
- **ADD_LP_PRO_RATA:** Add liquidity at the current pool reserve ratio.
- **REMOVE_LP_PRO_RATA:** Withdraw a specified share proportionally, when justified by risk or capital policy.
- **PAUSE_NEW_ACTIONS:** Stop new discretionary capital deployment and inventory actions.
- **RESUME_WITH_LIMITS:** Resume only after the required health checks pass.

Inventory disposition is evaluated as a separate, explicitly authorized spot-risk process. The orchestrator must not route a Dev-controlled trade through the same pool or related wallets to manufacture volume, candles, demand or price signals. Any legitimate treasury or inventory sale must follow its separate mandate, ownership disclosure and execution controls.

### 5.1 Action compatibility

Actions are not independently additive.

- ADD_LP and REMOVE_LP against the same pool cannot execute concurrently as separate competing plans. Net or sequence them into one approved plan.
- Multiple proposals using the same capital bucket must share one budget calculation.
- A pool action and an inventory action must be evaluated together if either changes the other's risk or available balance.
- Dependent actions execute only after the prior confirmed result is reconciled.
- If two actions have incompatible preconditions, select one bundle or HOLD; do not submit both and hope transaction ordering resolves the conflict.

A candidate bundle is denoted \(b\in\mathcal B_t\). The bundle includes action quantities, ordering, dependencies and expected state transitions.

## 6. Arbitration: hard constraints before optimization

The orchestrator uses a staged feasibility process. It is not a weighted vote.

### 6.1 Stage 0 — Data, authority and integrity gate

Reject a bundle if any of the following is true:

- State is stale, incomplete or internally inconsistent.
- Protocol version or account ownership assumptions are unverified.
- The action exceeds the authorized mandate or capital envelope.
- Asset accounting double-counts LP claims and free inventory.
- The action would create self-trades, wash volume, artificial candles or deceptive market activity.
- Required transaction preconditions or audit fields are absent.

A failed Stage 0 gate leads to OBSERVE or PAUSE_NEW_ACTIONS, not a speculative fallback trade.

### 6.2 Stage 1 — Deterministic safety invariants

For every candidate bundle, enforce:

\[
\begin{aligned}
K_{used}(b)&\leq K_{authorized}\\
K_{reserve}(b)&\geq K_{reserve}^{min}\\
K_{execution}(b)&\geq K_{execution}^{min}\\
Impact(b)&\leq Impact^{max}\\
Slippage(b)&\leq Slippage^{max}\\
C_{tx}(b)&\leq C_{tx}^{max}
\end{aligned}
\]

Also require non-negative available balances, valid LP ownership/withdrawal rights, protocol-valid instructions and no duplicate transaction intent.

These are hard constraints. The optimizer cannot trade them off against fee income or a market-quality score.

### 6.3 Stage 2 — Portfolio and tail-risk feasibility

Calculate the post-action portfolio using the full state transition, not just the free-wallet balances.

For each stress scenario \(\omega\in\Omega\):

\[
S_{t+h}^{\omega}=F_h(S_t,b,\omega)
\]

Evaluate:

- Free Token and quote inventory.
- LP-underlying Token and quote exposure.
- Combined Delta/Gamma and scenario PnL.
- Liquidity withdrawal and depth loss.
- Capital reserve after execution.
- Tail loss and correlated participant exits.

A candidate must satisfy the hard risk budgets. Where a risk is modeled probabilistically, use an explicit chance constraint such as:

\[
Pr(Risk(b)\leq B_{risk})\geq 1-\varepsilon
\]

and a tail-loss constraint:

\[
CVaR_{\alpha}(Loss(b))\leq B_{tail}
\]

The confidence level, scenario set and risk budget must be calibrated and versioned. Do not claim that a scenario test guarantees safety outside its modeled assumptions.

### 6.4 Stage 3 — Market-quality service targets

Market-quality objectives are evaluated only among bundles that passed the hard gates.

For each side and impact budget, define a depth shortfall:

\[
s_i(b)=\max(0,D_i^{min}-D_i(b))
\]

A normalized quality shortfall can be:

\[
S_Q(b)=\sum_i w_i
\frac{s_i(b)}{\max(D_i^{min},\epsilon)}
\]

The target depth is a service objective, not a reason to exceed authorized capital or risk limits. If no safe bundle can meet it, choose the safest feasible improvement or HOLD and report the remaining shortfall. Never manufacture trading activity to make a quality metric appear satisfied.

### 6.5 Stage 4 — Risk-adjusted economics

Among bundles with the same best feasible quality-service result, maximize:

\[
J_E(b)=
E[\Pi_{net}(b)]
-\lambda CVaR_{\alpha}(Loss(b))
-\gamma C_{capital}(b)
-\rho C_{rebalance}(b)
\]

where net PnL includes actual fees and legitimate execution outcomes, less protocol fees, priority fees, slippage, rent, capital opportunity cost and inventory mark-to-market. Avoid double-counting LVR, impermanent loss and mark-to-market loss: the accounting benchmark must be defined once.

### 6.6 Stage 5 — Minimize unnecessary churn

If candidate bundles have economically indistinguishable outcomes, prefer the one with fewer state changes and lower operational complexity:

\[
C_{churn}(b)=
\kappa_1 N_{actions}(b)
+\kappa_2 |\Delta K_L|
+\kappa_3 N_{dependent\_transactions}(b)
\]

This tie-breaker must never delay an emergency pause or a required risk-reducing action.

## 7. Lexicographic decision rule

The selection order is:

1. Discard actions that fail data, authority or market-integrity gates.
2. Discard actions that violate deterministic safety invariants.
3. Discard actions that breach portfolio or tail-risk budgets.
4. Among remaining actions, minimize market-quality service shortfall.
5. Among equally good quality outcomes, maximize risk-adjusted net economics.
6. Among economically equivalent outcomes, minimize churn and operational complexity.

This is a lexicographic/epsilon-constraint policy, not a majority vote and not one unconstrained weighted score. Risk and integrity cannot be compensated by higher expected fees.

A strategy profile may set different quality targets and authorized capital by lifecycle phase. It may not weaken the non-negotiable integrity and accounting invariants.

## 8. Risk Engine authority and emergency behavior

Risk is a formal guard, not an agent that can issue vague vetoes.

The Risk Engine publishes:

- Current hard limits and remaining budgets.
- Stress scenarios and model versions.
- Breached or near-breached constraints.
- Allowed action classes and maximum quantities.
- Required pause/resume conditions.

Emergency controls:

- On stale or contradictory data: pause new discretionary financial actions.
- On protocol/accounting anomaly: freeze dependent actions and require reconciliation.
- On execution uncertainty: do not blindly retry; first determine whether the prior transaction landed.
- On hard inventory/tail-risk breach: reject actions that increase the breached exposure; evaluate authorized risk-reducing alternatives against their full transition.
- On compromised keys or protocol exploit: follow the separately approved incident response, not an optimizer-selected market action.

A withdrawal does not automatically reduce Token inventory risk. Proportional LP removal transfers the LP's underlying assets to the wallet and reduces future LP Gamma, but the current portfolio's immediate economic exposure is largely unchanged before costs. The orchestrator must recompute the post-withdrawal portfolio and must not label a withdrawal as completed inventory de-risking.

## 9. Value of information and the OBSERVE action

When forecasts disagree or uncertainty is high, the system should consider waiting for more information.

Let \(Y\) be a potential new observation and \(C_{delay}\) the cost of waiting. A simplified value-of-information test is:

\[
VOI=
E_Y[\max_b J(b\mid Y)]
-\max_b E_Y[J(b\mid Y)]
-C_{delay}
\]

If VOI is positive and no hard safety condition requires immediate action, OBSERVE may be preferable to committing capital on a weak estimate.

Examples of useful new information:

- Confirmation that a large flow was one-off rather than persistent.
- Fresh on-chain reserves after a migration or LP event.
- Resolution of missing/duplicated transaction events.
- Updated independent executable reference depth.
- A clearer estimate of correlated holder exits.

Observation is not allowed to delay emergency protection. The system must distinguish uncertainty that justifies waiting from a known hard breach that requires action.

## 10. Conflict-resolution examples

### Case A — Market Quality requests ADD; Inventory reports high Token risk

Do not vote. Simulate the proposed proportional addition and compute the full post-add LP Gamma, inventory distribution, stress PnL and reserve use.

- If the bundle breaches the risk budget, reject ADD.
- If it passes but does not improve the quality target enough to justify its capital cost, HOLD.
- If it safely reduces a material depth shortfall and passes economics, authorize only the calculated quantity.

A high Token inventory warning is not automatically proof that adding LP increases current Delta: a proportional deposit from existing assets can leave current portfolio Delta approximately unchanged while increasing LP Gamma and changing future inventory behavior. Evaluate the full transition.

### Case B — Flow predicts concentrated selling; current depth is insufficient

Use multiple flow scenarios and forecast-error buffers. Test whether the required proportional LP addition remains feasible under correlated selling and reserve depletion.

If no safe bundle exists, report the depth shortfall and preserve the risk budget. Do not promise that the pool can absorb every possible sell wave.

### Case C — Liquidity proposes REMOVE; Market Quality warns depth is already low

Evaluate the withdrawal's reduction in future LP Gamma, released capital, current inventory transfer, lost fees and depth impact together. If the withdrawal is not required by a hard risk limit and its net value is negative, HOLD. If a hard risk limit requires reducing LP exposure, withdraw only the amount justified by the risk calculation and report the resulting depth shortfall.

### Case D — Two engines propose incompatible actions

Merge compatible quantities into a single bundle; sequence actions only when dependencies require it. If the actions cannot be reconciled under one state and budget, reject the conflicting bundle and recompute. Never allow two independent agents to race against the same pool or wallet balance.

### Case E — State changes after proposal generation

Invalidate any proposal whose material preconditions are no longer true. Refresh the canonical state and recompute. Do not execute an expired proposal simply because it was previously approved.

## 11. Multi-timescale authority

| Layer | Authority | Orchestrator responsibility |
|---|---|---|
| L0 seconds | Data freshness, transaction state, execution guard | Validate state version, enforce transaction bounds, pause on anomalies |
| L1 minutes | Flow estimates and inventory-risk envelope | Update scenario inputs and risk budgets within strategic limits |
| L2 hours | LP and capital allocation | Select ADD / HOLD / REMOVE quantities under current constraints |
| L3 lifecycle | Total authorized capital, treasury mandate and phase policy | Enforce the strategic envelope; require explicit approval for changes |

Higher-level layers set constraints; lower-level layers cannot silently expand them. A lower-level safety guard may pause actions immediately. Only the designated governance/owner process can change the strategic capital mandate.

## 12. Audit and decision record

For every decision, persist:

- decision_id and timestamp;
- canonical state version and data-quality status;
- proposals received and invalid proposals;
- candidate bundles and compatibility decisions;
- scenario set, forecast version and parameter version;
- hard constraints evaluated and rejection reasons;
- quality shortfall before/after;
- expected net economics and tail-risk estimate;
- selected action, quantity and expiry;
- Risk authorization;
- transaction signature and confirmation status;
- actual state delta and reconciliation result;
- forecast error and realized outcome.

This record must make it possible to reproduce why the system chose ADD, HOLD, REMOVE, OBSERVE or PAUSE.

## 13. Simulator acceptance tests

The orchestrator is not accepted until the simulator proves at least:

1. **No voting:** changing the number of agents supporting a proposal does not change the result if state, actions and constraints are identical.
2. **Hard-constraint dominance:** no fee or quality reward can make an unsafe action feasible.
3. **Stale-state rejection:** proposals based on invalidated state versions are not executed.
4. **No double counting:** LP claims and their underlying assets are reconciled once.
5. **Conflict resolution:** incompatible add/remove proposals cannot execute concurrently.
6. **Risk-complete withdrawal:** removing LP reduces modeled Gamma but does not falsely reduce current Token inventory exposure.
7. **Forecast uncertainty:** correlated sell scenarios and forecast errors affect feasibility.
8. **No forced action:** HOLD / OBSERVE is selected when all financial actions are infeasible or unjustified.
9. **Idempotency:** retries cannot duplicate a confirmed capital action.
10. **Audit replay:** the same state, proposals, parameters and seed reproduce the same decision.
11. **Market integrity:** LP events are not counted as swaps; self-trades and fabricated volume are not rewarded.
12. **Emergency precedence:** a safety pause is not blocked by normal cooldown or churn penalties.

## 14. Open research after this specification

The architecture is defined, but the following work remains:

- Derive the exact joint state transition for proportional PumpSwap LP add/remove, wallet inventory and all costs.
- Define a calibrated stress-scenario library, including correlated sell arrivals and external-reference shocks.
- Select robust/chance-constraint methods and calibrate their confidence levels from historical residuals.
- Specify the numerical optimization method and fallback behavior when the problem is infeasible.
- Derive action sequencing and transaction atomicity/idempotency requirements for the Solana execution path.
- Implement the orchestrator in the simulator and compare it against simple baseline policies.
- Validate out-of-sample across multiple launches and market regimes.

**Next research task:** Joint action sequencing and robust scenario evaluation. In particular, derive how proportional LP additions/removals interact with free inventory, reserve capital, transaction costs and forecast uncertainty over the full decision horizon.

No live execution should be enabled merely because this architecture document is complete. Implementation, simulation, paper execution and live authorization remain separate gates.
