# Dev Treasury & Exit Intelligence

**Document type:** Treasury exit strategy and mathematical research specification  
**Version:** 0.1  
**Status:** Theory defined; adaptive policy, empirical calibration and simulator implementation remain open  
**Parent specification:** [Market Making & Market Quality System](MARKET_MAKING_MARKET_QUALITY.md)  
**Decision authority:** [Market Making Decision Orchestrator](DECISION_ORCHESTRATOR.md)  
**Capital allocation:** [Dev LP vs Treasury — Dynamic Capital Allocation](DEV_LP_TREASURY_ALLOCATION.md)  
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

### 7.4 Three different break-even tests

Do not collapse capital recovery, economic profitability and operating solvency into one “break-even” flag.

**A. Cash-capital recovery**

Let \(C_0^{cash}\) be all verified external quote capital contributed to the project: curve purchases, quote-asset LP contributions, launch/migration and paid operating costs. Do not treat a free genesis allocation as a cash contribution; keep its non-cash opportunity basis separately.

Define cumulative net capital returned:

\[
R_t^{capital}=
\sum_j R_{AMM,j}^{owner}
+\sum_j Proceeds_{OTC,j}^{settled}
+\sum_j Q_{LP,j}^{withdrawn}
+\sum_j F_{creator,j}^{external,claimed}
-\sum_j C_{return,j}
\]

where:

- \(R_{AMM}^{owner}\) is the consolidated beneficial-owner quote inflow from a sale, not gross wallet proceeds;
- \(Proceeds_{OTC}^{settled}\) is net consideration from a verified independent buyer after settlement;
- \(Q_{LP}^{released}\) is quote principal actually released from Dev's own LP claim; it is returned capital, not profit;
- \(F_{creator}^{external,claimed}\) is Creator Fee received from eligible independent trading activity and actually settled;
- \(C_{return}\) includes execution/settlement costs not already included in \(C_0^{cash}\).

A sale's own Creator Fee is netted into \(R_{AMM}^{owner}\) if Dev is entitled to it; do not add it a second time as external fee revenue. LP fees already embedded in the LP reserve claim are not a second cash receipt.

The cash-capital recovery ratio is:

\[
CRR_t=\frac{R_t^{capital}}{C_0^{cash}}
\]

when \(C_0^{cash}>0\). Nominal cash-capital break-even is reached when \(CRR_t\geq1\). This says capital has been returned through realized proceeds and released quote principal; it does **not** prove that the project is profitable or solvent.

**B. Economic break-even**

Define route-aware net liquidation value:

\[
NLV_t=C_t+\mathcal L_t(H_t^{free},H_t^{LP},H_t^{locked})
+R_t^{eligible}-L_t^{outstanding}
\]

where \(\mathcal L_t\) is executable liquidation value after fees, impact, route capacity and valid unlock restrictions; \(R_t^{eligible}\) is a separately valued eligible receivable not already included in cash or LP reserves; and \(L_t^{outstanding}\) is the liability/obligation ledger.

Then:

\[
EconomicSurplus_t=NLV_t+D_t^{owner}-C_0^{cash}-B_0^{noncash}
\]

where \(D_t^{owner}\) is cash already distributed to capital providers and \(B_0^{noncash}\) is an explicitly selected opportunity basis for non-cash genesis allocations. Purchased inventory basis must not be subtracted again if its purchase cash outflow is already included in \(C_0^{cash}\).

Economic break-even is \(EconomicSurplus_t\geq0\). Report the result both with and without optional non-cash opportunity basis so that a free allocation cannot silently make the project appear more profitable.

**C. Operating solvency**

\[
C_t^{available}\geq O_t^{committed}+C_t^{minimum\ reserve}
\]

A project can have recovered its initial capital historically and still lack enough available cash for future obligations. Conversely, it can be solvent while not yet having recovered its original capital. These are separate controls.

### 7.5 Pump fee schedule is a versioned input, not one fixed fee

