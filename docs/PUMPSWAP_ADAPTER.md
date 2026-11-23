# PumpSwap State Adapter

**Status:** Implemented on `feat/pumpswap-state-adapter`; decoded-account normalization and fee-sweep state transitions are covered by unit tests. Raw Borsh decoding, transaction ingestion, fee quote parity and LP withdrawal accounting are not implemented here.

## Purpose

PumpSwap's raw quote vault is not always its executable pricing reserve. In particular, v2 trades can leave protocol and creator fees in the quote vault while subtracting those amounts from the signed `Pool::virtual_quote_reserves` field. Every quote and spot-price calculation must use:

\[
Q_{effective}=Q_{quote\ vault}+Q_{virtual}
\]

`virtual_quote_reserves` is signed `i128`, not `u64`. It can be negative. The program guarantees that the effective reserve is nonnegative and fits in `u64`.

## Canonical input contract

The adapter accepts:
- decoded `Pool` account fields from an IDL-versioned decoder;
- the raw base-vault SPL token-account amount;
- the raw quote-vault SPL token-account amount;
- base and quote mint decimals.

Amounts remain integers in raw token units. Decimal strings from JSON-RPC/indexer responses are accepted; floating-point raw amounts are rejected.

Optional trailing fields default to their documented legacy values when absent:
- `virtual_quote_reserves = 0`;
- `creator_fee_bps = 0`;
- `can_edit_creator_fee = false`;
- `is_holder_reward = false`;
- `protocol_fees = 0`;
- `creator_fees = 0`.

The adapter retains the pool's mayhem/cashback flags, creator metadata, mint/account addresses and LP supply. It does not infer an active fee schedule from stale constants.

## Fee-sweep accounting

For a confirmed fee-sweep amount \(F\), the quote vault decreases by \(F\), while the virtual quote reserve increases by \(F\):

\[
Q'_{vault}=Q_{vault}-F
\]

\[
Q'_{virtual}=Q_{virtual}+F
\]

Therefore:

\[
Q'_{effective}=Q'_{vault}+Q'_{virtual}
=Q_{effective}
\]

The selected unclaimed fee bucket decreases by the same amount. This is why a fee sweep must not be interpreted as a price move or a new swap.

The caller must map the decoded on-chain fee-bucket enum to `protocol` or `creator`; this module deliberately does not guess enum values.

## Important accounting boundaries

1. `quote_vault_amount` is a token-account balance, not necessarily LP-owned liquidity.
2. `effective_quote_reserves` is the pricing reserve, not a guaranteed LP redemption balance.
3. `protocol_fees_unclaimed` and `creator_fees_unclaimed` are excluded from pricing liquidity through the signed virtual reserve adjustment.
4. Boost reserves can make effective quote reserves differ from ordinary redeemable balances. Do not compute an LP claim or withdrawable amount from effective reserves alone.
5. Fee schedule selection is quote-mint-, pool-, market-cap- and program-version-dependent. The adapter stores observed pool fields but does not guess fee tiers.
6. V1 and v2 trade fee destinations differ. The event/account decoder must preserve the instruction version and fee recipient/bucket details.
7. This module normalizes decoded state; it does not decode raw account bytes, construct instructions, connect to wallets or submit transactions.

## Source and parity gates

The implementation follows the official Pump public documentation and current PumpSwap IDL:
- PumpSwap program ID: `pAMMBay6oceH9fJKBRHGP5D4bD4sWpmSwMn52FMfXEA`;
- `Pool::virtual_quote_reserves` is signed `i128`;
- effective quote reserves equal quote-vault balance plus virtual quote reserves;
- v2 keeps protocol and creator fees in the quote vault and offsets them in virtual reserves;
- fee sweeps reverse the offset without changing effective pricing reserves;
- older Pool layouts may omit appended fields, which default to zero/false.

Before claiming instruction parity, add dated mainnet/devnet fixtures and compare quote results, fee rounding, buy/sell reserve deltas, LP deposit/withdraw amounts, v1/v2 mixed trades, fee sweeps, mayhem/cashback and Token-2022 cases against the official SDK and deployed program behavior.
