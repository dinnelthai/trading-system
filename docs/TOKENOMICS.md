# R01 — Tokenomics and Supply Accounting

**Status:** mathematical specification and pure accounting primitives implemented. The default scenario remains synthetic until it is checked against a dated on-chain cohort.

## 1. Purpose

R01 defines the supply ledger, Dev ownership categories, free-float measures, and holder-concentration metrics used by every later lifecycle and strategy experiment.

It does **not** select a universal Dev allocation percentage. A 10%, 20%, or 30% allocation cannot be called optimal without specifying the launch protocol, reserve layout, vesting rules, market depth, and participant response.

## 2. Four different forms of Dev exposure

These must never be collapsed into one dev_allocation variable:

1. **Genesis allocation** — tokens assigned to Dev/treasury outside the curve at initialization. These tokens must be deducted from another initial supply bucket or the configured total supply must change.
2. **Curve acquisition** — tokens Dev actually purchases through the bonding curve. This is a normal executed buy: curve inventory falls, real quote reserves rise, the curve price changes, fees are paid, and Dev receives a cost basis.
3. **Secondary acquisition** — tokens transferred from an existing holder to Dev. Total supply and AMM reserves do not change; holder ownership and concentration do.
4. **LP claim** — Dev's pro-rata economic claim on pool reserves. It is not a wallet balance and is not additional supply. It is included in beneficial exposure only through look-through accounting.

The current simulator's dev_allocation means **pre-minted genesis allocation**. The current engine does not yet model a special Dev opening curve purchase; that must be represented later as an ordinary queued buy in the execution engine, not as free initial inventory.

## 3. Initial supply ledger

Let:

- \\(S_T\\): total token supply;
- \\(D_u\\): Dev unlocked genesis allocation;
- \\(D_l\\): Dev locked genesis allocation;
- \\(O_l\\): other explicitly locked supply;
- \\(C_r\\): real tokens available to curve buyers;
- \\(M\\): tokens reserved for migration to the post-graduation pool;
- \\(E\\): initial external-venue token inventory;
- \\(U_l\\): residual supply not assigned to a market or named wallet bucket, treated as locked/unallocated.

The initial ledger must satisfy:

\[
S_T = D_u + D_l + O_l + C_r + M + E + U_l
\]

with:

\[
D_u=D(1-v),\qquad D_l=Dv
\]

where \\(D\\) is the Dev genesis allocation and \\(v\\in[0,1]\\) is its locked fraction.

When migration inventory is not explicitly configured:

\[
M=S_T-D-O_l-C_r-E
\]

When migration inventory is explicitly configured, any positive residual is recorded as \\(U_l\\); a negative residual is rejected. No supply is silently dropped.

At runtime the conservation equation is:

**Before graduation**

\[
S_T=\sum_i W_i + (C_r+M)+E+L
\]

**After graduation**

\[
S_T=\sum_i W_i + P_T+E+L
\]

where \\(W_i\\) are wallet balances, \\(P_T\\) is the pool's token reserve, and \\(L\\) is locked/unallocated supply. The migration reserve moves from the curve token account into the pool; it is never counted twice.

Important exclusions:

- Virtual curve reserves are pricing coordinates, not owned token inventory.
- LP shares are claims on existing pool reserves, not newly minted tokens.
- An LP's look-through token claim is used for beneficial-ownership analysis but is excluded from supply conservation.
- Locked Dev tokens count toward ownership concentration but not immediately transferable wallet float.

## 4. Standard Pump-style baseline versus custom allocations

The current synthetic standard baseline is:

| Bucket | Tokens | Share of total |
|---|---:|---:|
| Total supply | 1,000,000,000 | 100% |
| Dev genesis allocation | 0 | 0% |
| Other locked supply | 0 | 0% |
| Real bonding-curve inventory | 793,100,000 | 79.31% |
| Migration inventory | 206,900,000 | 20.69% |
| External token inventory | 0 | 0% |

The reserve snapshot uses 1.073B virtual tokens and 30 SOL virtual quote reserves. These are protocol-model inputs that still require dated deployment verification; they are not a claim that every launch or deployment version uses identical values.

### Why a 20% pre-minted Dev allocation is not the same as a 20% curve purchase

Assume a 1B supply, 200M Dev genesis allocation, and keep the real curve inventory fixed at 793.1M. The residual migration inventory becomes:

\[
M=1,000M-200M-793.1M=6.9M
\]

That is 200M fewer migration tokens than the standard baseline. This is a different supply layout and must not be described as the standard Pump-style launch.

If instead Dev buys 200M tokens from the curve, the 200M comes out of the 793.1M curve inventory and the 206.9M migration reserve remains unchanged. With the initial virtual reserves \\(x=1,073M\\) tokens and \\(y=30\\) SOL, and ignoring other trades:

\[
Q_{net}=\frac{y\Delta x}{x-\Delta x}
=\frac{30\times200M}{1,073M-200M}
\approx6.87285\ SOL
\]

At a 100 bps curve fee, gross quote paid is:

\[
Q_{gross}=\frac{Q_{net}}{1-0.01}\approx6.94228\ SOL
\]

The theoretical spot price changes from \\(y/x\\) to ((y+Q_{net})/(x-\Delta x)), an increase of approximately 51.1%. This is a one-trade reserve calculation, not a recommended trade or an empirical execution quote.

### Locking changes sellability, not ownership

For a 200M Dev genesis allocation with 75% locked:

