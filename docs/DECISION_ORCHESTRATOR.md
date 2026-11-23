# Market Making Decision Orchestrator

**Document type:** Decision architecture and mathematical research specification  
**Version:** 0.4  
**Status:** Architecture and fixed-CPMM transition baseline defined; protocol validation, solver design and simulation validation remain open  
**Parent specification:** [Market Making & Market Quality System](MARKET_MAKING_MARKET_QUALITY.md)  
**Primary venue:** Fixed PumpSwap CPMM pool  
**Strategy scope:** Initial liquidity, proportional LP add/remove, spot inventory, Dev treasury exit and capital-risk management

---

## 1. Purpose

The Market Making Decision Orchestrator (MMDO) is the single decision-coordination layer for the Market Making & Market Quality System.

It resolves conflicting proposals from Market Intelligence, Flow Intelligence, Market Quality, Inventory, Liquidity, Dev Treasury & Exit, Execution and Risk. It does not use majority voting, allow each engine to execute independently, or let a market-quality target override capital and integrity constraints.

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
| action_type | HOLD, OBSERVE, ADD_LP_PRO_RATA, REMOVE_LP_PRO_RATA, SELL_TREASURY_AMM, SELL_TREASURY_OTC, HOLD_TREASURY, PAUSE_NEW_ACTIONS, or another explicitly authorized action |
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
S_t=(R_t,I_t,L_t,I_t^{owner},T_t,F_t,V_t,C_t,B_t,Q_t,A_t)
\]

where:

- \(R_t\): protocol reserves and pool state.
- \(I_t\): free Token and quote inventory by owner and location.
- \(I_t^{owner}\): wallet-clustered beneficial ownership and controlled-account attribution with confidence.
- \(T_t\): treasury cost basis, locked/unlocked inventory, vesting, realized proceeds, reserve mandate and exit-policy state.
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
- **REMOVE_LP_PRO_RATA:** Withdraw a specified fraction of the account's own LP shares proportionally, when justified by risk or capital policy. In the simulator, amount is that fraction in [0,1]; zero preserves legacy full withdrawal.
- **PAUSE_NEW_ACTIONS:** Stop new discretionary capital deployment and inventory actions.
- **RESUME_WITH_LIMITS:** Resume only after the required health checks pass.
- **SELL_TREASURY_AMM:** Sell an authorized unlocked tranche through a supported curve/AMM route under actual impact and reserve limits.
- **SELL_TREASURY_OTC:** Settle a documented sale with a genuinely independent counterparty.
- **HOLD_TREASURY:** Retain eligible treasury exposure when risk-adjusted continuation value exceeds current net realizable proceeds.

Treasury disposition is proposed by the Dev Treasury & Exit Engine and evaluated jointly with LP, inventory and capital actions. A controlled-wallet transfer is not a sale and does not reduce beneficial ownership. A Dev sale into a pool partly owned by Dev must report gross swap amount separately from the net reduction in beneficial exposure and quote value. The orchestrator must reject self-trades, wash volume, artificial candles, deceptive coordination and hidden-wallet exit policies. Permitted treasury sales require valid unlock, mandate, disclosure, route, impact and settlement checks.

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
- A claimed external sale is only a transfer among wallets with the same beneficial owner, or counterparty independence/settlement cannot be established to the required confidence.
- A treasury sale violates vesting, disclosure, legal/mandate or treasury-reserve restrictions.
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

For market-making actions, among bundles with the same best feasible quality-service result, maximize the following market-making economic objective:

For treasury exits, use the separate Dev Treasury & Exit mandate: maximize expected net realizable proceeds plus the risk-adjusted continuation value of remaining inventory, subject to the same hard integrity, ownership, vesting, capital, execution and market-quality constraints. Do not count LP principal as profit or use a weighted score to buy permission to breach a hard gate.

