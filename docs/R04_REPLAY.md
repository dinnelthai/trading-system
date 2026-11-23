# R04 — Deterministic On-Chain Event Replay

**Implementation status:** normalized event schema v1.0, slot/transaction/instruction ordering, reserve-state replay, LP position continuity, snapshot reconciliation, and replay CLI are implemented. A protocol-specific raw Solana decoder and complete archive-ingestion adapter are not yet implemented.

## 1. Objective

R01–R03 define the synthetic lifecycle market. R04 tests it against historical market facts.

The first deliverable is not a fitted Agent configuration. It is a deterministic replay tape that can prove, event by event, what the supplied chain data says happened.

R04 keeps three categories separate:

1. **Chain facts:** executed swaps, reserve states, LP changes, migration, token balances, fees, transaction order.
2. **Verified labels:** Dev/treasury, known KOL, sniper, arbitrageur, LP owner, whale, or other role supported by independent evidence.
3. **Latent behavior:** risk tolerance, private information, unsubmitted orders, intent, and off-chain influence. These cannot be read directly from swap events.

Never turn category 3 into a claimed on-chain fact.

## 2. Historical sample design

Do not calibrate only on winners. Use three cohorts:

| Cohort | Outcome pattern | Main questions |
|---|---|---|
| A — sustained post-graduation activity | Market remains active after graduation | What sustains trading, depth, and LP fee generation? |
| B — rapid post-graduation decline | Price and activity contract quickly | Who sells, when does liquidity leave, and how much executable depth remains? |
| C — high-volume / anomalous candles | Apparent volume or OHLC behavior is unusual | Which volume is genuine execution, which events are duplicated or delayed, and how much price impact came from each trade? |

A single token is a debugging fixture, not a calibration cohort. The final calibration set must include multiple launches in each outcome class and retain failed/non-graduating launches as a separate control group.

For every launch, collect the complete available lifecycle:
- mint creation and initial supply/account allocation;
- all bonding-curve buys and sells;
- curve virtual and real reserve changes;
- completion and migration;
- PumpSwap pool creation and initial reserves;
- all post-graduation swaps;
- LP add/remove events and position ownership;
- fee transfers / fee vault deltas where available;
- holder token-balance snapshots or balance deltas;
- block/slot transaction ordering and transaction metadata.

## 3. Canonical event order

The canonical order key is:

\[
(slot,\ transaction\_index,\ instruction\_index,\ inner\_instruction\_index,\ event\_index)
\]

- transaction_index is the transaction's position in the ordered block transaction list.
- instruction_index is the top-level instruction index within the transaction.
- inner_instruction_index identifies the inner instruction; -1 represents a top-level event.
- event_index disambiguates multiple decoded events emitted from one instruction.

This matters for a V3 completing buy: the curve TradeEvent, CompleteEvent, and PostCompleteBuyEvent are distinct events from the same instruction and must remain in their emitted order.

block_time is retained for time-series aggregation, not used to decide transaction order. Multiple transactions can share one timestamp. Never sort by signature text or wallet address to break same-slot ties.

If the data provider cannot supply transaction and instruction order, mark the sample as order-incomplete. Do not claim exact reserve replay.

## 4. Normalized JSONL contract v1.0

One JSON object per line. Raw token and quote quantities are integer atoms; never convert them to floating point before reserve reconciliation.

### Required common fields

| Field | Meaning |
|---|---|
| schema_version | 1.0 |
| event_id | Stable unique event identifier |
| token_address | Token mint |
| quote_mint | Quote asset mint; do not mix quote assets |
| slot | Solana slot |
| transaction_index | Transaction position in the block |
| instruction_index | Top-level instruction index |
| inner_instruction_index | Inner instruction index, or -1 |
| event_index | Event order within the instruction |
| block_time | Unix timestamp in seconds |
| signature | Transaction signature |
| event_type | Event type listed below |
| venue | pump_curve or pumpswap |
| reserve_domain | curve_virtual or pump_swap_pool |
| token_decimals / quote_decimals | Mint decimals |
| source | Archive/indexer source identifier |
| decoder_version | Version of the protocol decoder |
| route_id / hop_index | Optional multi-hop route identity and zero-based hop order; supplied together on swap events only |

### Event types

| event_type | Required payload |
|---|---|
| curve_swap | side, actor_wallet, token/quote amounts, curve virtual reserves before/after |
| curve_complete | completion marker emitted after the final curve leg; no reserve transition |
| post_complete_buy | V3 synthetic pool leg, side=buy, actor_wallet, amounts and pool-to-be reserves before/after |
| pool_swap | side, actor_wallet, token/quote amounts, effective PumpSwap reserves before/after |
| liquidity_add | owner_wallet, position_id, pool reserves before/after, LP shares before/after |
| liquidity_remove | owner_wallet, position_id, pool reserves before/after, LP shares before/after |
| migration | destination pool reserves after; optional before state and source real curve reserves |
| state_snapshot | reserve domain and observed reserves after the indexed event |

