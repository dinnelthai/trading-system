import pytest

from pump_sim.routing import RouteIntent, VenueQuote, choose_route


def intent(side="buy", **overrides):
    values = {
        "side": side,
        "input_amount": 1_000.0 if side == "buy" else 10.0,
        "reference_price": 100.0,
        "submitted_at_ms": 1_000,
        "max_quote_age_ms": 500,
        "max_latency_ms": 200,
        "max_execution_cost_bps": 500,
        "min_success_probability": 0.9,
        "failure_penalty_bps": 100,
    }
    values.update(overrides)
    return RouteIntent(**values)


def buy_quote(venue, output, **overrides):
    values = {
        "venue_id": venue,
        "side": "buy",
        "input_amount": 1_000.0,
        "output_amount": output,
        "executable_input_depth": 5_000.0,
        "quote_timestamp_ms": 990,
        "expected_latency_ms": 50,
        "success_probability": 0.99,
        "fee_quote_equiv": 0.0,
    }
    values.update(overrides)
    return VenueQuote(**values)


def test_buy_route_selects_lowest_expected_execution_cost():
    result = choose_route(
        intent(),
        [
            buy_quote("venue-a", 9.95),
            buy_quote("venue-b", 9.97),
            buy_quote("venue-c", 9.90),
        ],
    )
    assert result.action == "ROUTE"
    assert result.selected_venue_id == "venue-b"
    assert result.expected_cost_bps == pytest.approx(30.7)


def test_sell_route_uses_quote_output_against_reference_benchmark():
    result = choose_route(
        intent("sell"),
        [
            VenueQuote("venue-a", "sell", 10, 990, 100, 990, 50, 0.99),
            VenueQuote("venue-b", "sell", 10, 995, 100, 990, 80, 0.99),
        ],
    )
    assert result.action == "ROUTE"
    assert result.selected_venue_id == "venue-b"
    assert result.expected_cost_bps == pytest.approx(50.5)


def test_stale_quote_is_rejected():
    result = choose_route(intent(), [buy_quote("stale", 9.99, quote_timestamp_ms=400)])
    assert result.action == "NO_TRADE"
    assert "stale_quote" in result.assessments[0].rejection_reasons


def test_future_quote_is_rejected():
    result = choose_route(intent(), [buy_quote("future", 9.99, quote_timestamp_ms=1001)])
    assert result.action == "NO_TRADE"
    assert "future_quote" in result.assessments[0].rejection_reasons


def test_insufficient_executable_depth_is_rejected():
    result = choose_route(
        intent(),
        [buy_quote("shallow", 9.99, executable_input_depth=999)],
    )
    assert result.action == "NO_TRADE"
    assert "insufficient_executable_depth" in result.assessments[0].rejection_reasons


def test_latency_and_success_probability_constraints_are_applied():
    result = choose_route(
        intent(),
        [
            buy_quote("slow", 9.99, expected_latency_ms=250),
            buy_quote("unreliable", 9.99, success_probability=0.5),
        ],
    )
    assert result.action == "NO_TRADE"
    assert "latency_limit" in result.assessments[0].rejection_reasons
    assert "success_probability" in result.assessments[1].rejection_reasons


def test_execution_cost_limit_provides_no_trade_option():
    result = choose_route(
        intent(max_execution_cost_bps=10),
        [buy_quote("expensive", 9.90)],
    )
    assert result.action == "NO_TRADE"
    assert "execution_cost_limit" in result.assessments[0].rejection_reasons


def test_side_and_input_amount_mismatch_are_rejected():
    result = choose_route(
        intent(),
        [
            buy_quote("wrong-side", 9.99, side="sell"),
            buy_quote("wrong-size", 9.99, input_amount=500),
        ],
    )
    assert result.action == "NO_TRADE"
    assert "side_mismatch" in result.assessments[0].rejection_reasons
    assert "input_amount_mismatch" in result.assessments[1].rejection_reasons


def test_fee_is_already_reflected_in_net_output_and_not_subtracted_twice():
    result = choose_route(
        intent(),
        [buy_quote("fee-included", 9.95, fee_quote_equiv=50)],
    )
    assert result.assessments[0].execution_cost_bps == pytest.approx(50.5)
    assert result.expected_cost_bps == pytest.approx(50)


def test_latency_and_quote_age_penalties_affect_expected_cost():
    result = choose_route(
        intent(
            latency_penalty_bps_per_ms=0.1,
            staleness_penalty_bps_per_ms=0.2,
        ),
        [buy_quote("route", 9.99, quote_timestamp_ms=900, expected_latency_ms=100)],
    )
    # 10 bps execution cost + 10 bps latency + 20 bps staleness.
    assert result.expected_cost_bps == pytest.approx(40.9)


def test_equal_expected_cost_breaks_ties_by_latency_then_venue_id():
    result = choose_route(
        intent(),
        [
            buy_quote("venue-b", 9.99, expected_latency_ms=80),
            buy_quote("venue-c", 9.99, expected_latency_ms=50),
            buy_quote("venue-a", 9.99, expected_latency_ms=50),
        ],
    )
    assert result.selected_venue_id == "venue-a"


def test_duplicate_venue_quotes_are_rejected():
    with pytest.raises(ValueError, match="one quote per venue"):
        choose_route(intent(), [buy_quote("same", 9.99), buy_quote("same", 9.98)])


def test_invalid_route_intent_and_quote_values_are_rejected():
    with pytest.raises(ValueError, match="side"):
        RouteIntent("hold", 1, 1, 0)
    with pytest.raises(ValueError, match="success_probability"):
        RouteIntent("buy", 1, 1, 0, min_success_probability=1.1)
    with pytest.raises(ValueError, match="output_amount"):
        VenueQuote("v", "buy", 1, 0, 10, 0, 10, 1)