Cash-capital recovery ratio, economic NLV and operating-solvency coverage are separate diagnostics. Do not add capital already recovered as a second reward when it is already represented in treasury cash or NLV. A break-even target never overrides the impact, depth, reserve, ownership or market-integrity gates. Creator Fee is counted only for the actual beneficial recipient and only once; LP fees retained in reserves remain part of the LP claim.

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

### Case F — Dev proposes a treasury sale while owning part of the pool LP

Recompute the combined wallet-plus-LP transition. For an ideal fee-free CPMM, if Dev owns LP fraction alpha and sells q Token into that same pool, the net beneficial Token reduction is only (1-alpha)q and the net quote benefit is only (1-alpha) times the pool quote output. Report the gross swap and net owner-level exit separately. If alpha is 100%, do not classify the action as a net treasury exit.

### Case G — Dev transfers tokens to a different wallet

If the destination is still controlled by the same beneficial owner, classify the event as an internal transfer. Do not recognize sale proceeds, external distribution or a reduction in Dev concentration. A genuinely independent OTC buyer requires documented consideration and confirmed settlement.

### Case H — Dev proposes REMOVE_LP followed by SELL_TREASURY_AMM

Recompute the post-withdrawal pool reserves, remaining LP supply, Dev's new LP ownership fraction, and sell-side executable depth before evaluating the sale. Proportional withdrawal alone is not an exit. If the subsequent sale benefits from a smaller Dev LP share but breaches the post-action depth floor or marginal-impact limit, reject the sale bundle. Do not rank it higher merely because more of the swap loss is shifted to remaining LP owners. REMOVE_LP may still be considered independently as a risk or capital action; the sale must pass its own authorization and market-quality gates.

## 11. Multi-timescale authority

| Layer | Authority | Orchestrator responsibility |
|---|---|---|
| L0 seconds | Data freshness, transaction state, execution guard | Validate state version, enforce transaction bounds, pause on anomalies |
| L1 minutes | Flow estimates and inventory-risk envelope | Update scenario inputs and risk budgets within strategic limits |
| L2 hours | LP and capital allocation | Select ADD / HOLD / REMOVE quantities under current constraints |
| L3 lifecycle | Total authorized capital, treasury mandate, vesting/disclosure policy and phase limits | Enforce the strategic envelope; require explicit approval for changes |

Higher-level layers set constraints; lower-level layers cannot silently expand them. A lower-level safety guard may pause actions immediately. Only the designated governance/owner process can change the strategic capital mandate.

### 11.1 Initial cadence and trigger semantics

| Layer | Initial evaluation window | Trigger behavior | Allowed authority |
|---|---|---|---|
| L0 — Event safety | Event-driven; seconds-scale observation | Process confirmed swaps, reserve changes, LP events, transaction status and protocol anomalies | May pause new actions; does not resize LP |
| L1 — Inventory and flow | Rolling 1–5 minute windows | Update flow, inventory, forecast error and risk bands; request an early L2 review on material risk changes | May propose risk-envelope changes within L3 limits |
| L2 — Liquidity and capital | Periodic 1–4 hour review, plus risk-triggered re-evaluation | Compare proportional ADD / HOLD / REMOVE under the latest scenarios | Requires orchestrator and Risk authorization |
| L3 — Lifecycle capital | Launch, graduation or explicit mandate change | Set total authorized capital, phase limits, initial pool budget and reserve policy | Requires explicit owner/governance authorization |

These are starting design windows, not universal constants. Calibrate them against block time, event rate, transaction latency, pool depth, forecast horizon and lifecycle phase. A single large swap may trigger a fresh risk evaluation, but it must not automatically trigger an LP resize.

L0 is event-driven for safety and state correctness. An event is not itself a discretionary trading instruction. L1 can request an immediate L2 evaluation when a material risk boundary is crossed. L2 owns capital sizing. L3 owns the authorized capital envelope.

### 11.2 Hysteresis, persistence and cooldown

For a discretionary depth or risk trigger, define:

- Entry threshold \(\theta_{on}\).
- Exit threshold \(\theta_{off}\), where \(\theta_{off}<\theta_{on}\).
- Persistence window \(T_{persist}\).
- Post-confirmation cooldown \(T_{cooldown}\).
- Explicit emergency-pause conditions.

A discretionary trigger becomes eligible only when it persists for the required observation window, the canonical state is fresh, and the relevant forecast confidence is sufficient. Separate entry and exit thresholds prevent oscillation near a boundary.

Cooldown begins only after a confirmed state transition. A pending or unresolved transaction locks conflicting actions. Expiry of cooldown does not imply that another action should occur; the full state and action set must be recomputed.

Emergency safety pause may override normal cooldown. It does not waive authorization, on-chain precondition checks or state reconciliation for a financial transaction. In particular, stale data must not be used to justify an automatic LP withdrawal.

### 11.3 Forecast-error buffer and regime uncertainty

For predicted flow \(Q_{pred}\) and empirical forecast residual \(\epsilon_Q=Q_{actual}-Q_{pred}\), construct stress demand using a calibrated residual quantile:

\[
Q_{stress}=Q_{pred}+Quantile_{\alpha}(\epsilon_Q)
\]

Do not assume Gaussian residuals without empirical evidence. Meme-token flows may be heavy-tailed, clustered and regime-dependent. Calibrate residual distributions by lifecycle phase, forecast horizon and liquidity regime. If the model is out of distribution or confidence is inadequate, widen the scenario set or enter OBSERVE rather than presenting a precise point forecast as certainty.

### 11.4 Operating modes

The orchestrator should expose an explicit operating mode:

| Mode | Entry condition | Permitted behavior |
|---|---|---|
| NORMAL | State reconciled and all budgets within limits | Evaluate all authorized candidate actions |
| DEGRADED_DATA | Stale, missing or conflicting observations | Observe and reconcile; block discretionary financial actions |
| INVENTORY_DEFENSE | Inventory warning band or stress exposure elevated | Block risk-increasing actions; evaluate separately authorized risk reduction |
| CAPITAL_CONSERVATION | Reserve or tail-risk budget near limit | Block discretionary capital deployment |
| EMERGENCY_PAUSE | Protocol, key, accounting or critical safety incident | Stop new discretionary actions and follow incident controls |
| RECOVERY | Incident resolved but stability not yet demonstrated | Resume gradually after fresh state and a stable observation period |

Mode entry and exit use separate thresholds and dwell periods. Recovery requires transaction reconciliation and verified state consistency. A mode transition itself is not permission to trade.

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
13. **Beneficial-owner accounting:** controlled-wallet transfers do not reduce Dev exposure, count as external distribution or realize profit.
14. **LP self-internalization:** a Dev sale into its partly owned pool reports gross swap versus net owner-level exposure reduction correctly.
15. **Vesting and proceeds:** locked tokens cannot be sold; LP principal is not profit; OTC proceeds require confirmed independent settlement.
16. **Exit-policy comparison:** adaptive exit is compared against no-sale and fixed-schedule baselines on matched seeds using executable terminal value.
17. **Partial LP withdrawal:** withdrawing a fraction of an owner's LP shares preserves beneficial-owner Token/quote exposure before fees and costs, and releases cost basis pro-rata.
18. **Sequence externality:** sell-before-remove and remove-before-sell produce correctly reconciled owner exposure, quote proceeds, price impact and remaining external LP depth.
19. **Fee split:** sell-side pool reserve changes retain the LP fee portion and remove protocol/creator fee portions according to the active versioned fee model.

## 14. Open research after this specification

The architecture is defined, but the following work remains:

