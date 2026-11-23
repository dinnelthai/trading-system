# Multi-Venue Route Selection

**Status:** Implemented on `feat/pumpswap-state-adapter` as a pure route-choice model with a no-trade option. Venue quote adapters, historical calibration and execution are not implemented.

## Input contract

A RouteIntent describes one independent user order:
- side (buy or sell);
- input amount;
- independent reference price;
- submission timestamp;
- quote-age, latency, execution-cost and success-probability limits;
- optional latency, staleness and failure penalties.

A VenueQuote is a precomputed quote from one venue:
- exact side and input amount;
- net output amount after all venue fees;
- executable input depth;
- quote timestamp and expected latency;
- estimated settlement success probability;
- fee amount retained as a diagnostic field.

The module requires at most one candidate quote per venue for a single intent.

## Benchmark and cost

For a buy, benchmark output is:

[
Q_{benchmark}^{base}=rac{Q_{input}}{P^*}
]

For a sell:

[
Q_{benchmark}^{quote}=B_{input}P^*
]

Execution cost is:

[
C_{exec,bps}=
left(1-rac{Output_{net}}{Output_{benchmark}}ight)10,000
]

The quote's output is already net of all venue fees. The fee diagnostic is not deducted again.

Expected route cost includes execution, failure, latency and staleness:

[
E[C]=pC_{exec}+(1-p)C_{failure}
+lambda_L Latency+lambda_A QuoteAge
]

Only candidates meeting depth, quote freshness, latency, success-probability and maximum execution-cost constraints are eligible. The lowest expected-cost eligible venue wins. Ties break by lower latency and then venue ID. If none qualifies, the decision is `NO_TRADE`.

## Boundaries

- This module selects among supplied quotes; it does not fetch them.
- Reference price must come from an independent, valid reference adapter.
- Net output and executable depth must be produced by protocol-correct venue adapters.
- It currently models one venue per route; split routing and multi-hop path composition are not implemented.
- It does not construct, sign or submit transactions.
- It does not optimize trading volume or create synthetic demand.
- Route-choice elasticity and trader response parameters remain synthetic until calibrated against observed intent/route/fill data.
