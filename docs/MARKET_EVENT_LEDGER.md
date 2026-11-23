# Canonical Market Event Ledger

**Status:** Implemented on `feat/pumpswap-state-adapter`. Canonical identity, duplicate suppression, finality updates, reorg exclusion, attribution buckets, true-volume summaries and swap-derived candles have unit coverage. Raw Solana transaction decoding and on-chain ingestion remain separate, unimplemented inputs.

## 1. Canonical event identity

Each normalized event is identified by:

[
(chain_id, signature, instruction_index, event_index)
]

Slot and transaction index are retained for deterministic ordering. Parser version, source record ID and raw payload hash are retained for provenance.

A repeated delivery with the same identity and same payload is idempotent. A repeated identity with conflicting payload is rejected rather than silently overwritten.

## 2. Event categories

The ledger recognizes:
- swap;
- LP deposit;
- LP withdrawal;
- fee sweep;
- token transfer;
- mint;
- burn;
- other.

Only successful swap events at the configured finality threshold contribute to true volume and candles. The default threshold is `FINALIZED`; callers may explicitly select `CONFIRMED` for lower-latency analysis. Pending, failed and orphaned swaps are excluded. LP events, transfers, mint/burn events and fee sweeps never count as swaps.

## 3. Raw amount and quote-notional contract

Amounts are raw integers in token base units. Floats are rejected to avoid precision loss.

For a swap, the decoder supplies:
- base mint and quote mint;
- base and quote decimals;
- buy/sell side;
- base amount exchanged;
- quote notional;
- an explicit quote-notional basis.

Supported quote-notional bases:
- `POOL_GROSS`;
- `USER_PAID`;
- `USER_RECEIVED`.

Do not combine different bases into one volume series. The chosen basis must be consistent within each market and documented in every report. Fee components are stored separately and do not create additional volume.

## 4. Beneficial-owner attribution

Attribution is an explicit evidence label, not an inference made by the ledger:
- `verified_independent`;
- `unknown`;
- `related_or_controlled`;
- `suspected_non_independent`.

Unknown activity is never silently promoted to independent volume. Suspected activity is not treated as proven manipulation. The summary reports each category separately.

## 5. Finality and reorg behavior

The ledger supports monotonic transitions:
- pending → confirmed → finalized;
- any non-orphaned state → orphaned.

A lower finality status cannot overwrite a higher one. An orphaned event cannot be reactivated under the same identity. If a previously finalized event is explicitly orphaned, all derived true-volume and candle projections exclude it because projections are rebuilt from the current canonical event set.

## 6. True volume and OHLCV

Volume is grouped by base mint, quote mint and quote-notional basis. Different tokens or quote assets are not merged into one market.

Candles are built only from accepted swaps:
- price = normalized quote notional / normalized base amount;
- open/close follow slot, transaction, instruction and event order;
- high/low use executed swap prices;
- quote/base volume and buy/sell quote volume are reported separately;
- trade counts include swaps only.

Mint-decimal disagreement within one market/candle is treated as a data conflict, not silently averaged.

## 7. Boundaries

This module is an event-ledger and projection layer. It does not:
- decode raw Solana account or transaction bytes;
- infer beneficial ownership from wallet behavior;
- decide whether a suspicious pattern proves coordination;
- infer missing swap amounts or timestamps;
- treat LP operations or fee sweeps as trading volume;
- connect to a wallet or submit transactions.

The upstream decoder must preserve transaction success, slot order, instruction/event indices, raw token amounts, mint decimals, event type, finality, fee fields and source provenance.
