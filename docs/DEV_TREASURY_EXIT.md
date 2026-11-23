# Dev Treasury & Exit Intelligence

**Document type:** Treasury exit strategy and mathematical research specification  
**Version:** 0.1  
**Status:** Theory defined; adaptive policy, empirical calibration and simulator implementation remain open  
**Parent specification:** [Market Making & Market Quality System](MARKET_MAKING_MARKET_QUALITY.md)  
**Decision authority:** [Market Making Decision Orchestrator](DECISION_ORCHESTRATOR.md)  
**Scope:** Pump.fun bonding curve → graduation → fixed PumpSwap CPMM; spot-only treasury inventory and LP exposure

> This document defines a transparent, risk-aware treasury exit policy. It is not a claim that adaptive exit logic is implemented, does not authorize live execution, and does not provide a way to disguise beneficial ownership or manufacture market activity.

---

## 1. Product decision

Dev is not required to hold every allocated token indefinitely. Treasury inventory is capital with an acquisition basis, liquidity constraints, vesting restrictions, opportunity cost and an exit decision.

The system must optimize the **risk-adjusted, realizable net value** of Dev's treasury over the project lifecycle—not maximize the token's displayed spot price, not maximize wallet token balance, and not assume that LP fees justify holding the entire position forever.

The new subsystem is the **Dev Treasury & Exit Engine (DTEE)**.

Its responsibilities are to:

1. Maintain a beneficial-owner-level ledger of Dev's free, locked, vested, LP and cash assets.
2. Estimate the executable liquidation value of unlocked treasury inventory.
3. Decide HOLD versus partial exit versus full exit under a documented mandate.
4. Select among permitted sale routes and calculate route-specific costs and market impact.
5. Coordinate LP withdrawal and token sale as one portfolio transition where they interact.
6. Track realized proceeds, remaining exposure, cost basis, fees, taxes/other externally supplied obligations and post-exit risk.
7. Prevent internal wallet transfers or related-party trades from being misclassified as genuine external distribution.

The engine proposes actions only. The Decision Orchestrator applies hard constraints and authorizes any action; the Execution Engine performs and reconciles it.

## 2. Non-negotiable integrity boundary

The following are not exit strategies and must not be modeled as ways to improve apparent demand, price or distribution:

- Dev-controlled wallets trading with one another.
- Related-party wallets cycling tokens to manufacture volume.
- Transfers among wallets under common beneficial ownership being counted as external sales.
- Self-trades or wash trades designed to create candles, volume, holder counts or false independent demand.
- Concealing treasury ownership or coordinating promotional activity to create exit liquidity for undisclosed sales.

A transfer between two wallets with the same beneficial owner changes wallet location, not beneficial ownership. It creates no realized sale proceeds and no genuine external distribution.

A trade with a genuinely independent buyer, a documented OTC counterparty, or a real swap against a pool is a different event. It must be recorded with its actual route, consideration, fees, beneficial-owner attribution confidence and execution result. A different wallet address alone is not evidence of an independent buyer.

These are hard policy constraints, not tunable penalties.

## 3. Treasury accounting: what does Dev actually own?

The engine must aggregate all addresses under the same verified or confidence-scored beneficial owner. Wallet-level balances remain visible for audit, but policy decisions use the aggregated owner ledger.

Track at least:

| Bucket | Definition | Immediately sellable? |
|---|---|---|
| Free unlocked Token | Transferable Dev treasury Token outside LP | Yes, subject to mandate and execution limits |
| Locked Token | Token subject to vesting, lock or other transfer restriction | No, until legally/protocol-valid unlock |
| LP Token claim | Dev's look-through share of pool Token reserve | Only after valid LP withdrawal/transfer |
| LP quote claim | Dev's look-through share of pool quote reserve | Only after valid LP withdrawal/transfer |
| Treasury quote cash | Settled SOL/quote proceeds and available reserves | Yes, subject to reserve mandate |
| Pending proceeds | Unconfirmed swaps, OTC settlement or withdrawals | No; not counted as realized cash |
| Controlled-wallet inventory | Inventory in addresses beneficially owned/controlled by Dev | Still Dev exposure; not externalized |

