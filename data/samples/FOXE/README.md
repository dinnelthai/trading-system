# FOXE — Sample 001

**Status:** candidate identified; raw chain verification and decoding pending.

## Identity

- Mint: \`E2XCAc12j7Eb6NhXKYMmTcGBAryZ1WPuY1fwSbp4pump\`
- Name / symbol: Foxecoin / FOXE
- Quote mint: wrapped SOL (\`So11111111111111111111111111111111111111112\`)
- Creator reported by Pump: \`2griikJDBj2uJnjZ47s86tRn1XVTrLu2hMGS5UZto4sf\`
- Token program reported by a third-party indexer: Token-2022
- Decimals reported by a third-party indexer: 6
- Creation time reported: 2026-11-23 02:31 UTC
- Graduation time reported: 2026-11-23 02:38 UTC
- PumpSwap FOXE/SOL pool reported by a market indexer: \`GJELELum3v7KCSk5nEobE2VCeKoiDAZeSL9KW9WTedLx\`

The reported Token-2022 program is a discovery lead, not yet an on-chain verification. The actual enabled mint extensions are unknown until the mint account's TLV data is read from finalized RPC state. Do not infer that transfer fees or transfer hooks are enabled merely because the mint uses Token-2022.

## Discovery-source caveats

- Pump's public page identifies FOXE and its creator and shows a PumpSwap pool after graduation.
- A market page reports the full PumpSwap pool address above.
- An earlier DexScreener snapshot shows a different truncated pair, \`Cmbjy...tciT\`, while the token was still on its bonding curve. Do not use that pre-graduation pair as the PumpSwap migration pool.
- Public market snapshots are time-varying and sometimes disagree. Do not use their current price, market cap, volume, liquidity, or holder counts as historical ground truth.

See [manifest.json](manifest.json) for field-level verification status and source URLs.

## Step 1 — Probe the mint

From the repository root:

    export SOLANA_RPC_URL="YOUR_ARCHIVAL_RPC_ENDPOINT"

    pip install -e .
    solana-token-probe \
      --mint E2XCAc12j7Eb6NhXKYMmTcGBAryZ1WPuY1fwSbp4pump \
      --quote-mint So11111111111111111111111111111111111111112 \
      --out data/samples/FOXE/mint_probe.json

The command:
- verifies the mint account's owning token program;
- reads decimals and raw supply;
- parses Token-2022 mint TLV extension types without assuming an extension is active;
- records the wrapped-SOL quote mint program and decimals;
- paginates \`getSignaturesForAddress\` to discover the mint's earliest/latest slots;
- writes the address-indexed signatures to \`mint_probe.signatures.jsonl\`.

The signature index is newest-first and is only a discovery index. It is not canonical transaction order and is not a completeness proof for related pool/LP accounts.

If \`history_complete\` is false, increase \`--max-pages\` and rerun.

## Step 2 — Export full blocks

Read the discovered slot range:

    START_SLOT=$(python -c 'import json; print(json.load(open("data/samples/FOXE/mint_probe.json"))["history"]["first_seen_slot"])')
    END_SLOT=$(python -c 'import json; print(json.load(open("data/samples/FOXE/mint_probe.json"))["history"]["last_seen_slot"])')

Export every block in the range without an address filter:

    solana-block-export \
      --start-slot "$START_SLOT" \
      --end-slot "$END_SLOT" \
      --out data/samples/FOXE/raw_transactions.jsonl \
      --blocks-out data/samples/FOXE/block_manifest.jsonl

Do not use \`--contains-address\` for the final archive. Keep failed transactions and null/error slot manifest rows for coverage accounting.

## Step 3 — Verify lifecycle anchors

Before decoding the full stream, independently identify and record:
1. mint creation transaction and its slot/index;
2. bonding-curve PDA and initial virtual/real reserves;
3. all curve buys/sells, including any V3 completing-buy multi-event sequence;
4. completion and migration transaction;
5. PumpSwap pool address and initial reserves;
6. PumpSwap swaps, LP deposits/withdrawals, and fee sweeps;
7. token account pre/post balances and Token-2022 transfer behavior.

The pool address and timestamps in this discovery record remain provisional until the migration/create-pool instructions and their transaction account lists confirm them.

## Step 4 — Decode and replay

Write normalized events to a separate file; never edit the raw archive in place:

    pump-replay \
      --input data/samples/FOXE/normalized_events.jsonl \
      --out results/FOXE/replay.json

Do not calibrate the stochastic Agent model from FOXE alone. It is one debugging and protocol-coverage sample. Use it to validate the decoder and replay engine, then add independent launches from sustained, failed, and anomalous cohorts.