- Validate the proportional LP transition baseline against deployed PumpSwap reserve, LP mint/burn, fee, token-transfer and rounding semantics.
- Define a calibrated stress-scenario library, including correlated sell arrivals and external-reference shocks.
- Select robust/chance-constraint methods and calibrate their confidence levels from historical residuals.
- Specify the numerical optimization method and fallback behavior when the problem is infeasible.
- Derive action sequencing and transaction atomicity/idempotency requirements for the Solana execution path.
- Implement the orchestrator in the simulator and compare it against simple baseline policies.
- Integrate the Dev Treasury & Exit Engine; derive optimal stopping, partial liquidation and route selection under beneficial-owner accounting.
- Validate out-of-sample across multiple launches and market regimes.

**Next research task:** Derive and validate the Dev Treasury & Exit policy, including the LP-ownership-aware net-exit identity, before implementing joint LP/treasury action bundles and the capital-allocation solver.

No live execution should be enabled merely because this architecture document is complete. Implementation, simulation, paper execution and live authorization remain separate gates.

## 15. Exact proportional CPMM LP transition baseline

This section derives the ideal constant-product transition for the fixed-pool strategy. It is an analytical baseline, not a substitute for validating PumpSwap's actual LP mint/burn instructions, fee handling, token extensions, rounding and account semantics.

### 15.1 Definitions and assumptions

Let:

- \(X\): pool Token reserve.
- \(Y\): pool quote/SOL reserve.
- \(k=XY\): constant product.
- \(P=Y/X\): marginal spot price in SOL per Token.
- \(S\): total LP-share supply.
- \(\alpha\): Dev's share of total LP supply, so Dev owns \(\alpha S\) LP units.
- \(X_f,Y_f\): Dev's free Token and SOL inventory.

Assume a standard proportional CPMM with no transfer tax, no protocol-specific reserve adjustment, no fee accrued during the instantaneous action, and no rounding. The implementation adapter must replace these assumptions with verified PumpSwap semantics.

### 15.2 Proportional ADD

Let \(a\geq0\) be the fraction of current pool reserves added. The deposit is:

\[
\Delta X=aX,\qquad \Delta Y=aY
\]

Post-add reserves:

\[
X'=(1+a)X,\qquad Y'=(1+a)Y
\]

The spot-price ratio is unchanged:

\[
P'=\frac{Y'}{X'}=\frac{Y}{X}=P
\]

Under standard proportional LP minting, new LP units are \(aS\). Dev's new share is:

\[
\alpha'=\frac{\alpha S+aS}{(1+a)S}
=\frac{\alpha+a}{1+a}
\]

Dev's post-add LP claims are:

\[
X'_{LP}=\alpha'X'=(\alpha+a)X
\]

\[
Y'_{LP}=\alpha'Y'=(\alpha+a)Y
\]

The wallet contributes \(aX\) Token and \(aY\) SOL. Therefore, before fees and costs:

- Free Token falls by \(aX\).
- Free SOL falls by \(aY\).
- LP underlying claims rise by exactly those amounts.
- Total current portfolio Token and SOL quantities are unchanged.
- Current portfolio Delta is unchanged by the reclassification.
- Pool depth increases by the reserve scale factor \(1+a\).
- LP Gamma magnitude increases because more of the portfolio is now exposed to the CPMM's concave inventory curve.

Using the ideal CPMM LP value \(V_{LP}=2\alpha\sqrt{kP}\), the LP Gamma is:

\[
\Gamma_{LP}=-\frac{\alpha}{2}\sqrt{k}P^{-3/2}
\]

After ADD:

\[
\Gamma'_{LP}
=-\frac{\alpha+a}{2}\sqrt{k}P^{-3/2}
\]

Thus proportional ADD does not create an immediate directional Token purchase when funded from existing pro-rata inventory, but it does increase future inventory sensitivity to price movement. It is a transformation of inventory into LP exposure, not a free reduction of risk.

### 15.3 Proportional REMOVE

Let \(f\in[0,1]\) be the fraction of Dev's own LP units burned. Dev burns \(f\alpha S\) units.

Post-remove pool reserves:

\[
X'=(1-f\alpha)X,\qquad
Y'=(1-f\alpha)Y
\]

Total LP supply becomes \((1-f\alpha)S\), while Dev retains \(\alpha(1-f)S\). Therefore:

\[
\alpha'=\frac{\alpha(1-f)}{1-f\alpha}
\]

Dev's remaining LP claims are:

\[
X'_{LP}=\alpha'X'=\alpha(1-f)X
\]

\[
Y'_{LP}=\alpha'Y'=\alpha(1-f)Y
\]

The wallet receives \(f\alpha X\) Token and \(f\alpha Y\) SOL. Before fees and costs:

- Free Token rises by \(f\alpha X\).
- Free SOL rises by \(f\alpha Y\).
- LP claims fall by the same quantities.
- Total current portfolio Token and SOL quantities are unchanged.
- Current portfolio Delta is unchanged by the reclassification.
- Pool depth falls by the reserve scale factor \(1-f\alpha\).
- Dev's LP Gamma magnitude falls by the fraction \(f\).

The post-remove LP Gamma is:

\[
\Gamma'_{LP}
=-\frac{\alpha(1-f)}{2}\sqrt{k}P^{-3/2}
\]

Therefore REMOVE reduces future LP Gamma exposure but does not, by itself, reduce the Dev's current Token inventory exposure. It moves assets from the LP claim to the wallet and reduces market depth.

### 15.4 Price impact after proportional depth changes

For an ideal fee-free CPMM, a Token input \(q_X\) changes the marginal price by:

\[
\frac{P'}{P}=
\left(\frac{X}{X+q_X}\right)^2
\]

After proportional ADD with reserve scale \(s=1+a\):

\[
\frac{P'}{P}=
\left(\frac{sX}{sX+q_X}\right)^2
=
\left(1+\frac{q_X}{sX}\right)^{-2}
\]

For a quote/SOL input \(q_Y\):

\[
\frac{P'}{P}=
\left(1+\frac{q_Y}{Y}\right)^2
\]

After proportional ADD:

\[
\frac{P'}{P}=
\left(1+\frac{q_Y}{sY}\right)^2
\]

ADD therefore reduces the price impact of a given trade size by increasing the reserve denominator. REMOVE has the reverse effect with \(s=1-f\alpha\).

These equations describe marginal-price movement, not execution VWAP or user slippage. Production calculations must use the actual PumpSwap fee path, effective input amount, reserve semantics and token transfer behavior.

### 15.5 Decision implications

1. **ADD is not a buy:** proportional ADD funded from existing wallet assets does not change the spot price or total current Token/SOL holdings before costs.
2. **ADD increases LP Gamma:** it converts free inventory into an LP claim and increases future inventory sensitivity.
3. **REMOVE is not a sell:** proportional REMOVE does not sell the received Token; it transfers the underlying claim to free wallet inventory.
4. **REMOVE reduces depth and Gamma:** it lowers future LP inventory sensitivity but also reduces executable depth.
5. **Delta and Gamma must be separated:** a strategy can preserve current Delta while materially changing future risk through Gamma and liquidity depth.
6. **Risk must be measured at portfolio level:** compare the complete pre/post state, including free inventory, LP claims, fees, costs and stress scenarios.
7. **A fixed pool still requires dynamic capital decisions:** the system dynamically chooses whether and how much to ADD, HOLD or REMOVE; it does not dynamically move the LP price range.

### 15.6 Protocol validation requirements

Before using these equations in production code, verify against the deployed PumpSwap program and historical transactions:

- Exact reserve fields used for pricing.
- LP-share mint/burn formula and any locked/burned supply.
- Fee accounting and whether fees alter reserves or separate fee vaults.
- Token-2022 and transfer-fee behavior, if supported.
- Rounding direction and minimum deposit/withdrawal constraints.
- Migration initialization and any special initial LP accounting.
- Actual wallet and LP claim deltas from confirmed transactions.

A unit test must reconcile predicted and observed reserve, LP-share and wallet-balance changes for both ADD and REMOVE. Any mismatch blocks use of the analytical formula for live sizing.