Do not double-count LP underlying assets and LP shares. The LP claim is a look-through claim on pool reserves, not extra supply.

### 3.1 Cost basis by acquisition source

Cost basis must preserve provenance:

- Genesis allocation: use the applicable accounting/tax basis and separately record its economic opportunity cost. Do not silently assume that it is economically free.
- Curve purchase: actual quote paid plus attributable fees and execution costs.
- Secondary purchase: actual consideration paid plus fees.
- LP contribution: transfer the contributing assets' existing basis into the LP position; do not create a second acquisition cost.
- Vesting unlock: changes transferability, not beneficial ownership or historical cost basis.
- Controlled-wallet transfer: changes location only; it does not realize PnL or reset basis.

Realized profit is not equal to gross proceeds. LP principal returned by a withdrawal is not profit. LP fees retained in pool reserves are already included in the LP claim value and must not be added again as separate income; only separately claimable LP fee balances not included in reserve valuation are added. Creator fees are a separate quote-asset revenue stream and count as Dev treasury income only when the creator/beneficial owner is entitled to them; settled amounts enter treasury cash, while unclaimed amounts are tracked as a separate receivable with settlement risk. Fees routed to charity or holder-rewards recipients are not Dev income.

## 4. Treasury objective: realizable net value

Define the Dev treasury state:

\[
s_t=(H_t^f,H_t^l,H_t^{LP},C_t,\alpha_t,B_t,P_t,D_t,\sigma_t,U_t,Q_t)
\]

where:

- \(H_t^f\): free unlocked Token inventory.
- \(H_t^l\): locked Token inventory and unlock schedule.
- \(H_t^{LP}\): Dev's LP look-through Token and quote claims.
- \(C_t\): settled treasury quote cash.
- \(\alpha_t\): Dev's beneficial share of the relevant LP position.
- \(B_t\): source-specific cost basis.
- \(P_t\): local and independent executable reference prices.
- \(D_t\): executable depth and verified independent flow.
- \(\sigma_t\): volatility, regime and tail-risk estimates.
- \(U_t\): future vesting and other committed supply schedule.
- \(Q_t\): data quality, attribution confidence and state freshness.

At any decision time, define the net liquidation value:

\[
NLV_t=C_t+
\mathcal L_t(H_t^f,H_t^{LP},H_t^l)
-C_t^{future}
\]

where \(\mathcal L_t\) is the proceeds from a feasible, route-aware liquidation plan under current depth, protocol constraints, LP withdrawal rights and impact limits. It is not simply token quantity multiplied by marginal spot price.

At the evaluation horizon \(T\):

\[
\Pi_{Dev}^{net}
=
C_T+\mathcal L_T(H_T^f,H_T^{LP},H_T^l)
-B_{total}
-C_{execution}
-C_{capital}
-C_{other}
\]

where \(B_{total}\) is the consistently defined acquisition/accounting basis and \(C_{other}\) includes externally supplied tax, legal, settlement or mandate costs where applicable.

Report separately:

- realized proceeds;
- realized PnL;
- remaining unlocked and locked inventory;
- LP claims and withdrawable value;
- accrued/claimed LP fees;
- unrealized liquidation value;
- total net liquidation value;
- beneficial ownership and concentration.

Never count a token sale's cash proceeds and the same sold tokens' spot value simultaneously.

## 5. Action space

The Treasury Exit Engine may propose:

- **HOLD_TREASURY:** Keep the current exposure and wait for more information.
- **SELL_TREASURY_AMM:** Sell an authorized amount through a supported curve or AMM route, subject to actual depth, impact, slippage and reserve constraints.
- **SELL_TREASURY_OTC:** Sell to a genuinely independent counterparty under documented price, amount, settlement and disclosure terms.
- **WITHDRAW_LP_FOR_EXIT:** Withdraw a permitted portion of Dev's own LP claim, then re-evaluate the resulting Token and quote inventory before any sale.
- **TRANSFER_LP_CLAIM:** Transfer/sell a transferable LP claim to an independent buyer only if protocol rights and settlement are verified.
- **WAIT_FOR_UNLOCK:** Keep locked inventory restricted until its valid unlock condition.
- **PAUSE_EXIT:** Stop discretionary treasury sales when data, ownership, authorization or protocol state is unreliable.