- Dev direct ownership remains 20% of total supply;
- 150M (15% of total supply) is locked;
- 50M (5% of total supply) is unlocked before vesting.

A lock schedule changes the timing of potential sell supply. It does not make Dev's beneficial ownership disappear. The market must observe both ownership concentration and immediately transferable exposure.

## 5. Float and ownership are different measures

The simulator reports these separately:

- **Wallet free float:** sum of transferable token balances in participant wallets.
- **Locked supply:** tokens that cannot currently transfer under the configured lock/vesting assumption.
- **Curve inventory:** real tokens still available for curve buyers.
- **Migration inventory:** tokens reserved for pool creation.
- **Pool token reserve:** tokens currently held by the AMM and available to trade against quote assets.
- **External inventory:** tokens held by the simplified external venue.
- **LP token claim:** a participant's pro-rata look-through claim on pool token reserves.

There is no single universally correct "float" denominator for every question. For this reason, the simulator must not use the word float to mean both unlocked Dev wallet balance and total circulating supply.

## 6. Dev exposure metrics

For Dev:

\[
D_{direct}=D_u+D_l
\]

\[
D_{beneficial}=D_u+D_l+D_{LP,claim}
\]

Report at least:

- Dev unlocked share of total supply: \\(D_u/S_T\\);
- Dev locked share of total supply: \\(D_l/S_T\\);
- Dev direct ownership share: \\((D_u+D_l)/S_T\\);
- Dev beneficial exposure share: (D_{beneficial}/S_T);
- Dev unlocked share of circulating supply;
- Dev share of wallet free float;
- Dev LP token claim amount, reported separately as dev_lp_token_claim.

Do not infer that LP claim is instantly sellable. LP withdrawal constraints, lock/burn status, and the cost and impact of removing liquidity belong to the LP/lifecycle models.

## 7. Concentration metrics

For transferable wallet balances \\(w_i\\):

\[
HHI_{wallet}=\sum_i\left(\frac{w_i}{\sum_j w_j}\right)^2
\]

This is normalized over wallet free float, not total supply. If no wallet holds transferable tokens, HHI is zero rather than NaN.

For beneficial owner exposure:

\[
b_i=w_i+l_i+p_i
\]

where \\(l_i\\) is owner-attributed locked supply and \\(p_i\\) is the owner's LP token claim. Then:

\[
HHI_{beneficial}=\sum_i\left(\frac{b_i}{\sum_j b_j}\right)^2
\]

Also report:

- identified holder supply;
- identified-holder coverage of total supply;
- top-1 and top-5 shares of total supply;
- top-1 and top-5 shares of identified beneficial holdings.

This avoids the prior denominator error: a holder HHI must be normalized by the holdings included in that HHI. Dividing wallet-only balances by total circulating supply understates concentration whenever curve, pool, or locked inventory is excluded from the numerator.

Wallet clustering must use verified or confidence-scored evidence. A shared funder or common exchange source alone is not proof that two wallets have the same beneficial owner. A transfer between wallets attributed to the same beneficial owner changes wallet location only: it does not reduce beneficial ownership, count as external distribution, reset cost basis or realize sale proceeds. See [Dev Treasury & Exit Intelligence](DEV_TREASURY_EXIT.md).

## 8. Allocation decision model

The allocation problem is a constrained design problem, not a fixed percentage lookup.

Let the design vector be:

\[
z=(D_u,D_l,O_l,C_r,M,E,U_l)
\]

Subject to:

1. exact supply conservation;
2. protocol-valid curve reserve and completion rules;
3. protocol-valid migration inventory;
4. enforceable lock/vesting constraints;
5. an initial pool depth consistent with the intended trade-size and price-impact envelope;
6. transparent ownership and LP control disclosure.

Compare candidate designs across market-quality outcomes: holder concentration, unlocked overhang, curve progress, graduation probability, migration continuity, executable depth, drawdown, and participant outcomes. Keep genesis allocation and Dev curve purchases as separate experiment dimensions.

No universal "optimal Dev percentage" is asserted by R01. The next model stage must add Dev curve purchases as ordinary executions before any parameter sweep can compare them fairly with genesis allocation.

## 9. Implementation and acceptance criteria

Implemented in src/pump_sim/tokenomics.py:

- exact initial supply allocation derivation;
- explicit residual/unallocated locked-supply accounting;
- wallet HHI and beneficial-owner HHI with distinct denominators;
- LP look-through claims that do not inflate conserved supply;
- separate Dev unlocked, locked, direct-ownership, and LP-exposure metrics.

R01 is accepted when:

- the standard baseline reconciles to 1B tokens with 793.1M curve inventory and 206.9M migration inventory;
- a 20% pre-minted Dev allocation changes the derived migration inventory rather than creating extra tokens;
- a 20% curve purchase is modeled as a future executed trade, not genesis allocation;
- Dev locked supply counts as ownership but not transferable wallet float;
- LP claims affect beneficial exposure but are not added to supply;
- HHI uses the supply actually represented in its numerator;
- all tests pass and the existing total-supply conservation invariant remains intact.

## 10. Calibration status

The reserve snapshot is a protocol-model assumption inherited from the existing project specification. Participant holdings, owner clustering, vesting, wallet roles, and actual Dev behavior require on-chain evidence. Swaps alone cannot identify beneficial ownership, private intent, or KOL influence.

Do not promote synthetic allocation sweeps into empirical conclusions until a dated launch cohort has been normalized and independently validated.
