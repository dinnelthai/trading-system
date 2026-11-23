import pytest

from pump_sim.orchestrator import (
    Action,
    DecisionContext,
    DecisionHorizon,
    HysteresisLatch,
    LifecycleState,
    decide,
)


def context(**overrides):
    values = {
        "horizon": DecisionHorizon.TACTICAL,
        "lifecycle": LifecycleState.MATURE,
        "candidate_action": Action.ADD,
        "integrity_ok": True,
        "data_fresh": True,
        "accounting_reconciled": True,
        "cash_reserve_ok": True,
        "market_quality_status": "PASS",
        "add_authorized": True,
        "remove_authorized": True,
        "withdrawal_market_quality_safe": True,
        "capital_budget_approved": True,
    }
    values.update(overrides)
    return DecisionContext(**values)


def test_add_is_allowed_only_after_all_tactical_gates_pass():
    result = decide(context())
    assert result.action == Action.ADD
    assert result.reason_code == "all_add_gates_passed"
    assert result.risk_increasing is True
    assert result.vetoes == ()


def test_fast_horizon_never_adds_or_removes_under_normal_conditions():
    result = decide(context(horizon=DecisionHorizon.FAST))
    assert result.action == Action.OBSERVE
    assert result.reason_code == "execution_horizon_observe_only"


def test_curve_and_migration_states_cannot_add_pool_liquidity():
    for lifecycle in (LifecycleState.CURVE, LifecycleState.MIGRATION_PENDING):
        result = decide(context(lifecycle=lifecycle))
        assert result.action == Action.OBSERVE
        assert result.reason_code == "pool_not_ready"


def test_integrity_failure_or_paused_quality_forces_pause():
    integrity = decide(context(integrity_ok=False))
    quality = decide(context(market_quality_status="PAUSED"))
    assert integrity.action == Action.PAUSE
    assert quality.action == Action.PAUSE


def test_stale_data_and_accounting_mismatch_force_reconciliation():
    stale = decide(context(data_fresh=False))
    mismatch = decide(context(accounting_reconciled=False))
    assert stale.action == Action.RECONCILE
    assert mismatch.action == Action.RECONCILE


def test_cash_reserve_failure_pauses_new_actions():
    result = decide(context(cash_reserve_ok=False))
    assert result.action == Action.PAUSE
    assert result.reason_code == "cash_reserve_gate"


def test_degraded_market_quality_vetoes_add():
    result = decide(context(market_quality_status="DEGRADED"))
    assert result.action == Action.HOLD
    assert result.risk_increasing is False
    assert "market_quality_or_minimum_depth_gate" in result.vetoes


def test_minimum_depth_breach_vetoes_add():
    result = decide(context(minimum_depth_breached=True))
    assert result.action == Action.HOLD


def test_tail_risk_breach_allows_only_authorized_safe_reduction():
    safe = decide(context(tail_risk_breached=True))
    unsafe = decide(
        context(tail_risk_breached=True, withdrawal_market_quality_safe=False)
    )
    assert safe.action == Action.REMOVE
    assert safe.risk_increasing is False
    assert unsafe.action == Action.PAUSE


def test_stress_lifecycle_requires_risk_reduction_or_pause():
    result = decide(context(lifecycle=LifecycleState.STRESS))
    assert result.action == Action.REMOVE
    blocked = decide(
        context(lifecycle=LifecycleState.STRESS, remove_authorized=False)
    )
    assert blocked.action == Action.PAUSE


def test_degraded_market_can_remove_only_when_post_withdrawal_quality_is_safe():
    result = decide(
        context(
            candidate_action=Action.REMOVE,
            market_quality_status="DEGRADED",
            withdrawal_market_quality_safe=True,
        )
    )
    assert result.action == Action.REMOVE


def test_remove_requires_authorization_and_post_withdrawal_safety():
    unauthorized = decide(context(candidate_action=Action.REMOVE, remove_authorized=False))
    unsafe = decide(
        context(candidate_action=Action.REMOVE, withdrawal_market_quality_safe=False)
    )
    assert unauthorized.action == Action.HOLD
    assert unsafe.action == Action.HOLD


def test_strategic_add_requires_capital_budget_approval():
    blocked = decide(
        context(horizon=DecisionHorizon.STRATEGIC, capital_budget_approved=False)
    )
    allowed = decide(
        context(horizon=DecisionHorizon.STRATEGIC, capital_budget_approved=True)
    )
    assert blocked.action == Action.HOLD
    assert allowed.action == Action.ADD


def test_recovery_and_early_pool_do_not_use_mature_add_policy():
    recovery = decide(context(lifecycle=LifecycleState.RECOVERY))
    early = decide(context(lifecycle=LifecycleState.EARLY_POOL))
    assert recovery.action == Action.HOLD
    assert early.action == Action.HOLD


def test_cooldown_blocks_normal_actions_but_does_not_hide_risk_breach():
    normal = decide(context(cooldown_active=True))
    risk = decide(context(cooldown_active=True, inventory_limit_breached=True))
    assert normal.action == Action.HOLD
    assert risk.action == Action.PAUSE


def test_terminal_and_paused_lifecycle_are_non_add_states():
    terminal = decide(context(lifecycle=LifecycleState.TERMINAL))
    paused = decide(context(lifecycle=LifecycleState.PAUSED))
    assert terminal.action == Action.OBSERVE
    assert paused.action == Action.PAUSE


def test_hysteresis_requires_persistent_condition_to_activate():
    latch = HysteresisLatch()
    assert latch.update(True, timestamp_s=0, activate_after_s=10, deactivate_after_s=5) is False
    assert latch.update(True, timestamp_s=5, activate_after_s=10, deactivate_after_s=5) is False
    assert latch.update(True, timestamp_s=10, activate_after_s=10, deactivate_after_s=5) is True
    assert latch.active is True


def test_hysteresis_requires_persistent_clear_condition_to_deactivate():
    latch = HysteresisLatch(active=True)
    assert latch.update(False, timestamp_s=10, activate_after_s=10, deactivate_after_s=5) is True
    assert latch.update(False, timestamp_s=14, activate_after_s=10, deactivate_after_s=5) is True
    assert latch.update(False, timestamp_s=15, activate_after_s=10, deactivate_after_s=5) is False
    assert latch.active is False


def test_hysteresis_resets_pending_activation_when_condition_clears():
    latch = HysteresisLatch()
    assert latch.update(True, timestamp_s=0, activate_after_s=10, deactivate_after_s=5) is False
    assert latch.update(False, timestamp_s=5, activate_after_s=10, deactivate_after_s=5) is False
    assert latch.update(True, timestamp_s=6, activate_after_s=10, deactivate_after_s=5) is False
    assert latch.update(True, timestamp_s=16, activate_after_s=10, deactivate_after_s=5) is True


def test_hysteresis_rejects_non_monotonic_time():
    latch = HysteresisLatch()
    latch.update(False, timestamp_s=10, activate_after_s=1, deactivate_after_s=1)
    with pytest.raises(ValueError, match="monotonic"):
        latch.update(True, timestamp_s=9, activate_after_s=1, deactivate_after_s=1)


def test_decision_context_rejects_invalid_types_and_quality_status():
    with pytest.raises(ValueError, match="market_quality_status"):
        context(market_quality_status="unknown")
    with pytest.raises(TypeError, match="integrity_ok"):
        context(integrity_ok=1)