An LP withdrawal is not a token sale. A controlled-wallet transfer is not a sale. An OTC agreement is not realized until consideration is settled and the independent counterparty/beneficial ownership conditions are met.

## 6. Sale-route economics

### 6.1 Bonding-curve sale

Before graduation, use the actual curve sell function, real quote reserve, fee schedule, creator/protocol fee rules, slippage limits and curve completion semantics. Virtual reserves are pricing coordinates, not quote cash available for withdrawal.

A treasury sale must not be sized by assuming that virtual quote reserves are spendable. If real quote reserves cannot support the requested sale, the action is infeasible or must be reduced.

### 6.2 PumpSwap CPMM sale

After graduation, use the protocol-specific swap calculation and current confirmed reserves. For an ideal fee-free CPMM with Token reserve \(X\), quote reserve \(Y\), and Token input \(q\):

\[
\Delta Y=\frac{Yq}{X+q}
\]

The post-swap marginal price ratio is:

\[
\frac{P'}{P}=\left(\frac{X}{X+q}\right)^2
\]

For a maximum permitted marginal-price decline \(\delta\), the idealized input bound is:

\[
q_{impact}^{max}
=
X\left(\frac{1}{\sqrt{1-\delta}}-1\right)
\]

This is only a fee-free analytical bound. Production sizing must use the actual PumpSwap fee path, token transfer behavior, reserve semantics, rounding and transaction simulation. The bound does not guarantee a particular VWAP or realized execution price.

### 6.3 Critical correction: Dev selling into a pool it partly owns

If Dev owns a fraction \(\alpha\) of the LP shares and sells \(q\) Token into that same idealized pool, the pool receives \(q\) Token and pays \(\Delta Y\) quote.

Before fees:

\[
\Delta Y=\frac{Yq}{X+q}
\]

Dev's LP claim simultaneously increases by \(\alpha q\) Token and decreases by \(\alpha\Delta Y\) quote. Therefore the change in Dev's combined wallet-plus-LP exposure is:

\[
\Delta H_{Dev}=-(1-\alpha)q
\]

\[
\Delta C_{Dev}^{net}=(1-\alpha)\Delta Y
\]

This is an accounting identity under the stated idealized assumptions, not an execution recommendation.

Consequences:

- If Dev owns 40% of the LP, a sale of \(q\) into that pool reduces Dev's combined beneficial Token exposure by only \(0.6q\), before fees and other ownership links.
- The net quote benefit is also only \(0.6\Delta Y\), because the quote claim on Dev's LP falls.
- If Dev owns 100% of the LP, selling into its own pool does not create a net beneficial-owner exit or net quote gain before costs. It changes pool state and wallet balances but is economically circular.
- The swap must not be described as independent buyer demand merely because the AMM instruction succeeded.

The simulator must aggregate all Dev-controlled LP wallets when calculating \(\alpha\). It must report gross swap amount and net beneficial-owner exposure reduction separately.

### 6.4 Independent OTC sale

For a genuinely independent buyer purchasing \(q\) at an agreed price \(P_{OTC}\):

\[
Proceeds_{OTC}=qP_{OTC}-C_{settlement}-C_{fees}
\]

The route can avoid direct AMM reserve impact, but introduces counterparty, settlement, concentration and disclosure risks. Require verified beneficial-owner independence, documented consideration and confirmed settlement. Do not count a transfer to a controlled or related wallet as an OTC exit.

### 6.5 Route comparison

For each route \(r\), compute:

\[
NetProceeds_r(q)=GrossProceeds_r(q)-Fees_r(q)-ImpactCost_r(q)-SettlementRiskCost_r(q)
\]

Compare routes on the same state snapshot and the same amount. The highest displayed price is not necessarily the route with the highest net proceeds or the greatest reduction in Dev's beneficial exposure.

## 7. When should Dev sell?

There is no universally optimal fixed price, market-cap multiple, elapsed time or percentage. The exit decision is a stochastic optimal-stopping and partial-liquidation problem.

At time \(t\), the engine compares:

1. The net value of selling a feasible tranche now.
2. The risk-adjusted expected value of retaining that tranche for a future decision.
3. The value of waiting for better information, when waiting does not violate a hard risk or mandate condition.

A finite-horizon value function is:

\[
V_t(s_t)=
\max_{a_t\in\mathcal A(s_t)}
\left[
R_t(a_t)-C_t(a_t)
+e^{-\rho\Delta t}
\mathbb E_t[V_{t+\Delta t}(s_{t+\Delta t})]
\right]
\]

where the action can sell part or all of the eligible inventory, hold, withdraw a permitted LP portion, or use a verified independent OTC route. The state transition includes pool impact, LP ownership, future unlocks, independent flow, costs and market regime.

The practical marginal rule is:

\[
\text{Sell a tranche when }
MV_{sell,t}^{net}
\geq
MV_{hold,t}^{risk-adjusted}
\]

where:

- \(MV_{sell,t}^{net}\) is the marginal net cash value achievable now through a permitted route.
- \(MV_{hold,t}^{risk-adjusted}\) is the expected discounted value of retaining the same marginal exposure, after uncertainty, tail risk, capital cost, future supply and feasible future execution are considered.

This is not a claim that the future price can be predicted exactly. It is a decision rule to compare current executable value with the distribution of future realizable value.

### 7.1 Inputs to the hold-versus-sell comparison

- Current executable proceeds, not only spot price.
- Independent buyer flow and its persistence/confidence.
- Quote reserve and sell-side executable depth.
- Price impact and expected execution slippage.
- Volatility, downside tail risk and external-reference basis.
- Dev beneficial ownership and LP share.
- Future vesting/unlock overhang and other known supply events.
- Project operating obligations and treasury cash requirements.
- LP fees expected to accrue, net of adverse selection and inventory risk.
- Probability of protocol, security, market or venue failure.
- Cost of waiting and opportunity cost of locked capital.

A strong real independent bid may increase the amount that can be sold with less impact. It does not justify manufacturing demand, hiding ownership or coordinating promotional activity around a treasury sale.

### 7.2 No forced full hold and no forced full exit

The optimal action may be a partial sale. The system must not assume either:

- Dev must hold 100% of its unlocked allocation to support the market; or
- Dev should sell 100% as soon as any target is reached.

The retained reserve is derived from explicit future obligations, authorized operating capital, LP commitments and risk limits. Inventory above that reserve is eligible for the hold-versus-sell optimizer, subject to vesting and integrity constraints.

### 7.3 What makes an exit window attractive?

The best exit window is not necessarily the highest displayed price. It is the point where a meaningful amount of inventory can be converted into settled quote assets at a favorable net price, while the risk-adjusted value of waiting is no longer better.

Evidence that can improve an exit window:

- Strong, sustained buy-side executable depth from the real pool and/or verified independent counterparties.
- Sufficient quote reserves to pay the intended sale without exceeding the approved impact budget.
- A pool price that is consistent with independent executable reference prices rather than a temporary isolated print.
- Healthy two-sided participation and low data uncertainty.
- A sale quantity that can be absorbed without breaching the approved post-sale depth and reserve floors.
- A current net proceeds estimate that exceeds the risk-adjusted continuation value for the tranche being considered.

Signals that must not be mistaken for an attractive exit window:

- A high marginal spot price with very little executable depth.
- A brief price spike unsupported by persistent independent flow.
- Volume created by LP events, internal transfers, controlled-wallet trades or related-party activity.
- A chart pattern or price level without a corresponding executable bid.
- A promotional attention spike when treasury ownership or planned sales are not properly disclosed.

Therefore, the engine should rank windows by **net executable proceeds, risk reduction and continuation value**, not by ATH detection or a fixed market-cap target. No model can guarantee that it sells at the ex-post peak.

## 8. Sale sizing and execution schedule

The amount sold in one decision cycle is constrained by:

\[
q_t\leq
\min(
H_t^{eligible},
q_t^{impact},
q_t^{route},
q_t^{mandate}
)
\]

where:

- \(H_t^{eligible}\): unlocked inventory available under the treasury mandate.
- \(q_t^{impact}\): maximum amount within the approved impact/slippage budget.
- \(q_t^{route}\): route capacity supported by current executable depth or a settled OTC agreement.
- \(q_t^{mandate}\): maximum authorized tranche under the disclosed treasury policy.

The execution scheduler may split a legitimate sale into bounded tranches to reduce execution cost and settlement risk. Splitting is not permission to disguise the beneficial owner, evade disclosure, create artificial activity or misrepresent the sale as unrelated demand.

The scheduler must stop or re-evaluate when:

- the price-impact or slippage budget is exceeded;
- independent depth materially deteriorates;
- the pool quote reserve or external venue capacity becomes insufficient;
- the reference price becomes stale or diverges beyond the approved band;
- the transaction state is uncertain;
- an unlock, ownership or authorization condition fails;
- a hard market-integrity or risk gate is triggered.

## 9. Lifecycle policy

The engine must evaluate exits in all lifecycle phases rather than assuming Dev can only sell after graduation.

| Phase | Relevant sale constraints | Decision focus |
|---|---|---|
| Bonding curve | Real quote reserve, curve fees, real-token reserve and completion mechanics | Whether any sale is feasible without violating the treasury mandate or distorting lifecycle accounting |
| Graduation | Migration state, pool initialization, LP lock/ownership and reserve reconciliation | Reconcile holdings before considering any sale; no assumption that migration price equals executable exit value |
| Early PumpSwap | Shallow or unstable depth, concentrated holders, high uncertainty | Small feasible tranches or wait; compare independent OTC capacity and pool impact |
| Mature market | More observable independent flow and potentially deeper liquidity | Optimize net proceeds, exposure reduction and capital recovery |
| Stress / impaired market | Collapsing depth, stale data, protocol risk or correlated exits | Pause discretionary execution when state is unreliable; use pre-authorized incident and treasury policies, not a panic market-impacting algorithm |

These are decision contexts, not automatic sale signals. A lifecycle label alone must never trigger a sale.

## 10. Dev exit and LP actions must be optimized jointly

A proportional LP withdrawal transfers the LP's underlying Token and quote assets to the wallet. It does not sell the Token and does not, by itself, reduce current beneficial Token exposure.

The orchestrator must compare complete action bundles:

- HOLD LP + HOLD free inventory.
- HOLD LP + sell eligible free inventory.
- Proportional REMOVE + HOLD released Token.
- Proportional REMOVE + sell a bounded amount through an approved independent route.
- Transfer a permitted LP claim to an independent buyer, if the protocol and mandate allow it.

For each bundle, compute:

- post-action free Token and quote balances;
- remaining LP claims and LP ownership share;
- current and future Delta/Gamma;
- pool depth and price impact;
- net cash proceeds;
- realized and unrealized PnL;
- capital reserves and future operating obligations;
- beneficial-owner concentration after the action.

Never label a withdrawal as an exit until the resulting Token exposure is actually transferred to an independent beneficial owner or otherwise disposed of under a valid mandate.

### 10.1 Proportional LP withdrawal is an inventory transfer, not an exit

Let Dev own fraction \(\alpha\) of total LP shares and withdraw fraction \(w\) of Dev's own LP shares. Define:

\[
\lambda=1-w\alpha
\]

The pool reserves after the withdrawal are:

\[
X_w=\lambda X,\qquad Y_w=\lambda Y
\]

Dev's remaining LP ownership fraction becomes:

\[
\alpha_w=\frac{\alpha(1-w)}{1-w\alpha}
\]

Dev receives \(w\alpha X\) Token and \(w\alpha Y\) quote asset into its wallet. Its remaining LP claim is \(\alpha(1-w)X\) Token and \(\alpha(1-w)Y\) quote asset. Therefore:

\[
H'_{Dev}+\alpha_w X_w=H_{Dev}+\alpha X
\]

\[
C'_{Dev}+\alpha_w Y_w=C_{Dev}+\alpha Y
\]

Before fees, transfer costs and external obligations, proportional withdrawal leaves Dev's beneficial Token and quote exposure unchanged. It changes asset location, pool depth and the ownership fractions of the remaining LPs. The simulator must not record the withdrawal itself as a token sale or treasury exit.

For \(\alpha=0.40\) and \(w=0.50\), \(\lambda=0.80\) and \(\alpha_w=0.25\). Dev has removed half of its own LP units; the remaining pool is 80% of its former reserve size, and Dev owns 25% of that remaining pool.

### 10.2 Sell-before-withdraw versus withdraw-before-sell

Compare the same token sale \(q\), the same starting pool \((X,Y)\), and the same proportional withdrawal fraction \(w\). First use a fee-free CPMM to isolate the ownership and depth effect.

**A — Sell first, then withdraw:**

\[
G_A=\frac{Yq}{X+q}
\]

Dev's net beneficial Token exposure reduction is:

\[
R^A_{Token}=(1-\alpha)q
\]

Dev's net quote exposure increase is:

\[
R^A_{quote}=(1-\alpha)G_A
\]

The proportional withdrawal after the swap does not change the post-swap spot price.

**B — Withdraw first, then sell:**

\[
G_B=\frac{\lambda Yq}{\lambda X+q}
\]

Dev's net beneficial Token exposure reduction is:

\[
R^B_{Token}=(1-\alpha_w)q
=\frac{1-\alpha}{\lambda}q
\]

Dev's net quote exposure increase is:

\[
R^B_{quote}=(1-\alpha_w)G_B
=\frac{(1-\alpha)Yq}{\lambda X+q}
\]

The post-sale marginal price ratio is:

\[
\frac{P'_B}{P_0}=
\left(\frac{\lambda X}{\lambda X+q}\right)^2
\]

By contrast, selling before withdrawing gives:

\[
\frac{P'_A}{P_0}=
\left(\frac{X}{X+q}\right)^2
\]

Since \(\lambda<1\), the same sale quantity consumes a larger fraction of the remaining pool after withdrawal. It creates more price impact and leaves less executable depth.

**Interpretation:** Withdraw-before-sell can show a larger owner-level quote gain because Dev has reduced its share of the pool before the swap. That is not free alpha or newly created market value. The remaining external LPs bear a larger share of the swap's reserve loss and price impact. The sequence must never be selected solely because it maximizes Dev's cash proceeds.

The orchestrator must enforce post-action depth floors, maximum marginal impact, sell-side executable-depth limits, ownership disclosure and LP/market-quality constraints. A legitimate risk-driven LP withdrawal may still be valid, but it does not grant permission to dump into the thinner pool. If the resulting sale fails quality or authorization gates, the valid action is to withdraw and hold, use a verified independent OTC route, or wait—not to force the AMM sale.

### 10.3 Fee-aware owner-level accounting

For a sell of \(q\) Token, define:

- \(G\): gross quote output along the AMM curve before fees;
- \(f_{total}\): total trader-side fee rate deducted from gross output;
- \(f_{LP}\): LP fee amount retained in effective pool reserves, expressed as a fraction of \(G\);
- \(D_{pool}=G(1-f_{LP})\): quote reserve debit after the LP-retained fee.

The trader receives:

\[
N=G(1-f_{total})
\]

If Dev owns fraction \(\alpha\) of the pool LP at the time of sale, its owner-level quote exposure change is:

\[
\Delta C_{Dev}=N-\alpha D_{pool}
=G[(1-f_{total})-\alpha(1-f_{LP})]
\]

This formula separates the seller's actual proceeds from the loss in Dev's own LP claim. It must use the fee split and effective-reserve semantics for the exact protocol version and transaction route. Creator/protocol fees paid out of the pool are not LP-retained reserve value.

For the current simplified simulator, \(f_{total}=f\) and \(f_{LP}=f\ell\), where \(\ell\) is the configured LP share. The full Pump.fun canonical fee model additionally needs separate creator, protocol and LP fee components and the active market-cap tier. Any creator fee entitlement must be tracked as a separate quote-asset receivable/cash flow, not added to pool reserves. LP fees already retained in reserves must not also be added as a second income item.

### 10.4 Numerical comparison

For an idealized fee-free example with \(X=1{,}000{,}000\) Token, \(Y=1{,}000\) SOL, \(\alpha=0.40\), \(w=0.50\), and \(q=100{,}000\) Token:

| Metric | Sell then withdraw | Withdraw then sell |
|---|---:|---:|
| Pool size at sale | 100% | 80% |
| Dev LP share at sale | 40% | 25% |
| Gross AMM quote output | 90.91 SOL | 88.89 SOL |
| Dev net quote exposure increase | 54.55 SOL | 66.67 SOL |
| Dev net Token exposure reduction | 60,000 | 75,000 |
| Post-sale marginal price decline | 17.36% | 20.99% |

The second sequence appears better for Dev's immediate owner-level cash result, but it imposes a larger price decline and leaves 20% less pool depth before the sale. The extra 12.12 SOL is a redistribution of value/risk through a more damaging trade against the remaining LPs, not a free increase in system-wide value. The market-quality gate must take precedence over that private cash metric.

The example is an analytical invariant test, not a recommended trading tactic. Actual PumpSwap execution must include fee tiers, creator/protocol/LP fee destinations, raw and effective quote reserves, transaction ordering, slippage and protocol-version semantics.

## 11. Disclosure, ownership and market-integrity controls

Every treasury exit policy must define:

- beneficial owner and controlled-wallet set;
- source of tokens and cost-basis method;
- locked/unlocked status and vesting schedule;
- authorized sale routes and maximum tranche limits;
- disclosure requirements and any legally applicable restrictions;
- treasury reserve requirements and intended use of proceeds;
- audit and reconciliation procedure.

Wallet clustering must be conservative and confidence-scored. A shared funder or common exchange source alone is not proof of common ownership. Conversely, a new wallet address alone is not proof of independent ownership.

The system records internal transfers separately from swaps, OTC settlements and LP transfers. Internal transfers do not reduce Dev beneficial ownership, do not count as genuine external distribution and do not create trade volume.

## 12. Integration with Market Making Decision Orchestrator

The Dev Treasury & Exit Engine is a proposal engine, not a transaction authority.

Every proposal must include:

- beneficial-owner aggregate and state version;
- free, locked, LP and controlled-wallet inventory;
- source-specific cost basis;
- eligible sale quantity and reason;
- route, gross proceeds and net proceeds estimate;
- price-impact, slippage and settlement-risk estimates;
- LP ownership fraction and net exposure reduction;
- disclosure/authorization status;
- expected post-action market quality and portfolio risk;
- proposal expiry and reconciliation requirements.

The Orchestrator applies this priority order:

1. Ownership, data, protocol, legal/mandate and market-integrity gates.
2. Vesting, capital authorization, reserve and portfolio-risk constraints.
3. Minimum acceptable market-quality and execution constraints.
4. Net realizable treasury proceeds and risk-adjusted continuation value.
5. Lowest unnecessary operational churn.

Treasury profit cannot override a hard integrity, authorization or risk constraint. Market-quality targets cannot force Dev to hold all tokens indefinitely; instead, the optimizer must choose a permitted route and disclose any remaining depth shortfall.

## 13. Simulator policy comparisons

The simulator must compare at least these policies under identical random seeds and market paths:

1. **No discretionary sale:** Hold all eligible inventory, subject only to required vesting and terminal valuation.
2. **Fixed vesting sale:** Existing dev_treasury_sale_fraction behavior; retain as a simple baseline, not the target algorithm.
3. **Fixed tranche schedule:** Predefined, disclosed sales at set intervals.
4. **Risk-threshold exit:** Sell only when inventory or tail-risk limits are breached, subject to execution constraints.
5. **Adaptive optimal-stopping exit:** Compare current net executable proceeds with risk-adjusted continuation value.
6. **Route-aware exit:** Compare AMM execution with verified independent OTC capacity and LP-claim disposition where supported.
7. **Capital-recovery policy:** Test recovery of actual invested capital separately from profit harvesting; do not treat return of LP principal as profit.

Do not optimize or select policies on one favorable seed. Use multiple independent seeds, calibrated cohorts and held-out launches.

### 13.1 Required outcome metrics

- Total net realized treasury proceeds.
- Realized PnL and terminal net liquidation value.
- Percentage of Dev beneficial exposure actually externalized.
- Remaining unlocked, locked and LP exposure.
- Sale VWAP and execution shortfall versus a defensible pre-trade reference.
- Pool price impact, post-sale executable depth and recovery.
- Treasury cash reserve and capital runway.
- LP fee income net of inventory loss and costs.
- Dev concentration and top-holder concentration.
- Number of tranches, failed transactions and unresolved settlements.
- Independent buyer/OTC counterparty concentration.
- Market-integrity violations: target is zero.

Report mean, median, p10, p90 and tail outcomes. A strategy with higher average proceeds but unacceptable tail loss, market impact or integrity violations is rejected.

## 14. Acceptance criteria

The Dev Treasury & Exit Engine is not accepted until:

1. Locked inventory cannot be sold before its configured valid unlock.
2. Controlled-wallet transfers do not reduce beneficial ownership or count as sales.
3. LP claims and wallet balances reconcile without double counting.
4. LP principal withdrawal is not counted as profit.
5. Cost basis remains attached to inventory through LP add/remove and wallet transfers.
6. Dev LP ownership is aggregated across controlled LP accounts.
7. A sale into a partly Dev-owned pool reports gross swap amount separately from net beneficial exposure reduction.
8. A 100%-Dev-owned idealized LP pool does not report a self-internalized swap as a net treasury exit.
9. AMM sale sizing respects actual fee-aware impact, slippage and quote-reserve constraints.
10. OTC proceeds are not realized until independent counterparty settlement is confirmed.
11. A stale or inconsistent state blocks discretionary treasury execution.
12. No self-trade, wash volume, artificial candle, deceptive coordination or hidden-wallet exit policy is rewarded.
13. Adaptive exit is compared against fixed-schedule and no-sale baselines on matched seeds.
14. Terminal valuation uses executable liquidation value, not marginal spot price.
15. Every sale proposal and confirmed result is auditable and reproducible.

## 15. Open research and implementation order

1. Extend the canonical state contract with beneficial-owner treasury inventory, cost basis, vesting, creator-fee receivables and route capacity.
2. Validate Pump curve and PumpSwap treasury sell transitions against protocol-specific fee and reserve mechanics, including separate creator, protocol and LP fee flows.
3. Validate sell-side fee retention in the simulator and pool-depth analytics; explicit reserve-delta regression tests now cover the simplified two-component model.
4. Add and validate partial LP withdrawal semantics and pro-rata LP cost-basis release.
5. Compare sell-before-remove and remove-before-sell under market-quality constraints, not private proceeds alone.
6. Implement the LP-ownership-aware net-exit accounting identity and test it against simulated swaps.
7. Add a route-aware sale capacity model for AMM and independent OTC execution.
8. Define the treasury reserve/obligation mandate and the risk-adjusted continuation-value model.
9. Implement the Dev Treasury & Exit Engine as a proposal generator.
10. Integrate it with Orchestrator hard gates and joint LP/exit action bundles.
11. Run matched-seed policy experiments, historical replay and held-out validation.
12. Keep adaptive exit in research/paper mode until all accounting, authorization, integrity and execution gates pass.

**Current implementation note:** The simulator now supports fractional LP withdrawal (REMOVE_LP amount is the fraction of the account's LP shares; zero preserves full withdrawal), pro-rata LP cost-basis release, and sell-side LP-fee retention in the simplified CPMM. The model remains a two-component LP/protocol fee abstraction and does not yet implement Pump's dynamic creator/protocol/LP fee tiers. The adaptive optimal-stopping engine, beneficial-owner exit ledger and route-aware treasury optimizer specified here are not yet implemented.

No live execution is authorized by this document.

