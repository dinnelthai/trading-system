# R02 — Bonding Curve Mathematics and Execution

**Status:** reserve math, fee accounting, synthetic migration, asymmetric depth, and slippage-aware order settlement implemented. This is a continuous-reserve research model, not a lamport-exact transaction emulator.

## 1. Why this stage exists

A bonding-curve market has several values that must not be confused:

1. **Spot price / FDV:** calculated from virtual reserves.
2. **Real quote reserve:** actual quote inventory available to fund curve sells and later migration.
3. **Fee vault:** protocol and creator fees accumulated by the program but not available as LP liquidity.
4. **Migration pool reserve:** the real token and quote reserves actually deposited into the post-graduation pool.

A rising FDV does not mean the curve has received an equal amount of SOL. The virtual SOL reserve is a pricing coordinate, not a cash balance.

The official Pump documentation describes the curve as a Uniswap-V2-style constant-product curve over synthetic reserves, and separately identifies real token and real SOL reserves. It also defines completion by exhausting real token reserves. References: [Pump program state and curve](https://github.com/pump-fun/pump-public-docs/blob/main/docs/PUMP_PROGRAM_README.md), [Pump fee program](https://github.com/pump-fun/pump-public-docs/blob/main/docs/FEE_PROGRAM_README.md).

## 2. Five reserve/accounting variables

Use these symbols throughout the model:

| Symbol | Meaning | Is it tradable liquidity? |
|---|---|---|
| (x) | Virtual token reserve | No; price coordinate |
| (y) | Virtual quote reserve | No; price coordinate |
| (R_T) | Real token inventory available to curve buyers | Yes, on the buy side |
| (R_Q) | Real quote reserve accumulated by curve trades | Yes, on the sell side |
| (F_P,F_C) | Pending protocol and creator fee balances | No; fee claims, not LP liquidity |

The token account also contains the migration inventory. Before synthetic migration:

\[
T_A = R_T + M
\]

where (M) is the token inventory reserved for the future pool. When a V3 completing buy also buys from the pool-to-be, that migration inventory is reduced before the pool is created.

The virtual price and curve FDV are:

\[
P=\frac{y}{x}
\]

\[
FDV=P\cdot S_T=\frac{yS_T}{x}
\]

The real quote reserve is a different variable. It starts at zero for the standard SOL-paired curve even though the virtual quote reserve starts at 30 SOL.

## 3. Buy mathematics

Let (G) be the all-in quote budget including protocol and creator fees. Let (r) be the combined fee rate.

For the continuous model, fees are charged on the quote amount entering reserves:

\[
N=\frac{G}{1+r}
\]

\[
F=N\cdot r,\qquad G=N+F
\]

The tokens received from net reserve input (N) are:

\[
\Delta T=\frac{xN}{y+N}
\]

The state transition is:

\[
x'=x-\Delta T,\quad y'=y+N
\]

\[
R_T'=R_T-\Delta T,\quad R_Q'=R_Q+N
\]

The virtual invariant is preserved:

\[
x'y'=xy
\]

The buy is capped by real curve inventory on the curve leg. If the budget cannot buy all remaining real tokens, the engine executes a partial curve fill and returns the unused budget.

### Exact-token quote

For an exact desired output (Delta T), the net quote required is:

\[
N=\frac{y\Delta T}{x-\Delta T}
\]

The all-in quote cost is:

\[
G=N(1+r)
\]

As (Delta T\) approaches (x), the required quote tends to infinity. This is the mathematical reason a constant-product curve cannot buy all virtual tokens.

## 4. Sell mathematics and the real SOL cap

For a sale of (Delta T), the gross quote removed from reserves is:

\[
Q_g=\frac{y\Delta T}{x+\Delta T}
\]

Fees are deducted from gross output:

\[
Q_{user}=Q_g-F_P-F_C
\]

The state transition is:

\[
x'=x+\Delta T,\quad y'=y-Q_g
\]

\[
R_T'=R_T+\Delta T,\quad R_Q'=R_Q-Q_g
\]

The sell must never withdraw more quote than the real quote reserve contains. Solving (Q_g\le R_Q) gives the maximum curve sell amount:

\[
\Delta T_{max}=\frac{R_Qx}{y-R_Q}
\]

The simulator caps sells at this amount. This is an economic reserve cap, not a wallet-balance cap.

## 5. Fee accounting: reserve versus fee vault

Pump's newer V3 trade instructions keep protocol and creator fees on the curve until a later sweep; the buyback component of the protocol fee is paid during the trade. The fee amounts are unchanged relative to the corresponding older trade instructions. See [Bonding Curve Trades V3](https://github.com/pump-fun/pump-public-docs/blob/main/docs/instructions/TRADE_V3.md) and [Fee sweeps](https://github.com/pump-fun/pump-public-docs/blob/main/docs/instructions/SWEEP_FEES.md).

The simulator now separates:

- protocol fees pending;
- creator fees pending;
- buyback fees paid immediately;
- fees paid out immediately in legacy mode;
- real quote reserve.

For V3-style retained fees:

\[
F_{vault}=F_{P,pending}+F_{C,pending}
\]

\[
\text{curve account quote balance}=R_Q+F_{vault}
\]

The fee vault is not included in sell depth or migration LP reserves.

The buyback fee is modeled as a component of protocol fees, not an extra fee on top of protocol fees. Validation rejects a buyback rate greater than the protocol rate.

### Dynamic fee tiers

Pump's public fee documentation selects bonding-curve fee tiers from market cap computed with virtual reserves:

\[
MC=\frac{yS_T}{x}
\]

The simulator supports the same kind of threshold selection through curve_fee_tiers. Each tier uses:

- market_cap_quote_threshold;
- protocol_fee_bps;
- creator_fee_bps;
- optional buyback_fee_bps.

The highest threshold not above the current virtual-reserve market cap is selected; if the market cap is below the first threshold, the first tier applies. If no tiers are configured, the synthetic fallback rates in SimConfig apply. The model does not fetch live fee tiers automatically.

## 6. Graduation and migration

The completion condition is:

\[
R_T=0
\]

It is not a market-cap target or a quote-reserve target.

For a curve-only completion, the pool receives:

\[
B_0=T_A
\]

\[
Q_0=R_Q-F_{migration}
\]

Pending protocol and creator fees remain separate from pool liquidity. Migration transfers the real quote reserve into the pool, subtracts the configured migration fee, and zeros the curve's migrated real quote/token account balances in the simulator.

The model records both the curve terminal price and the pool opening price. With no synthetic buy, the migration fee creates a small, measurable price gap.

## 7. V3 synthetic migration: completing buy crosses into the pool-to-be

The current Pump V3 behavior is more advanced than the older partial-fill-only model. A V3 completing buy can buy the remaining curve inventory and then use its remaining budget against the pool that will be created by migration. The pool opens with exactly the post-buy reserves. Both legs use the bonding-curve fee schedule, not the PumpSwap pool fee schedule. References: [official synthetic migration specification](https://github.com/pump-fun/pump-public-docs/blob/main/docs/SYNTHETIC_MIGRATION.md), [V3 trade instructions](https://github.com/pump-fun/pump-public-docs/blob/main/docs/instructions/TRADE_V3.md).

Let the remaining curve inventory be (R_T).

First, calculate the net quote needed to exhaust the curve:

\[
N_c=\frac{yR_T}{x-R_T}
\]

\[
G_c=N_c(1+r_c)
\]

After this curve leg:

\[
x_c=x-R_T,\quad y_c=y+N_c
\]

The pool-to-be reserves, before the synthetic pool leg, are:

\[
B_0=T_A-R_T
\]

\[
Q_0=R_Q+N_c-F_{migration}
\]

If the user has remaining gross budget (G_l=G-G_c), the net quote entering the pool-to-be is:

\[
N_p=\frac{G_l}{1+r_p}
\]

The extra tokens received are:

\[
\Delta T_p=\frac{B_0N_p}{Q_0+N_p}
\]

The pool opens with:

\[
B_1=B_0-\Delta T_p
\]

\[
Q_1=Q_0+N_p
\]

The simulator updates the migration token account and quote reserve before creating the pool. This makes the pool opening price continuous with the price after the synthetic pool leg.

### Numerical example: a 100 SOL completing buy

Using the default reserve snapshot and the illustrative 100 bps protocol-only fallback:

- Curve leg: approximately 85.85541 SOL gross spend buys the final 793.1M curve tokens.
- Remaining gross budget: approximately 14.14459 SOL.
- Synthetic pool leg: approximately 14.00454 SOL enters the pool-to-be after fees and buys approximately 29.26959M more tokens.
- Pool opens with approximately 177.63041M tokens and 98.99490 SOL quote reserve.
- Opening spot price is approximately 5.5731e-7 SOL/token, or about 557.31 SOL FDV.

With synthetic migration disabled, the curve-only buy would stop after the first leg and leave approximately 14.14459 SOL of the 100 SOL budget unspent. This is why the final V3 buy must be modeled as two linked legs rather than a simple curve cap.

Only the completing V3 buy receives this treatment. The legacy/partial-fill behavior remains available by setting curve_synthetic_migration to false.

## 8. Why FDV can be much larger than real SOL backing

Use the repository's synthetic standard reserve snapshot:

- total supply: 1,000,000,000 tokens;
- virtual token reserve: 1,073,000,000;
- virtual quote reserve: 30 SOL;
- real curve token inventory: 793,100,000;
- migration inventory: 206,900,000;
- initial real quote reserve: 0 SOL.

The starting spot price and FDV are:

\[
P_0=\frac{30}{1.073B}\approx2.7959\times10^{-8}
\]

\[
FDV_0\approx27.96\ SOL
\]

At curve completion, the net quote added to real reserves is approximately 85.00536 SOL. With the illustrative 100 bps protocol-only fallback fee:

- gross user spend is approximately 85.85541 SOL;
- pending protocol fee is approximately 0.85005 SOL;
- real quote reserve is approximately 85.00536 SOL;
- after the 0.015000001 SOL migration fee, the initial pool receives approximately 84.99036 SOL.

The terminal virtual price is approximately (4.1088\times10^{-7}) SOL per token, corresponding to an FDV of approximately 410.88 SOL.

So the model can show roughly 410.88 SOL FDV while the initial pool has only about 84.99 SOL of quote liquidity. These are not contradictory: FDV is a marginal price multiplied by total supply; pool quote reserve is actual inventory available to trade.

The 100 bps fee in this example is the repository's synthetic fallback, not a statement of the live fee tier for every current Pump coin.

## 9. Asymmetric depth at a chosen price-impact threshold

A single depth number hides whether a market can absorb buys or fund sells. The simulator reports both sides.

For target upward spot-price impact (delta), the virtual-curve buy-side quote depth is:

\[
D_{buy}=y(\sqrt{1+\delta}-1)
\]

It is capped by the quote needed to exhaust the remaining real curve token inventory.

For target downward spot-price impact (delta), the sell-side quote depth is:

\[
D_{sell}=\min\left(R_Q,\ y(1-\sqrt{1-\delta})\right)
\]

The sell side is therefore bounded by actual quote reserves. At launch, real quote reserve is zero, so the curve has no sell-side quote depth even though its virtual price is nonzero.

After graduation, the same price-impact calculation is applied to actual pool reserves. The default depth-impact threshold is 500 bps (5%) and can be changed in SimConfig.

## 10. Asynchronous execution and slippage

Agents still wake asynchronously and submit orders with individual latency. Orders settle at simulated block times with randomized within-block priority.

R02 adds a transaction-like slippage guard:

1. At submission, the agent quotes expected output against the then-current market state.
2. The agent's slippage tolerance defines a minimum acceptable output.
3. At settlement, the engine recomputes output against the latest reserves.
4. If the output is below the minimum, the order reverts and no balances or reserves change.

This creates realistic competition between orders that were quoted against the same earlier state. The model reports submitted orders, successful executions, failed orders, slippage reverts, and execution latency.

It remains a simplified block-ordering model. It does not model Solana's full scheduler, priority fees, bundle auctions, validator behavior, or an actual mempool.

## 11. Implementation and acceptance

Implemented:

- pure continuous-reserve formulas in src/pump_sim/curve_math.py;
- fee-tier selection and separate protocol/creator/buyback fee accounting;
- real quote reserve and fee-vault separation;
- V3 synthetic migration for the completing buy;
- curve-to-pool reserve migration without double counting;
- buy-side and sell-side depth at a configurable price-impact threshold;
- slippage-aware order settlement and execution telemetry;
- exact-output quote helper for a desired token amount;
- regression tests for invariant preservation, fee accounting, synthetic migration, migration continuity, real quote caps, and slippage reverts.

### Known limitations

- The ABM uses floating point quote/token units. It does not yet reproduce lamport/token-atom floor/ceil rounding exactly.
- The default fee configuration is synthetic. Live Pump fee tiers are not fetched automatically.
- The external venue and pool fee model remain simplified.
- The model does not implement Mayhem-specific exceptions, full v2/v3 instruction account semantics, on-chain transaction scheduling, or real RPC ingestion.
- The curve quote formulas are continuous; exact transaction quoting should be cross-checked against the official Pump SDK before using the model as an indexer or execution quote source.

R02 is accepted only as the research engine's continuous-reserve baseline. Protocol-parity claims require a separate integer-arithmetic and dated on-chain fixture suite.