### Amount and reserve fields

- token_amount_raw: token swap amount in token atoms.
- quote_amount_raw: gross quote notional before venue fees, in quote atoms. For a buy this is the gross swap input; for a sell it is the gross quote output before fees.
- fee_quote_raw: total unique quote-denominated fee for the event. Do not add it into quote_amount_raw a second time.
- Fee components may be supplied separately as lp_fee_quote_raw, protocol_fee_quote_raw, creator_fee_quote_raw, buyback_fee_quote_raw, cashback_quote_raw, and holder_rewards_quote_raw. Some components can be subcomponents of another fee (for example, buyback can be part of protocol fee); never sum overlapping fields to derive total fees.
- The decoder must preserve instruction-level fee values and the slot-specific fee configuration. Pump's global fee schedule and per-coin flags can change over time; the latest config is not a historical substitute.
- base_reserve_before_raw, quote_reserve_before_raw, base_reserve_after_raw, quote_reserve_after_raw: exact pricing reserves for the event's reserve_domain.
- For curve_swap, base/quote reserve fields represent virtual curve reserves. Optional real_token_reserve_* and real_quote_reserve_* fields carry actual curve inventory and quote account balance.
- For PumpSwap, quote_reserve_* always means **effective quote reserves**, not the raw quote vault balance. Preserve pool_quote_vault_before_raw / pool_quote_vault_after_raw and signed pool_virtual_quote_reserve_before_raw / pool_virtual_quote_reserve_after_raw separately. Validate effective quote = quote vault + signed virtual quote reserve at each supplied state.
- The replay checks continuity of both raw quote-vault balance and signed virtual quote reserve independently, even when their sum (effective quote reserve) is unchanged.
- PumpSwap virtual_quote_reserves is a signed i128 and may be negative. Effective quote reserves are guaranteed nonnegative by the program. Do not parse the virtual field as u64 or silently clamp it.
- A state_snapshot may provide only the after quote-vault / virtual-reserve pair; a transition event may provide before and after pairs.
- lp_shares_before_raw and lp_shares_after_raw are the position's exact LP token balance, not total pool supply.
- source_base_reserve_raw and source_quote_reserve_raw on migration represent source real curve reserves, not virtual reserves.
- participant_type is optional and should only be populated from independently verified labels.

### Pump V3 and PumpSwap V2 event handling

The Pump bonding-curve program and PumpSwap AMM have separate program IDs and versioned instruction families. Preserve instruction names and decoder version in the raw archive. V2 and V3 instructions can coexist with legacy instructions.

For a V3 completing buy, normalize the emitted sequence separately:
1. TradeEvent as curve_swap for the curve portion.
2. CompleteEvent as curve_complete.
3. PostCompleteBuyEvent as post_complete_buy for the pool-to-be portion.
4. The later migration event initializes or confirms the destination pool.

Do not combine the two buy legs into one curve swap. The synthetic pool leg is not a post-graduation PumpSwap trade.

For PumpSwap V2, protocol and creator fees can remain in the quote vault while being excluded from pricing via signed virtual quote reserves. The replay's effective quote reserve must therefore be derived from both fields. Fee configuration and instruction version must be captured at the event's slot; do not assume the current fee schedule applies retroactively.

PumpSwap multi_hop_swap instructions must be split into one normalized swap event per pool/curve hop. Preserve a shared route_id and the zero-based hop_index on each hop. Each hop is replayed against its own token/quote mint pair; route_id links the per-hop records without collapsing them into one synthetic trade.

