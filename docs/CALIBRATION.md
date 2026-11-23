# Empirical calibration from on-chain swaps

The simulator has two distinct inputs:

1. **Observed market facts** from indexed on-chain events.
2. **Latent behavioral assumptions** such as private risk tolerance, intent, information quality, and unsubmitted orders.

The calibration tool reports the first category and explicitly flags the second. It does not pretend that swaps alone reveal every participant's psychology.

## Normalized CSV schema

One row represents one executed swap for one token. Required columns:

| Column | Type | Meaning |
|---|---|---|
| \`timestamp\` | Unix seconds | Block or transaction timestamp |
| \`wallet\` | string | Trader wallet address |
| \`side\` | \`buy\` / \`sell\` | Token-side trade direction |
| \`token_amount\` | positive number | Token amount exchanged |
| \`quote_amount\` | positive number | Quote amount exchanged |

Optional columns:

| Column | Meaning |
|---|---|
| \`token_address\` | Mint address; required when the file combines multiple tokens |
| \`phase\` | \`bonding_curve\` or \`pump_swap_pool\` to estimate graduation timing |
| \`participant_type\` | Independently verified label: dev, sniper, kol, arbitrageur, retail, whale, lp_provider, mev_risk, unknown |
| \`fee_quote\` | Fee paid in quote units; used to estimate observed fee bps |
| \`venue\` | Source venue / pool identifier |
| \`signature\` | Transaction signature for traceability |

Do not combine different quote assets or different token mints in one calibration sample. If a file includes multiple token addresses, pass \`--token-address\`.

## Run calibration

    pump-calibrate --input data/swaps.csv --out results/calibration.json

For a multi-token file:

    pump-calibrate --input data/swaps.csv --token-address YOUR_MINT --out results/calibration.json

Equivalent module invocation:

    python -m pump_sim.calibrate --input data/swaps.csv --out results/calibration.json

## What is measured

- Trade and wallet counts, buy/sell counts, quote and token volume.
- Trade-size, inter-arrival, and matched buy-to-sell holding-duration distributions.
- Trades per minute, buy/sell quote-volume ratio, wallet-volume HHI.
- Top 1% / top 10% wallet volume share.
- Per-participant-type trade sizes, turnover, and volume share.
- Fee bps when \`fee_quote\` is present.
- First observed post-graduation timestamp when \`phase\` is labeled.

Unlabeled wallet role inference is intentionally conservative and heuristic:
- Whale candidates require a sufficiently large sample and extreme wallet-level quote volume.
- Sniper candidates are early wallets with multiple observed swaps.
- Arbitrageur candidates require repeated short buy/sell holding cycles.
- Remaining unlabeled swap wallets are grouped as retail for descriptive purposes.

These are not ground-truth identities. Use independently verified labels whenever available.

## What swaps cannot identify

Swap-only data cannot reliably identify:
- KOLs whose influence occurs off-chain;
- LP providers without add/remove-liquidity events;
- Dev / treasury wallets without known attribution;
- MEV actors from the victim swap alone;
- wallet balances before the sample, private information, risk tolerance, or unsubmitted orders.

For these, add separately normalized LP events, holder balance snapshots, known wallet labels, and off-chain campaign / KOL event timestamps.

## Calibration protocol

1. Collect multiple launches with complete pre- and post-graduation history.
2. Normalize amounts to one quote asset and one token mint per sample.
3. Label a subset of wallets using independent evidence.
4. Calibrate observable trade-size, activity, holding-time, concentration, fee, and migration distributions.
5. Fit latent behavior parameters on a training cohort.
6. Validate on held-out launches and compare distributions, not just one price path.
7. Keep the synthetic baseline config unchanged; store each calibrated scenario as a separate versioned config.

The report status \`partial_observed_data_only\` is deliberate. Do not treat heuristic labels or inferred behavior as empirical fact.