The official [Pump.fun fee schedule](https://pump.fun/docs/fees) states that canonical PumpSwap fees depend on the token's quote-denominated market cap, calculated as current token price multiplied by 1 billion tokens. The published schedule was last updated 16 November 2026. Selected SOL-pair tiers are:

| Venue / market-cap tier | Creator | Protocol | LP | Total |
|---|---:|---:|---:|---:|
| Bonding curve | 0.300% | 0.950% | 0% | 1.250% |
| PumpSwap canonical, 0–420 SOL | 0.300% | 0.930% | 0.020% | 1.250% |
| PumpSwap canonical, 420–1,470 SOL | 0.950% | 0.050% | 0.200% | 1.200% |
| PumpSwap canonical, 98,240 SOL and above | 0.050% | 0.050% | 0.200% | 0.300% |
| PumpSwap non-canonical | 0% | 0.050% | 0.250% | 0.300% |
| PumpSwap canonical, custom pair | 0.050% | 0.050% | 0.200% | 0.300% |

USDC canonical pools use their own USDC-denominated thresholds; do not reuse the SOL thresholds. The complete tier table must be loaded from a versioned schedule rather than copied as one constant.

Important consequences:

1. The Creator Fee is not constant. In the published SOL canonical schedule it rises from 0.300% in the first tier to 0.950% in the 420–1,470 SOL tier, then declines as market cap rises.
2. The LP and Protocol components also change at the first tier boundary. Their actual reserve treatment must be taken from the active instruction/version.
3. Creator Fee belongs to the creator only when the creator is the designated beneficiary. If the coin uses Holder Rewards or a charity destination, do not book that amount as Dev Creator Fee income. Holder Rewards, if Dev separately qualifies as a holder, require their own eligibility and distribution-cost ledger.
4. Every fee is in the relevant quote asset. For multi-pool routes, Pump's published rules charge the Protocol Fee on the first pool and the Creator/Holder Rewards and LP Fee on the final pool; some interfaces may apply fee logic on every hop.
5. Pump's Platform Fee is separate from the pool fee schedule: the published rate is 0.45% without a referral code or 0.40% with one for Pump web/mobile trades, and it does not apply through Terminal or third-party interfaces. Third-party interface, router, priority and network costs remain separate route inputs.

The fee adapter must resolve, for each confirmed transaction:

- venue and instruction/program version;
- canonical versus non-canonical pool;
- pair asset and market-cap tier at the transaction's applicable state;
- Creator, Protocol and LP fee rates **and actual amounts**;
- creator-beneficiary mode: creator, Holder Rewards, charity or unknown;
- route/interface fees and each pool hop;
- quote asset in which each fee is collected;
- raw quote vault, signed virtual quote reserve and effective pricing reserve;
- slot, transaction signature and fee-schedule version.

The actual confirmed transaction and pool-state delta are authoritative. A theoretical rate table is a quote/forecast input, not a replacement for on-chain reconciliation.

#### Creator Fee volume sensitivity

If the applicable fee basis is approximated by eligible independent trade volume \(V_{eligible}\), the gross Creator Fee estimate is:

\[
F_C^{gross}\approx r_C V_{eligible}
\]

and the volume required for a target Creator Fee \(F_{target}\) is:

\[
V_{required}\approx\frac{F_{target}}{\eta r_C}
\]

For a 10 SOL target and full creator entitlement, this is approximately 3,333 SOL of eligible volume at 0.300%, 1,053 SOL at 0.950%, or 20,000 SOL at 0.050%. This is a sensitivity calculation, not a volume target. Use only genuine eligible external trades, actual fee basis and settled receipts. Dev's own sales and controlled-wallet turnover must not be presented as independent Creator Fee revenue. Holder Rewards and charity destinations are not Creator Fee income for Dev.


### 7.6 Fee-aware owner-level sale accounting

For one Dev sale, let:

- \(G\): gross quote output from the AMM curve before fees;
- \(F_C,F_P,F_L\): actual Creator, Protocol and LP fee amounts;
- \(F_R\): separate interface/router/platform charges;
- \(N=G-F_C-F_P-F_L-F_R\): quote received by the selling wallet in this simplified output-fee case;
- \(D_{eff}\): reduction in the pool's effective quote reserve;
- \(\alpha\): Dev's beneficial LP share immediately before the swap;
- \(\eta\): fraction of Creator Fee beneficially owned by Dev;
- \(q_w\): Token debited from Dev's wallet;
- \(q_p\): Token credited to the pool;
- \(P_{ref}\): independent executable reference price, not the post-trade local marginal price.

The consolidated owner-level quote change is:

\[
\Delta Q_{owner}=N-\alpha D_{eff}+\eta F_C-C_{other}
\]

The beneficial Token change is:

\[
\Delta H_{owner}=-q_w+\alpha q_p
\]

For a standard token transfer with no transfer fee, \(q_w=q_p=q\), so \(\Delta H_{owner}=-(1-\alpha)q\).

The immediate economic value change against the independent reference is:

\[
\boxed{\Delta NLV_{ref}=\Delta Q_{owner}+P_{ref}\Delta H_{owner}}
\]

In the simplified CPMM where only the LP fee is retained in the effective pricing reserve, \(D_{eff}=G-F_L\). PumpSwap V2 may use raw-vault and signed virtual-reserve adjustments, so production code must use the confirmed effective reserve delta rather than blindly applying this simplified identity.

If the fee basis is \(G\), \(F_i=r_iG\), and there are no separate route costs:

\[
\Delta Q_{owner}
=G[(1-r_C-r_P-r_L)-\alpha(1-r_L)+\eta r_C]
\]

This prevents three accounting errors:

- counting the full wallet output while ignoring Dev's own LP-funded share of the quote reserve;
- counting the Creator Fee as income when it belongs to holders or charity;
- adding LP fees as separate income when they are already reflected in the LP claim.

A Creator Fee generated by Dev's own sale is an internal transfer within the consolidated beneficial owner if Dev receives it; it offsets that fee cost but is not independent external trading revenue.

### 7.7 Worked example: a small sale under a real fee tier

Use an analytical PumpSwap canonical SOL-pair state:

- total supply: 1 billion tokens;
- \(X=100,000,000\) Token and \(Y=100\) SOL;
- \(P_{ref}=Y/X=0.000001\) SOL per Token, giving a 1,000 SOL market cap; assume the independent executable reference agrees with this pre-trade pool spot for the isolated example;
- \(q=2,500,000\) Token, or 2.5% of the starting Token reserve;
- Dev owns \(\alpha=40\%\) of the LP;
- fee tier: 420–1,470 SOL, with Creator 0.950%, Protocol 0.050%, LP 0.200%;
- assume \(F_i=r_iG\), Creator Fee is actually payable to Dev (\(\eta=1\)), and exclude app/router/network costs for this isolated example.

The curve output is:

\[
G=\frac{100\times2,500,000}{100,000,000+2,500,000}
=2.439024\ SOL
\]

Fee allocation:

| Component | SOL |
|---|---:|
| Creator Fee | 0.023171 |
| Protocol Fee | 0.001220 |
| LP Fee retained | 0.004878 |
| Seller wallet output | 2.409756 |

The effective quote reserve debit in this simplified model is:

\[
D_{eff}=G-F_L=2.434146\ SOL
\]

Dev's consolidated quote increase is:

\[
\Delta Q_{owner}
=2.409756-0.40(2.434146)+0.023171
=1.459268\ SOL
\]

Its beneficial Token exposure falls by:

\[
(1-0.40)\times2,500,000=1,500,000\ Token
\]

At the independent reference price, the value of that reduced exposure is 1.5 SOL. Thus:

\[
\Delta NLV_{ref}=1.459268-1.500000
=-0.040732\ SOL
\]

The post-trade marginal-price decline is approximately 4.814%. Gross curve VWAP is 2.439% below the pre-trade reference; the seller's net output after the 1.20% pool fee is 3.610% below that reference, before any separate interface or network costs.

This example demonstrates that the sale converts some Token exposure into quote cash at a small execution cost; it does not create free wealth. If Dev is not entitled to the Creator Fee, the same example's net value change is approximately -0.063902 SOL. All figures are model outputs under the stated fee-basis assumption, not a live quote or a recommendation to trade.

### 7.8 Solve the cash break-even quantity without violating depth

For a single constant-fee-tier CPMM sale, assume:

- no transfer fee, so \(q_w=q_p=q\);
- \(D_{eff}=G(1-r_L)\);
- all fee rates use the same gross basis \(G\);
- \(\alpha\) and fee tier remain constant during the transaction;
- route charges are split into a proportional rate \(r_R\) and fixed cost \(C_f\).

Define:

\[
k=(1-r_C-r_P-r_L-r_R)-\alpha(1-r_L)+\eta r_C
\]

Then the net owner-level quote recovery from the sale is:

\[
R_{AMM}^{owner}(q)=k\frac{Yq}{X+q}-C_f
\]

Let \(S\) be the remaining cash-capital recovery shortfall after all previously settled eligible proceeds and released LP quote principal. If \(k>0\), define:

\[
A=\frac{S+C_f}{k}
\]

The idealized quantity required to close that shortfall is:

\[
\boxed{q_{BE}=\frac{XA}{Y-A}}
\]

This solution exists only if \(0<A<Y\). It is not permission to trade that quantity.

The maximum quantity under a marginal-price decline limit \(\delta\) is found from:

\[
(1-\delta)t^2+[2(1-\delta)-r_L]t-\delta=0
\]

where \(t=q/X\), and \(q_{impact}^{max}=Xt\). The actual permitted quantity is:

\[
q_{max}=\min(q_{impact}^{max},q_{route},q_{eligible},q_{mandate})
\]

If \(q_{BE}>q_{max}\), the cash shortfall cannot be closed by one permitted sale in the current state. Do not exceed the impact/depth limit. Re-evaluate after genuinely new market information and state changes, or assess a verified independent route and the treasury's funding/obligation plan.

For the worked fee-tier state above, \(r_C=0.0095\), \(r_P=0.0005\), \(r_L=0.002\), \(\eta=1\), \(\alpha=0.40\), and \(r_R=0\), so \(k=0.5983\). If the remaining recovery shortfall is \(S=5\) SOL and fixed costs are zero, the closed-form result is approximately \(q_{BE}=9.119\) million Token. That quantity implies roughly 16.0% marginal-price impact, well above the illustrative 5% cap. The permitted 5% impact quantity is only about 2.601 million Token and recovers approximately 1.516 SOL at the owner level under these assumptions. The correct result is “the 5 SOL target is not reachable in one compliant sale in this state,” not “increase the sale until the target is met.”


For fee-tier crossings, multiple routes, PumpSwap virtual-reserve semantics or changing LP ownership, solve the exact state transition numerically using the versioned fee adapter. Do not extrapolate the constant-tier closed form across a tier boundary.

### 7.9 Partial liquidation as a marginal optimal-stopping problem

Let \(M_{hold,t}\) be the risk-adjusted continuation value per unit of **net beneficial Token exposure**. It is derived from the distribution of future executable liquidation proceeds after discounting, tail-risk charge, future unlock/supply, venue failure and capital carrying costs. It is not the displayed spot price.

Under the same simplified constant-tier assumptions, the marginal owner-level quote proceeds per unit of net beneficial Token exposure sold are:

\[
M_{sell}(q)=
\frac{kYX}{(1-\alpha)(X+q)^2}
\]

An interior partial-sale solution satisfies:

\[
M_{sell}(q^*)=M_{hold,t}
\]

and therefore:

\[
\boxed{
q^*=
\sqrt{\frac{kYX}{(1-\alpha)M_{hold,t}}}-X
}
\]

Clamp this analytical benchmark to \([0,q_{max}]\), and use it only when \(k>0\), \(\alpha<1\), and the assumptions remain valid. If the result is zero or negative, HOLD is preferred by this simplified marginal test. If it exceeds \(q_{max}\), the quality/risk limit binds; do not automatically execute the remainder later.

Example using the same \(X,Y,\alpha,k\) above, with an illustrative risk-adjusted continuation value \(M_{hold}=0.95P_{ref}\):

\[
q^*\approx2.452\ million\ Token
\]

This is below the 5% impact cap of approximately 2.601 million Token. The model would then re-evaluate after the confirmed state transition. If \(M_{hold}=P_{ref}\), the unconstrained result is negative and the model prefers HOLD. If \(M_{hold}=0.90P_{ref}\), the unconstrained result exceeds the impact cap, so the cap—not the target price—binds.

The \(M_{hold}\) values above are controlled assumptions for demonstrating the equation, not forecasts. In production, use scenario distributions, calibrated independent flow and held-out launch data.

A tranche is a new decision after a confirmed state update, not a fixed instruction to keep selling. In a fee-free CPMM with no intervening state changes, splitting the same aggregate Token input does not create additional aggregate depth or remove the curve's total price impact. Real Pump fee tiers, retained fees, rounding, per-transaction costs and intervening independent flow require exact sequential replay.

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
- \(F_C,F_P,F_L\): actual Creator, Protocol and LP fee amounts;
- \(F_R\): separate interface/router/platform charges;
- \(N=G-F_C-F_P-F_L-F_R\): quote received by the selling wallet in this simplified output-fee case;
- \(D_{eff}\): reduction in the pool's effective quote reserve;
- \(\alpha\): Dev's beneficial LP share immediately before the swap;
- \(\eta\): fraction of Creator Fee beneficially owned by Dev;
- \(q_w\): Token debited from Dev's wallet;
- \(q_p\): Token credited to the pool.

The consolidated owner-level quote change is:

\[
\Delta Q_{owner}=N-\alpha D_{eff}+\eta F_C-C_{other}
\]

The beneficial Token change is:

\[
\Delta H_{owner}=-q_w+\alpha q_p
\]

For a standard token transfer with no transfer fee, \(q_w=q_p=q\), so \(\Delta H_{owner}=-(1-\alpha)q\). Against an independent executable reference price \(P_{ref}\), the immediate economic value change is:

\[
\Delta NLV_{ref}=\Delta Q_{owner}+P_{ref}\Delta H_{owner}
\]

In the simplified CPMM where only the LP fee is retained in the effective pricing reserve, \(D_{eff}=G-F_L\). PumpSwap V2 may use raw-vault and signed virtual-reserve adjustments, so production code must use the confirmed effective reserve delta rather than blindly applying this simplified identity.

If the fee basis is \(G\), \(F_i=r_iG\), and there are no separate route costs:

\[
\Delta Q_{owner}
=G[(1-r_C-r_P-r_L)-\alpha(1-r_L)+\eta r_C]
\]

A Creator Fee generated by Dev's own sale is an internal transfer within the consolidated beneficial owner if Dev receives it; it offsets that fee cost but is not independent external trading revenue. Do not add LP fees separately when they are already reflected in the LP reserve claim.

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
16. Cash-capital recovery is calculated from net beneficial-owner proceeds and released LP quote principal, not gross wallet swap output alone.
17. Cash-capital recovery, economic break-even and operating solvency are reported as three separate tests.
18. Creator Fee is attributed only to its actual beneficiary; Holder Rewards and charity flows are not Dev Creator Fee income.
19. Fee schedules are selected by venue, pair, tier, instruction/version, route and slot; confirmed fee amounts reconcile to chain data.
20. A calculated break-even quantity or optimal tranche never overrides impact, depth, reserve, vesting, ownership or market-integrity constraints.

## 15. Open research and implementation order

1. Extend the canonical state contract with beneficial-owner treasury inventory, cost basis, vesting, creator-fee receivables, cash-capital contributions/returns and route capacity.
2. Build a versioned Pump fee adapter for Bonding Curve, canonical/non-canonical PumpSwap, SOL/USDC/custom pairs, multi-hop routes and interface fees; preserve slot-specific effective-reserve semantics.
3. Implement separate cash-capital recovery, economic NLV and operating-solvency ledgers; reconcile LP principal, creator-fee entitlement and LP fees without double counting.
4. Implement the constant-tier break-even solver and fee-aware impact cap as analytical baselines; use a numerical solver for tier/route/reserve transitions.
5. Calibrate (M_{hold}) from independent executable flow, historical cohorts and tail-risk scenarios; validate partial-liquidation policy on held-out launches.
6. Validate Pump curve and PumpSwap treasury sell transitions against protocol-specific fee and reserve mechanics, including separate creator, protocol and LP fee flows.
7. Validate sell-side fee retention in the simulator and pool-depth analytics; explicit reserve-delta regression tests now cover the simplified two-component model.
8. Add and validate partial LP withdrawal semantics and pro-rata LP cost-basis release.
9. Compare sell-before-remove and remove-before-sell under market-quality constraints, not private proceeds alone.
10. Implement the LP-ownership-aware net-exit accounting identity and test it against simulated swaps.
11. Add a route-aware sale capacity model for AMM and independent OTC execution.
12. Define the treasury reserve/obligation mandate and the risk-adjusted continuation-value model.
13. Implement the Dev Treasury & Exit Engine as a proposal generator.
14. Integrate it with Orchestrator hard gates and joint LP/exit action bundles.
15. Run matched-seed policy experiments, historical replay and held-out validation.
16. Keep adaptive exit in research/paper mode until all accounting, authorization, integrity and execution gates pass.

No live execution is authorized by this document.

