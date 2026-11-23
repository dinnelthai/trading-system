# Solana Historical Archive Export

R04 uses raw finalized Solana block responses as the source archive. Indexer exports may help discover candidate launches and signatures, but the replay dataset must retain transaction order and enough raw metadata to independently decode protocol events.

## 1. Why getBlock is the base archive

Use Solana JSON-RPC getBlock with:
- commitment: finalized;
- transactionDetails: full;
- encoding: json;
- maxSupportedTransactionVersion: 1;
- rewards: false.

The returned transactions array is the canonical transaction order within that block. Each transaction's metadata can include innerInstructions, logs, loaded addresses, preTokenBalances, and postTokenBalances. The exporter records the array index as transaction_index and preserves the full transaction/meta objects.

Official references:
- [Solana getBlock RPC](https://solana.com/docs/rpc/http/getblock)
- [Solana JSON RPC response structures](https://solana.com/docs/rpc/json-structures)
- [Solana transaction introspection](https://solana.com/docs/core/transactions/transaction-introspection)

If the provider cannot serve the requested finalized historical slots, record the failure in the block manifest. Do not silently skip missing ranges.

## 2. Probe a mint before exporting its lifecycle

Set `SOLANA_RPC_URL`, install the project, and run:

    solana-token-probe \
      --mint TOKEN_MINT \
      --quote-mint So11111111111111111111111111111111111111112 \
      --out data/mint_probe.json

This records the mint owner program, decimals, raw supply, Token-2022 TLV extension IDs/payload hashes, quote-mint metadata, and the address-indexed signature history. The signature index provides candidate first/last slots; it is newest-first and is not the canonical transaction order or a completeness proof. The mint account snapshot records the RPC context slot and raw-data hash.

If the signature history reaches `--max-pages`, `history_complete` is false. Increase the page cap and repeat. After the candidate slot range is known, export every block in that range without an address filter.

## 3. Export a slot range

Set the archive RPC endpoint in an environment variable so credentials do not enter shell history or source control:

    export SOLANA_RPC_URL="YOUR_ARCHIVAL_RPC_ENDPOINT"

Then export the launch's slot range:

    solana-block-export \
      --start-slot START_SLOT \
      --end-slot END_SLOT \
      --out data/raw_transactions.jsonl \
      --blocks-out data/block_manifest.jsonl

The exporter writes:
- raw_transactions.jsonl: one full raw transaction record per line, with slot, transaction_index, signature, transaction metadata, execution status, and SHA-256 of the canonicalized raw record;
- block_manifest.jsonl: one row per requested slot, including block hash, block time, transaction count, and status.

Failed transactions are retained and marked failed. They must not mutate the replay state, but can be used to study failed order attempts and slippage reverts.

A null block result is recorded as skipped_or_unavailable. RPC failures are recorded as rpc_error. The exporter does not invent a block timestamp when blockTime is null.

## 4. Optional coarse address filter

For a small discovery export, the exporter can retain transactions whose raw JSON contains a supplied address:

    solana-block-export \
      --start-slot START_SLOT \
      --end-slot END_SLOT \
      --contains-address TOKEN_MINT \
      --out data/token_screened_transactions.jsonl

This is only a coarse filter. It is explicitly marked as not being a completeness proof. A transaction related to a token may reference a pool, token account, vault, or intermediate quote mint without containing the base mint in the exact serialized section being screened. Use an unfiltered slot archive or a separately verified address/signature inventory for final completeness.

## 5. Version-aware Pump decoder requirements

The protocol decoder must identify the program ID and instruction variant for every event. Current official public documentation lists:

- Pump bonding-curve program: 6EF8rrecthR5Dkzon8Nwu78hRvfCKubJ14M5uBEwF6P
- PumpSwap AMM program: pAMMBay6oceH9fJKBRHGP5D4bD4sWpmSwMn52FMfXEA

Decode the relevant legacy and versioned instruction/event families, including:
- Pump create / create_v2;
- Pump buy / sell, buy_v2 / sell_v2, buy_v3 / sell_v3, buy_exact_quote_in_v3;
- TradeEvent, CompleteEvent, PostCompleteBuyEvent, CompletePumpAmmMigrationEvent;
- Pump migrate / migrate_v2;
- PumpSwap create_pool, buy / sell, buy_v2 / sell_v2;
- PumpSwap CreatePoolEvent, BuyEvent, SellEvent, DepositEvent, WithdrawEvent, SweepPoolFeeEvent;
- multi_hop_swap, split into individual pool/curve hops with one route ID and explicit hop index.

The Pump IDL and PumpSwap IDL are versioned inputs to the decoder. Store the exact IDL commit/version used for each decoded range. A latest IDL must not be assumed to describe all historical transactions.

## 6. Account and instruction decoding

For raw JSON transactions, resolve account indices against static account keys plus loaded addresses. Decode top-level instructions and inner CPI instructions separately. Preserve:
- outer instruction index;
- inner instruction index;
- event/log order within an instruction;
- program ID;
- instruction discriminator/name;
- all relevant account addresses;
- pre/post token balance rows, including mint, owner, token account index, and raw amount/decimals.

Use raw integer amounts. Avoid uiAmount floating point fields for reserve reconciliation.

For Token-2022, preserve the token program owner, mint extension TLV data, and token-account extension data. Decode TransferCheckedWithFee / transfer-fee withheld amounts and any transfer-hook CPI from the actual transaction. The presence of Token-2022 alone does not prove that any particular extension is enabled.

## 7. Data quality gate before paid history or calibration

Before purchasing a large archive export, test a narrow range covering:
1. a token creation transaction;
2. at least one curve buy and one curve sell;
3. the completing V3 buy if present;
4. a migration transaction;
5. one PumpSwap buy and sell;
6. one LP deposit and withdrawal, if the pool has them.

Verify that the provider returns:
- full transactions and stable transaction order within each slot;
- inner instructions and program logs;
- token pre/post balances;
- all required account keys, including loaded addresses;
- raw instruction data;
- sufficient history for the complete launch lifecycle.

Do not proceed to parameter fitting if the provider only supplies decoded trade rows but omits LP events, reserve states, or same-slot ordering.

## 8. Privacy and operations

- Keep RPC credentials in environment variables; never commit endpoint URLs containing API keys.
- Keep raw archives immutable. Write decoded normalized events to a separate versioned file.
- Record source, slot range, provider, IDL version, decoder version, and raw-file hashes in the dataset manifest.
- Never overwrite the synthetic baseline configuration with values fitted from one launch.
