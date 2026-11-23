# Dev LP vs Treasury — Dynamic Capital Allocation

**Document type:** Portfolio allocation and LP economics research specification  
**Version:** 0.1  
**Status:** Analytical baseline defined; calibrated allocator and simulator implementation remain open  
**Parent specification:** [Market Making & Market Quality System](MARKET_MAKING_MARKET_QUALITY.md)  
**Decision authority:** [Market Making Decision Orchestrator](DECISION_ORCHESTRATOR.md)  
**Related specifications:** [Dev Treasury & Exit Intelligence](DEV_TREASURY_EXIT.md), [PumpSwap Pool Microstructure](POOL_MICROSTRUCTURE.md)  
**Scope:** Pump.fun bonding curve → graduation → fixed PumpSwap CPMM; spot-only assets, no perpetual or options hedging

> This is a research and risk-management model. It does not authorize live execution, self-trading, wash volume, artificial price/volume activity, concealed beneficial ownership, or deceptive treasury exits. Only genuine independent trading activity may be used to estimate fee revenue.

---

## 1. Research question

The allocator decides how much of Dev's beneficially owned capital should remain in:

1. **LP:** a pro-rata claim on the PumpSwap pool, earning the LP portion of genuine swap fees while carrying inventory and adverse-selection risk;
2. **Free Token Treasury:** unlocked Token held outside the pool, retaining directional upside and downside;
3. **Quote Treasury:** SOL/USDC held outside the pool, preserving operating runway and the option to deploy later.

Creator Fee is tracked as a separate project cash flow/receivable. It is not automatically LP yield and must not be used to justify an LP allocation unless a measured increase in genuine eligible volume is causally attributable to additional depth.

The target is not maximum LP TVL or maximum fee income. It is the highest risk-adjusted, executable net asset value subject to capital, liquidity, market-integrity and operating-reserve constraints.

## 2. Consolidated asset ledger

At time \(t\), define:

- \(C_t\): free quote asset in the treasury;
- \(H_t\): free, unlocked Token inventory;
- \(P_t\): independent executable reference price in quote units per Token;
- \(X_t,Y_t\): total pool Token and effective quote reserves;
- \(\alpha_t\): Dev's beneficial share of total LP shares;
- \(R_{C,t}^{accrued}\): Creator Fee accrued but not yet swept/claimed;
- \(R_{C,t}^{settled}\): Creator Fee actually received;
- \(L_t\): outstanding liabilities and committed obligations.

The consolidated net liquidation value is:

\[
NLV_t=C_t+H_tP_t+\mathcal V_{LP,t}
+\mathcal V_{C,t}^{receivable}-L_t
\]

where \(\mathcal V_{LP,t}\) is the executable value of Dev's actual LP claim and \(\mathcal V_{C,t}^{receivable}\) is a separately haircut-valued eligible receivable. Do not add LP fees again if they are already retained in pool reserves and reflected in the LP claim. Do not count an accrued Creator Fee as both a receivable and settled cash.

The portfolio's first-order Token exposure is:

\[
\Delta_{Token,t}=H_t+\alpha_tX_t
\]

This is the free Token inventory plus the Token amount economically represented by Dev's LP claim. It is not the same as the Dev wallet balance.

## 3. Constant-product LP payoff and inventory Greeks

For a fee-free constant-product pool:

\[
K=XY,\qquad P=\frac{Y}{X}
\]

At a given reference price \(P\):

\[
X(P)=\sqrt{\frac K P},\qquad
Y(P)=\sqrt{KP}
\]

If Dev owns LP fraction \(\alpha\), its reserve claim is:

\[
X_D=\alpha\sqrt{\frac K P},\qquad
Y_D=\alpha\sqrt{KP}
\]

and its quote-denominated mark-to-market value is:

\[
\boxed{V_{LP,D}(P)=2\alpha\sqrt{KP}}
\]

The LP's first and second price sensitivities are:

\[
\Delta_{LP}=\frac{\partial V_{LP,D}}{\partial P}
=\alpha\sqrt{\frac K P}=\alpha X
\]

\[
\Gamma_{LP}=\frac{\partial^2V_{LP,D}}{\partial P^2}
=-\frac{\alpha}{2}\sqrt K P^{-3/2}
=-\frac{\alpha X}{2P}
\]

Consequences:

- LP has positive Token Delta, but its Token inventory falls as price rises and grows as price falls.
- LP has negative Gamma: it sells some Token into rises and accumulates Token into declines.
- Adding or removing a proportional LP position changes Gamma and pool depth, but does not by itself change the portfolio's current beneficial Token quantity at the instant of the action.
- Removing LP is an inventory transfer, not a Token sale. Actual Token exposure is reduced only by a valid disposition to an independent beneficial owner or another permitted disposal.

The portfolio Delta is:

\[
\Delta_{portfolio}=H+\alpha X
\]

A risk engine must track Delta and Gamma separately. A low wallet Token balance does not imply low economic Token exposure.

### 3.1 Impermanent loss benchmark

Let \(r=P_1/P_0\) be the price ratio since LP entry. Ignoring fees and external deposits/withdrawals, the LP value relative to simply holding its initial Token/quote basket is:

\[
IL(r)=\frac{2\sqrt r}{1+r}-1
\]

This is a benchmark comparison, not a separate cash expense. It must not be subtracted again if the portfolio's actual LP reserve value has already been marked to market.

## 4. LVR: the first-order cost of passive liquidity

Loss-versus-rebalancing (LVR) compares a passive CFMM LP with a strategy that replicates the LP's inventory changes by trading at the external reference price. In the continuous-time, frictionless-arbitrage, constant-product baseline, instantaneous LVR as a fraction of pool value is one eighth of instantaneous price variance. See [Milionis et al., Automated Market Making and Loss-Versus-Rebalancing](https://arxiv.org/abs/2208.06046).

For Dev's LP claim value \(K_D=\alpha\cdot TVL\):

\[
\boxed{LVR_D\approx\frac18K_D\sigma^2\,dt}
\]

where \(\sigma\) is annualized/continuous volatility and \(dt\) uses the same time unit. For a one-day discrete screening calculation, use the realized one-day return standard deviation \(\sigma_d\):

\[
LVR_{D,day}\approx\frac18K_D\sigma_d^2
\]

This is a first-order analytical baseline, not a calibrated PumpSwap forecast. Meme-token jumps, block latency, stale external prices, concentrated flow, pool outages and transaction costs can make realized LP losses worse. Add a separately calibrated jump/operational-risk charge only if it does not duplicate losses already captured in LVR or the scenario PnL.

**Do not add IL and LVR as two independent losses.** They use different comparison portfolios. Report IL as the HODL-relative diagnostic and LVR as the rebalancing-relative adverse-selection diagnostic. Use actual NLV changes for the optimizer.

## 5. PumpSwap fee economics: LP Fee and Creator Fee are different businesses