Official protocol references:
- [Pump program and Bonding Curve](https://github.com/pump-fun/pump-public-docs/blob/main/docs/PUMP_PROGRAM_README.md)
- [Bonding Curve V3](https://github.com/pump-fun/pump-public-docs/blob/main/docs/instructions/TRADE_V3.md)
- [PumpSwap program](https://github.com/pump-fun/pump-public-docs/blob/main/docs/PUMP_SWAP_README.md)
- [PumpSwap V2](https://github.com/pump-fun/pump-public-docs/blob/main/docs/instructions/PUMP_SWAP_TRADE_V2.md)
- [Negative virtual quote reserves](https://github.com/pump-fun/pump-public-docs/blob/main/docs/NEGATIVE_VIRTUAL_QUOTE_RESERVES.md)

All raw amount fields are integer strings or JSON integers. Decimal floats are rejected. This prevents precision loss in reserve comparisons.

## 5. Replay invariants

The replay engine checks:

1. Unique event IDs and unique canonical order keys.
2. One token mint, one quote mint, and consistent decimals per replay.
3. Reserve continuity: an event's before state must equal the previous event's after state for the same reserve domain.
4. LP position continuity: a position's previous share balance must match the next liquidity event's before balance.
5. Migration source reserve agreement when source reserves and curve state are both present.
6. Snapshot reconciliation: an observed state snapshot is compared with replay state. It never silently resets or repairs the replay.
7. Execution price versus pre-trade spot and post-trade marginal price.
8. Liquidity add/remove spot-price movement. A ratio-matched deposit or withdrawal should have approximately zero spot-price impact.

A reserve mismatch is a result, not something to smooth away. Preserve the event and report the discrepancy.

## 6. Current command

Install the package in the project environment, then run:

    pump-replay --input data/normalized_events.jsonl --out results/replay.json

For a multi-token archive:

    pump-replay --input data/all_events.jsonl --token-address TOKEN_MINT --out results/replay.json

The report contains event counts, transaction counts, reserve continuity, snapshot comparisons, final reserve states, migration count, LP position continuity, liquidity changes, execution slippage, marginal price impact, and the existing swap-only descriptive calibration report.

replay_status=consistent means only that the supplied normalized event stream is internally consistent. coverage_status=normalized_event_stream_only explicitly does not certify that the source archive or decoder captured every relevant on-chain event.

## 7. Source ingestion and decoder gate

The raw decoder is a separate layer from replay. It must be versioned by program/IDL version and retain:
- raw transaction/signature and slot;
- transaction index in the block;
- top-level and inner instruction indices;
- event/log index;
- program ID and instruction/event name;
- account keys and relevant pre/post token balances;
- raw integer amounts and mint decimals;
- source record ID and raw payload hash;
- decoder version and decode warnings.

Do not buy or trust a historical data export until a small sample proves that it includes:
- transaction index within each slot;
- instruction and inner-instruction order;
- both sides and raw token/quote amounts;
- reserve state or enough account data to reconstruct it;
- LP add/remove ownership and position identity;
- migration and initial pool state.

A trades-only export is sufficient for descriptive swap statistics, but not for full lifecycle replay, LP attribution, reserve reconciliation, or holder cost-basis reconstruction.

## 8. R04 acceptance sequence

### R04.1 — Event contract and replay engine
- [x] Versioned normalized event schema.
- [x] Slot/transaction/instruction deterministic ordering.
- [x] Curve and pool reserve replay.
- [x] LP position and reserve continuity.
- [x] Snapshot drift reporting.
- [x] Execution price / spot / marginal impact separation.
- [x] Pump V3 completion marker and synthetic pool-leg ordering.
- [x] Signed PumpSwap virtual quote reserve / effective quote reserve validation.
- [x] Separate continuity checks for quote-vault and virtual-reserve components.
- [ ] Real archive sample and decoder completeness proof.

### R04.2 — Holder ledger and participant attribution
- [ ] Token account balance deltas and owner aggregation.
- [ ] Cost-basis lots and realized/unrealized PnL by wallet.
- [ ] Wallet clustering kept separate from verified identity.
- [ ] Dev, treasury, LP owner, sniper, KOL, arbitrageur, whale and retail labels with evidence/provenance.
- [ ] Sandwich candidates and cross-pool arbitrage candidates as event-pattern classifications, not identity claims.

### R04.3 — Candle and volume reconciliation
- [ ] Build 1-second, 1-minute, and 5-minute OHLCV from ordered executions.
- [ ] Compare with independent chart/indexer feeds.
- [ ] Attribute volume to unique signatures/instructions and detect duplicate ingestion.
- [ ] Compare execution VWAP, marginal spot, reference venue, slippage, and depth.
- [ ] Report candle-quality indicators (KQI) with explicit formulas.

### R04.4 — Parameter fitting and held-out validation
- [ ] Fit observable arrival, order-size, inter-arrival, holding-time, and capital distributions.
- [ ] Fit role-specific behavior only where role labels are independently supported.
- [ ] Keep latent risk preference, private information, and unsubmitted intent as priors or sensitivity parameters.
- [ ] Fit on training launches; validate on held-out launches.
- [ ] Store calibrated configs separately; never overwrite the synthetic baseline.
- [ ] Report confidence intervals and residuals by cohort, lifecycle phase, and participant type.

## 9. What this stage does not claim

- It does not decode arbitrary raw Solana transactions yet.
- It does not establish that an archive export is complete.
- It does not infer KOL identity from trading alone.
- It does not infer a sandwich attacker from a victim swap alone.
- It does not reconstruct private intent or off-chain information.
- It does not execute transactions or connect to a wallet.

Historical replay establishes observed market facts. The stochastic Agent model remains a separate hypothesis layer that must explain those facts out of sample.
