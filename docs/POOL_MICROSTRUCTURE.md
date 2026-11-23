# R03 — PumpSwap Pool Microstructure, LP Inventory, and Candle Distortion

**Status:** fee-aware pool depth, LP ownership accounting, pool-state event diagnostics, execution-versus-spot price separation, and true-versus-observed candle diagnostics are implemented on `main`.

## 1. R03 questions

R02 modeled the bonding curve and the completing V3 buy. R03 starts after the pool exists and asks:

1. How much can the pool actually buy or sell before marginal price moves by 1%, 5%, or 10%?
2. How do swaps, LP additions, and LP withdrawals change reserves, (k), and executable depth?
3. Who owns the LP shares, and how much liquidity is locked, agent-owned, or unassigned?
4. Why can a chart candle differ from the pool's marginal spot price?
5. How much chart distortion comes from delayed, dropped, or duplicated feed events rather than real executions?

This stage records market state and diagnostics. It does not add a live trading or transaction-ordering mechanism.

## 2. Three prices, not one

For pool reserves (x) tokens and (y) quote units:

[
P_{spot}=rac{y}{x}
]

For a swap with quote amount (Q) and token amount (T), the execution/VWAP price is:

[
P_{exec}=rac{Q}{T}
]

The post-swap marginal price is:

[
P_{after}=rac{y'}{x'}
]

These are not interchangeable.

- **Pre-trade spot** is the marginal price before the swap.
- **Execution price** is the average price paid/received across the AMM curve.
- **Post-trade spot** is the new marginal price after reserves change.

The trade candle uses the execution price because it is derived from an actual simulated swap. The engine separately records pre- and post-trade spot prices and both execution slippage and marginal price impact.

For a buy, adverse execution slippage is:

[
S_{buy}=left(rac{P_{exec}}{P_{before}}-1ight)10{,}000
]

For a sell:

[
S_{sell}=left(1-rac{P_{exec}}{P_{before}}ight)10{,}000
]

Marginal price impact is:

[
I=left(rac{P_{after}}{P_{before}}-1ight)10{,}000
]

The two metrics describe different things. A large order can have a much larger marginal price impact than its average execution-price deviation from the pre-trade spot.

## 3. Fee-aware pool depth

The previous constant-product closed forms assume no fee. R03 solves the actual pool implementation, where part of the swap fee stays in reserves for LPs and the protocol portion leaves the pool.

Let:

- (f): total pool fee rate;
- (l): share of the fee retained by LPs;
- (c=f(1-l)): protocol fee fraction removed from reserves;
- (x,y): pre-swap token and quote reserves.

### 3.1 Buy depth

For gross quote input (q):

[
n=(1-f)q
]

[
x'=xrac{y}{y+n}
]

[
y'=y+q-cq
]

The exact marginal-price ratio is:

[
rac{P'}{P}=
left(1+(1-c)rac{q}{y}ight)
left(1+(1-f)rac{q}{y}ight)
]

For a target upward price impact (delta), define (g=q/y), (a=1-c), and (b=1-f). Then:

[
abg^2+(a+b)g-delta=0
]

The positive root gives gross buy-side depth:

[
q_{buy}=yrac{sqrt{(a+b)^2+4abdelta}-(a+b)}{2ab}
]

The engine also reports the net swap input and token output.

### 3.2 Sell depth

For token input (T), gross quote removed from reserves is:

[
q_g=rac{yT}{x+T}
]

The user receives:

[
q_{user}=q_g(1-f)
]

The pool quote reserve falls by (q_g(1-c)), because LP-retained fees remain in reserves.

Let (t=T/x). The post-swap marginal-price ratio is:

[
rac{P'}{P}=rac{1+ct}{(1+t)^2}
]

For a target downward price impact (delta):

[
(1-delta)t^2+[2(1-delta)-c]t-delta=0
]

The positive root determines token sell depth. The simulator reports token input, gross quote removed, and net quote received.

### 3.3 Reported depth bands

The engine reports fee-aware depth for:

- 1% marginal price impact;
- 5% marginal price impact;
- 10% marginal price impact.

Buy depth is gross quote paid by the trader. Sell depth is net quote received by the seller. Both are calculated against actual pool reserves and the configured fee split.

## 4. LP changes and pool invariants

The pool tracks:

[
k=xy
]

[
TVL_{quote}=xP+y=2y
]

The quote-denominated TVL formula is valid because the current marginal price is (y/x).

A proportional liquidity addition or withdrawal changes pool size and executable depth but does not change spot price:

[
rac{y+Delta y}{x+Delta x}=rac{y}{x}
]

The simulator uses ratio-matched deposits: if the wallet supplies an imbalanced token/quote pair, only the amount matching the pool ratio is added; the excess remains in the wallet. Withdrawals are pro-rata claims on reserves.

R03 records four event categories:

- `migration`: the pool is created from post-completion reserves;
- `liquidity_add`: Dev or an LP agent adds matched inventory;
- `liquidity_remove`: an LP owner withdraws its share;
- `swap`: a pool trade changes reserves and marginal price.

For each event the optional trace stores before/after reserves, spot price, (k), LP shares, and 1%/5% depth. Set `record_pool_event_trace=true` to include the event trace in the run summary. It is disabled by default to keep Monte Carlo output compact.

### LP ownership

The model distinguishes:

- initial locked LP shares;
- shares held by identified agents;
- unassigned/unlocked shares.

The LP ownership HHI is:

[
HHI_{LP}=sum_ileft(rac{s_i}{S_{LP}}ight)^2
]

Locked and unassigned shares are separate buckets. Agent shares are attributed by agent ID. This is an LP-share ownership concentration measure, not a token-holder HHI.

## 5. True candles versus observed candles

The simulator keeps two separate trade-derived candle streams:

### True execution candles

Built from every successful simulated swap, using:

- execution/VWAP price;
- quote volume;
- token volume;
- buy/sell quote volume;
- buy/sell trade count.

LP additions and removals are not trades and do not create OHLCV volume. A proportional LP change does not create a price candle because it does not change spot price.

### Observed feed candles

Built from feed events after simulated latency. Events can be:

- dropped;
- delayed into a later candle interval;
- duplicated.

A duplicate affects observed volume and trade counts but does not create a second true execution. A delayed event may move the observed OHLC update into a different interval. These are data-feed distortions, not new market trades.

### Distortion metrics

R03 compares matched true/observed candle intervals and reports:

- open, high, low, and close MAE/max error in bps;
- volume MAE in quote units and relative percentage;
- buy-volume and sell-volume MAE;
- trade-count MAE;
- buy/sell imbalance MAE;
- matched and unmatched bar counts;
- OHLC mismatch count;
- observed/true total volume ratio.

An unmatched candle can be caused by feed latency moving the event across a bar boundary or by dropped/duplicated events. The simulator does not fabricate true volume to fill empty bars.

## 6. Numerical invariants and interpretation

1. A balanced LP add/remove should preserve spot price to floating-point tolerance.
2. A liquidity addition should increase 1%/5% executable depth; a withdrawal should reduce it.
3. Fee-aware depth must reproduce the requested marginal-price impact when applied to the pool's actual `buy` or `sell` method.
4. LP-retained fees increase pool reserves and (k); protocol fees are excluded from the pool.
5. True candle volume equals successful swap volume, not liquidity events.
6. Observed candle volume may differ from true volume due to feed drops, delays, and duplicates.
7. Execution/VWAP price and post-swap spot price must remain separate in every report.

## 7. Implementation

- `src/pump_sim/pool_analytics.py`: exact fee-aware depth, LP ownership, and candle comparison metrics.
- `src/pump_sim/core.py`: pool state event capture, swap execution slippage, side-aware candles, pool summary, and Monte Carlo aggregation.
- `configs/default.json`: optional `record_pool_event_trace` switch.
- `tests/test_pool_analytics.py`: fee-aware depth parity, LP ownership, and candle distortion tests.
- `tests/test_core.py`: balanced LP price invariance, depth changes, swap event trace, and execution slippage tests.

## 8. Limitations

- The pool is still a continuous floating-point constant-product AMM, not an instruction-exact PumpSwap implementation.
- LP additions are ratio-matched; protocol-specific account constraints, minimum liquidity, position NFTs, and exact token atom rounding are not modeled.
- The feed model represents generic drops, duplicates, and latency; it is not calibrated to a specific RPC/indexer provider.
- No active sandwich transaction sequence, wash trading, fake volume, or deceptive coordination is implemented. MEV remains an abstract risk overlay.
- A price candle represents executed swap VWAP, not a sampled reserve spot-price series. A separate spot-state time series can be added if a specific charting/indexer convention requires it.