The official [Pump.fun fee schedule](https://pump.fun/docs/fees), last updated 16 November 2026, defines a tiered schedule for canonical SOL/USDC PumpSwap pools. Selected SOL-pair tiers:

| Canonical SOL market-cap tier | Creator | Protocol | LP | Total |
|---|---:|---:|---:|---:|
| 0–420 SOL | 0.300% | 0.930% | **0.020%** | 1.250% |
| 420–1,470 SOL | 0.950% | 0.050% | **0.200%** | 1.200% |
| 1,470–2,460 SOL | 0.900% | 0.050% | **0.200%** | 1.150% |
| 98,240 SOL and above | 0.050% | 0.050% | **0.200%** | 0.300% |
| Non-canonical PumpSwap | 0% | 0.050% | **0.250%** | 0.300% |

The full SOL and USDC tier tables, custom-pair rules, route behavior and beneficiary rules are in the official fee schedule. USDC thresholds are not interchangeable with SOL thresholds.

Key implications:

1. The LP component in the first canonical SOL tier is 0.020%; at 420 SOL it becomes 0.200%, a tenfold increase. The total fee falls slightly, but the LP share rises.
2. Creator Fee is a separate flow. In the 420–1,470 SOL tier it is 0.950%, not 0.200%.
3. Creator Fee belongs to Dev only when Dev is the actual designated beneficiary. Holder Rewards and charity destinations are not Dev Creator Fee income.
4. A non-canonical pool has no Creator Fee under the published schedule and a 0.250% LP fee.
5. Fee rates are determined by venue, pair asset, market-cap tier, route and active program/instruction version. The allocator must not use one hard-coded fee rate.

### 5.1 LP Fee income

Let:

- \(f_L(t)\): LP fee rate active for the relevant pool and transaction;
- \(V_t^{eligible}\): genuine quote-denominated swap volume eligible for the pool's LP fee;
- \(\alpha_t\): Dev's LP ownership share.

A first-order Dev LP fee accrual estimate is:

\[
F_{LP,D}\approx\alpha_t f_L(t)V_t^{eligible}
\]

The exact ledger must use confirmed fee amounts and reserve deltas. Where LP fees are retained in pool reserves, their value is already part of the LP claim; this formula is an attribution view, not a second asset to add to NLV.

### 5.2 Creator Fee income

If Dev is the actual Creator Fee beneficiary:

\[
F_{C,D}=\eta_C\sum_t r_C(t)V_{C,t}^{eligible}
\]

where \(\eta_C\) is Dev's actual beneficiary share and \(r_C(t)\) is the applicable Creator Fee rate. \(V_C^{eligible}\) must be based on genuine eligible transactions, not internal transfers or controlled-wallet turnover.

Creator Fee is not a return on LP capital. It is project/creator revenue that may exist even when Dev owns no LP. Attribute only the incremental Creator Fee caused by additional LP depth if a credible counterfactual shows that additional depth increased genuine eligible volume.

### 5.3 Accrued is not settled

For newer Pump/PumpSwap trade instructions, Protocol and Creator Fees can remain recorded in the curve/pool until a sweep instruction; LP fees continue to enter pool reserves on each trade. Creator Fee is only moved to the creator vault after sweep_creator_fee, then claimed/distributed. The trade event records the fee when charged; the sweep event records payout. Do not count both as income. See [Pump's SWEEP_FEES instructions](https://github.com/pump-fun/pump-public-docs/blob/main/docs/instructions/SWEEP_FEES.md).

The ledger must keep separate fields for:

- fee charged/accrued;
- fee swept to the beneficiary vault;
- fee claimed/settled to treasury;
- fee distributed to team/holders/charity;
- claim, rent, network and priority costs.

An accrued fee receivable may be haircut for settlement delay, beneficiary uncertainty, distribution obligations and claim costs.

## 6. LP profitability screening rule

Let:

- \(T\): total pool TVL in quote units;
- \(V\): genuine quote-denominated swap volume over the same time window;
- \(\tau=V/T\): pool turnover over that window;
- \(f_L\): LP fee rate;
- \(\sigma_d\): realized one-day standard deviation of log returns;
- \(c_d\): other daily costs per unit of Dev LP capital, excluding LVR already counted.

The first-order daily LP excess return over the rebalancing benchmark is:

\[
\boxed{r_{LP}^{excess}\approx f_L\tau-\frac{\sigma_d^2}{8}-c_d}
\]

A necessary screening condition for LP fees to compensate the diffusion LVR baseline is:

\[
\boxed{\tau^*\approx\frac{\sigma_d^2/8+c_d}{f_L}}
\]

This is not a standalone ADD signal. It ignores directional risk, jumps, changing fee tiers, liquidity shocks, and the value of the alternative treasury allocation. The portfolio optimizer must still evaluate scenario NLV and hard risk constraints.

### 6.1 Fee/volatility break-even turnover

Ignoring all additional costs, the following daily turnover is needed merely to offset the continuous-time LVR baseline:

| Daily realized volatility | LP fee 0.020% | LP fee 0.200% | LP fee 0.250% |
|---:|---:|---:|---:|
| 10% | 6.25x TVL | 0.625x TVL | 0.50x TVL |
| 20% | 25.00x TVL | 2.50x TVL | 2.00x TVL |
| 30% | 56.25x TVL | 5.625x TVL | 4.50x TVL |
| 50% | 156.25x TVL | 15.625x TVL | 12.50x TVL |

This makes a crucial distinction: **high trading volume alone does not make LP attractive**. Volume must be high relative to TVL and volatility. At the first canonical SOL tier, the 0.020% LP fee requires very high turnover to offset even the diffusion baseline. Above 420 SOL, the 0.200% LP fee materially changes the hurdle. Jumps and adverse selection can raise the real hurdle further.

## 7. Marginal value of adding Dev LP capital

The average LP fee yield does not tell us whether the next unit of Dev capital should enter the pool. Additional Dev LP capital increases Dev's ownership share but may also expand the pool and change genuine volume.

Let:

- \(K_D\): Dev's current LP claim value;
- \(E\): external LP capital;
- \(T=K_D+E\): total LP capital/TVL in quote-equivalent units;
- \(\alpha=K_D/T\);
- \(V(T)\): genuine fee-eligible volume as a function of total pool depth;
- \(\epsilon_V=\frac{d\ln V}{d\ln T}\): local volume elasticity to pool depth;
- \(f_L\): locally constant LP fee rate within the current fee tier.

Dev's LP fee accrual is:

\[
F_D(K_D)=\frac{K_D}{K_D+E}f_LV(K_D+E)
\]

Differentiating gives the marginal fee capture from one additional unit of Dev LP capital:

\[
\boxed{
\frac{dF_D}{dK_D}
=f_L\frac VT(1-\alpha+\alpha\epsilon_V)
}
\]

The marginal LVR cost per unit of Dev LP capital is approximately \(\sigma_d^2/8\). Therefore:

\[
\boxed{
M_{LP}=f_L\tau(1-\alpha+\alpha\epsilon_V)
-\frac{\sigma_d^2}{8}-c_d
}
\]

Interpretation:

- If \(\epsilon_V=0\), deeper liquidity does not increase volume; added Dev capital mainly dilutes fee ownership across a larger pool.
- If \(0<\epsilon_V<1\), additional depth increases volume, but less than proportionally.
- If \(\epsilon_V=1\), volume scales proportionally with depth and marginal fee capture equals the average fee yield.
- If \(\epsilon_V>1\), depth has a strong positive effect on genuine volume. This must be established empirically, not assumed.

The allocator should ADD only if \(M_{LP}\) exceeds the risk-adjusted shadow value of the alternative use of the same Token/quote assets and all market-quality, capital and risk constraints pass. If the fee tier changes at the current market-cap boundary, recompute on both sides of the tier; do not differentiate through a discontinuous rate as if it were smooth.

### 7.1 Creator Fee synergy is a separate marginal term

If additional LP depth demonstrably increases genuine eligible volume that earns Creator Fee for Dev, define a separate eligible-volume elasticity \(\epsilon_C\). The incremental project-level Creator Fee contribution per unit of additional Dev LP capital is:

\[
M_C^{incremental}=\eta_Cr_C\tau_C\epsilon_C
\]

where \(\tau_C=V_C/T\). Add this to a **project-wide** capital allocation objective only when the causal depth-to-volume effect is supported by data. Do not add the Creator Fee on baseline volume to LP yield; it exists independently of Dev LP ownership.

## 8. Portfolio-level capital allocation

Let \(B\) be the investable quote-equivalent capital budget, excluding restricted/locked assets and separately valued receivables. Define:

- \(K_L\): Dev's LP claim value;
- \(K_H=H P\): free unlocked Token value;
- \(K_C=C\): free quote Treasury.

The capital identity is:

\[
K_L+K_H+K_C=B
\]

For a balanced CPMM, adding LP with total quote-equivalent value \(\Delta K_L\) requires approximately:

\[
\Delta Token=\frac{\Delta K_L}{2P},\qquad
\Delta Quote=\frac{\Delta K_L}{2}
\]

This reclassifies existing assets into an LP claim; it does not create new portfolio capital or change current beneficial Token quantity at the instant of a proportional deposit. It does increase negative Gamma and changes pool depth.

At each decision time, select a feasible action bundle \(a_t\) to maximize:

\[
\max_{a_t}
E_t[\Delta NLV_{t:t+H}]
-\lambda CVaR_{\beta}(-\Delta NLV)
-\gamma C_{lockup}
-\rho C_{operations}
\]

subject to:

\[
\begin{aligned}
K_L+K_H+K_C&=B\\
K_C&\geq K_{operating}^{min}+K_{committed}\\
Impact(a_t)&\leq Impact^{max}\\
Depth_{buy/sell}(a_t)&\geq Depth^{min}_{buy/sell}\\
CVaR_{\beta}(Loss(a_t))&\leq B_{tail}\\
|\Delta_{Token}(a_t)|&\leq Exposure^{max}
\end{aligned}
\]

The exact constraints also include vesting, beneficial ownership, protocol compatibility, authorized capital, data freshness and market-integrity gates. A return optimizer cannot trade away a hard constraint.

The objective must mark LP reserves, free Token, quote Treasury, accrued/settled Creator Fee and liabilities exactly once. Do not add LP Fee income on top of reserve value if it is already retained in the pool.

## 9. Dynamic policy by observed market state

Regime labels are inputs, not automatic trade triggers. The allocator should use realized volatility, genuine independent turnover, executable depth, price/reference basis, flow concentration, LP ownership and data quality.

| Observed condition | Capital-allocation response | Reason |
|---|---|---|
| Low volatility + persistent genuine turnover + adequate depth | Consider ADD/HOLD if marginal LP economics beat the alternative | Fees may compensate for LVR |
| High volatility + weak turnover | Reduce new LP deployment; preserve quote reserve | LVR can dominate fee capture |
| High volatility + high turnover | Run fee/LVR and jump-stress comparison; do not infer profitability from volume | High volume can still be toxic |
| Strong uptrend | Recompute LP inventory and total Token Delta; keep free Token only if directional exposure is within mandate | CPMM LP sells Token into rises |
| Sustained decline / correlated sells | Stop adding LP if Token inventory or tail-risk limits approach; consider partial REMOVE to reduce future Gamma | LP accumulates Token into declines; REMOVE alone does not sell it |
| Thin pool / deteriorating external depth | Enforce minimum depth and impact budgets; avoid extracting liquidity solely to improve Dev's private exit proceeds | Remaining LPs and users bear the depth loss |
| Stale price, incomplete events or reserve mismatch | OBSERVE / PAUSE discretionary actions | Do not allocate capital on unreliable state |

The action set remains HOLD, OBSERVE, ADD_LP_PRO_RATA, REMOVE_LP_PRO_RATA, PAUSE_NEW_ACTIONS, RESUME_WITH_LIMITS, and separately authorized treasury dispositions. ADD/REMOVE and sale proposals must be evaluated as a joint state transition where they interact.

## 10. Worked daily screening example

Assume a PumpSwap canonical SOL pool in the 420–1,470 SOL tier:

- total pool TVL: 100 SOL-equivalent;
- Dev LP claim: 20 SOL-equivalent, so \(\alpha=20\%\);
- external LP claim: 80 SOL-equivalent;
- genuine eligible pool volume: 300 SOL/day, so \(\tau=3x\);
- daily realized volatility: \(\sigma_d=20\%\);
- LP fee rate: \(f_L=0.200\%\);
- ignore other costs for this first-order example.

Dev's LP fee accrual estimate:

\[
F_{LP,D}=0.20\times0.002\times300=0.12\ SOL/day
\]

Dev's diffusion LVR estimate:

\[
LVR_D=\frac18\times20\times0.20^2=0.10\ SOL/day
\]

First-order LP excess over the rebalancing benchmark:

\[
0.12-0.10=+0.02\ SOL/day
\]

If the same pool were in the 0–420 SOL tier, the LP fee rate would be 0.020%:

\[
F_{LP,D}=0.20\times0.0002\times300=0.012\ SOL/day
\]

Then:

\[
0.012-0.10=-0.088\ SOL/day
\]

This shows how the LP component of the fee schedule changes the LP economics even when volume and volatility remain unchanged.

At the 420–1,470 SOL tier, the separate Creator Fee is 0.950%. If all 300 SOL/day is genuine eligible volume and Dev is the actual beneficiary, gross Creator Fee accrual is:

\[
F_{C,D}=0.0095\times300=2.85\ SOL/day
\]

That 2.85 SOL is **not** the return on Dev's 20 SOL LP claim. It is separate Creator Fee revenue. It may be accrued but not yet swept/claimed, and it is unavailable to Dev if the beneficiary mode is Holder Rewards or charity. It must not be used to claim that the LP position itself earned 2.97 SOL/day.

The example is a screening calculation, not a forecast. It assumes the full stated volume is eligible, the fee tier is constant during the day, and the diffusion LVR approximation is adequate. Actual PumpSwap accounting must reconcile instruction-level fees, quote reserves and confirmed external flow.

## 11. State variables and calibration requirements

The allocator requires a time-aligned state snapshot containing:

- effective pool reserves, raw quote vault and signed virtual quote reserve;
- LP shares, beneficial owner, Dev LP fraction and locked/unassigned LP shares;
- genuine buy/sell quote volume by transaction and route;
- actual LP fee amounts and the active fee tier per transaction;
- Creator Fee beneficiary mode, accrued amount, swept amount, claimed amount and distributions;
- external reference price, basis, realized volatility at multiple horizons and jump observations;
- executable buy/sell depth at approved impact bands;
- free, locked and LP Token inventory plus cost basis;
- quote Treasury, operating obligations and minimum reserve;
- event completeness, latency, duplicate/drop status and state watermark.

Calibrate \(V(T)\) and its elasticity using matched cohorts or controlled historical comparisons. A correlation between TVL and volume is not enough: both may be caused by market attention or price appreciation. Use held-out cohorts and report uncertainty. Until credible calibration exists, set \(\epsilon_V=0\) for the conservative LP capital-allocation baseline.

## 12. Experiment plan

Compare these policies on matched random seeds and held-out historical cohorts:

1. Hold all capital in the original Token/quote basket.
2. Hold free Token and quote only; no Dev LP.
3. Fixed LP allocation percentages.
4. LP allocation from fee-turnover minus LVR screening.
5. Marginal LP allocator using \(\epsilon_V=0\).
6. Marginal LP allocator using calibrated \(V(T)\) elasticity.
7. Joint LP/Treasury allocator with Creator Fee recorded separately.
8. Joint allocator with attributable incremental Creator Fee synergy only.
9. Fixed cash-reserve policy versus obligation-aware dynamic cash reserve.
10. Stress-aware partial REMOVE policy that recognizes REMOVE is not a Token sale.

Sensitivity dimensions:

- LP fee tier, Creator Fee tier and beneficiary mode;
- daily volatility, jump frequency and correlated holder sells;
- genuine volume/TVL turnover and its response to pool depth;
- Dev versus external LP share and LP concentration;
- reference-price basis, latency and arbitrage capacity;
- operating reserve, capital lockup and fee claim delay;
- route costs, failed transactions and liquidity withdrawal by other LPs.

Report mean, median, p10, p90, CVaR, cash runway, net liquidation value, LP fee accrual, Creator Fee accrued/settled, beneficial Token Delta/Gamma, pool depth, impact, and market-integrity violations. Run at least 100 seeds for exploration and 500+ for tail comparisons.

## 13. Acceptance criteria

The allocator is not accepted until:

1. LP claims, free inventory and cash reconcile to beneficial-owner balances without double counting.
2. LP fee accrual is counted once, either through reserve value or a separately settled cash claim.
3. Creator Fee is separated from LP Fee and attributed to the actual beneficiary.
4. Accrued Creator Fee and swept/claimed Creator Fee are separate states; sweep events are not counted as new fee income.
5. IL and LVR are reported against distinct benchmarks and are not summed as duplicate losses.
6. The first-order LVR screening formula is labeled as an approximation and not treated as a calibrated forecast.
7. LP ADD/REMOVE changes Delta/Gamma and depth correctly; REMOVE is not reported as a Token sale.
8. A fee tier transition causes the fee model to recompute using the applicable program, pair, route and market-cap tier.
9. Volume elasticity is calibrated or conservatively set to zero; internal/controlled trades never count as genuine volume.
10. Operating reserves, tail-risk limits, minimum depth and impact constraints remain hard gates.
11. Treasury and LP policies are compared on matched seeds and held-out data.
12. No self-trade, wash volume, artificial candle, deceptive coordination or hidden-wallet exit policy is rewarded.

## 14. Implementation order

1. Extend the canonical state with Dev's LP/Treasury beneficial-owner ledger, LP cost basis, Creator Fee beneficiary and accrued/swept/claimed states.
2. Reuse the versioned Pump fee adapter specified in [Dev Treasury & Exit Intelligence](DEV_TREASURY_EXIT.md).
3. Add LP Delta/Gamma and benchmark-specific IL/LVR analytics.
4. Add turnover/LVR screening metrics using true external swaps and the active LP fee tier.
5. Estimate the depth-to-genuine-volume elasticity with historical cohorts; use zero until validated.
6. Implement the LP marginal capital allocator as a proposal engine, not a transaction authority.
7. Integrate its proposals with the Decision Orchestrator's hard gates and joint action bundles.
8. Run matched-seed Monte Carlo, historical replay and paper validation before any live authorization.

No live execution is authorized by this document.
