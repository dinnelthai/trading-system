# Market Integrity Engine

**Status:** Implemented on `feat/pumpswap-state-adapter` as a conservative offline diagnostic layer with unit tests. Raw transaction decoding, wallet-label ingestion, identity resolution and live monitoring remain unimplemented.

## Purpose

The engine asks whether observed swap volume is concentrated, rapidly reversed, linked to verified related owners, synchronized across related wallets, or large relative to executable sell depth. It produces review signals; it does not decide that an address is malicious or that a pattern is manipulation.

It consumes the [Canonical Market Event Ledger](MARKET_EVENT_LEDGER.md) event contract. Only unique successful swaps at the configured finality threshold enter its metrics.

## Evidence tiers

### Strong evidence — may form a related-owner cluster

- `disclosed_control`;
- `verified_shared_authority`.

Both must be explicitly marked verified and have confidence of at least 0.95. These links can form a transitive owner cluster. The analyzer reports the volume and number of observed wallets in those linked clusters separately.

### Weak evidence — review only, never merge

- shared funding source;
- shared fee payer;
- common withdrawal destination;
- timing correlation;
- similar amount pattern.

These can occur for legitimate reasons such as custodians, relayers, exchanges, common infrastructure or coincident market behavior. They are counted as weak-link evidence and are not used to infer common beneficial ownership.

## Implemented diagnostics

1. **Rapid same-wallet round trip** — detects buy and sell activity within a configured rolling window. The turnover ratio is based on base-token inventory bought versus sold; quote notional is used only for the minimum activity threshold. A balanced quote amount with a material remaining Token inventory does not pass this test.
2. **Verified related-owner turnover** — reports large two-way turnover across wallets joined by strong evidence. It is a review signal and does not automatically relabel the events.
3. **Synchronized related-wallet burst** — reports multiple wallets in the same verified owner cluster trading within a narrow time window.
4. **Wallet concentration** — reports top-wallet share of total market notional and HHI across wallets with identified addresses. Unattributed volume is reported separately.
5. **Sell flow versus depth** — compares sell notional in a configured time window with the most recent sufficiently fresh executable sell-depth observation.
6. **Pool/reference divergence** — reports absolute log-basis divergence only when the supplied reference is explicitly marked valid.

## Attribution is not rewritten

The report keeps these quantities separate:
- event-provided verified-independent volume;
- unknown-attribution volume;
- event-provided related/controlled volume;
- event-provided suspected-non-independent volume;
- volume from wallets connected by verified owner-link evidence;
- volume with no actor-wallet identity.

A behavioral anomaly is not enough to reclassify unknown volume as related/controlled. Upstream attribution requires auditable evidence.

## Simulation integration

`SimulationEngine.summary()` now emits a `market_integrity` object by adapting simulated fills to the canonical event schema. In this synthetic fixture only, agent identities are known by construction: the Dev agent is labeled related/controlled and each other simulated agent is labeled independent. This is ground-truth metadata for simulator validation, not a rule that may be applied to real wallets.

The projection uses raw integer amounts at declared synthetic mint precision and preserves the same market, side, finality and attribution dimensions as historical replay. Real historical events must instead use evidence-backed attribution labels supplied by the data pipeline.

## Output interpretation

Flags use `info`, `review` and `high` severity. `requires_review` is true when any review/high flag exists. It is not an automatic market halt. The caller must apply policy-specific gates, confirm the data is complete, and preserve the evidence that generated the alert.

Concentration, round trips and synchronized activity can be normal. A large sell relative to depth may indicate genuine stress rather than misconduct. Pool/reference divergence can also be caused by stale or non-independent reference data. Review the source events, venue freshness and protocol state before drawing conclusions.

## Boundaries

The engine does not:
- deanonymize wallets or identify people;
- infer beneficial ownership from timing, amounts or shared infrastructure alone;
- generate, optimize or conceal wash trades;
- generate artificial candles or fake volume;
- execute trades or alter liquidity;
- prove intent, collusion or manipulation;
- replace a legal/compliance review.

The engine is only as complete as its upstream event decoder, wallet-link evidence, venue independence checks and depth observations.
