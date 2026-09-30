"""
Tests for Execution Stop Conditions Engine (Phase 1).
Validates preflight blocking, cascading BLOCKED status,
and strict prevention of converting BLOCKED tests to PASS.
"""

import pytest
import os
import sys

skill_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if skill_root not in sys.path:
    sys.path.insert(0, skill_root)

from modules.execution.stop_conditions import StopConditionManager, StopReason


@pytest.fixture
def stop_manager():
    return StopConditionManager()


def test_preflight_blocks_when_device_disconnected(stop_manager):
    """Device disconnection halts execution immediately."""
    ok, reason, msg = stop_manager.evaluate_preflight(
        device_connected=False,
        build_available=True,
        app_installed=True,
        app_launch_ok=True,
        env_reachable=True
    )
    assert ok is False
    assert reason == StopReason.DEVICE_DISCONNECTED
    assert "No physical Android device" in msg


def test_preflight_blocks_when_build_unavailable(stop_manager):
    """Missing build/APK halts execution immediately."""
    ok, reason, msg = stop_manager.evaluate_preflight(
        device_connected=True,
        build_available=False,
        app_installed=False,
        app_launch_ok=False,
        env_reachable=True
    )
    assert ok is False
    assert reason == StopReason.BUILD_UNAVAILABLE


def test_preflight_blocks_when_app_not_installed(stop_manager):
    """Uninstalled app triggers INSTALLATION_FAILED stop condition."""
    ok, reason, msg = stop_manager.evaluate_preflight(
        device_connected=True,
        build_available=True,
        app_installed=False,
        app_launch_ok=False,
        env_reachable=True
    )
    assert ok is False
    assert reason == StopReason.INSTALLATION_FAILED


def test_preflight_blocks_when_env_unreachable(stop_manager):
    """Unreachable target server triggers ENVIRONMENT_UNAVAILABLE stop condition."""
    ok, reason, msg = stop_manager.evaluate_preflight(
        device_connected=True,
        build_available=True,
        app_installed=True,
        app_launch_ok=True,
        env_reachable=False
    )
    assert ok is False
    assert reason == StopReason.ENVIRONMENT_UNAVAILABLE


def test_apply_stop_condition_cascades_blocked_status(stop_manager):
    """Applying stop condition marks all dependent test cases BLOCKED."""
    test_cases = [
        {"id": "TC-01", "name": "Verify Home", "status": "PLANNED"},
        {"id": "TC-02", "name": "Verify Search", "status": "PLANNED"},
        {"id": "TC-03", "name": "Verify Price", "status": "PLANNED"}
    ]

    blocked = stop_manager.apply_stop_condition(
        reason=StopReason.APP_LAUNCH_FAILED,
        message="App crashed on launch with SIGSEGV",
        test_cases=test_cases
    )

    assert len(blocked) == 3
    for tc in blocked:
        assert tc["status"] == "BLOCKED"
        assert tc["block_reason"] == StopReason.APP_LAUNCH_FAILED.value
        assert "SIGSEGV" in tc["block_message"]


def test_strict_rule_never_convert_blocked_to_pass(stop_manager):
    """Safety guarantee: can_transition_to_pass strictly rejects BLOCKED status."""
    assert stop_manager.can_transition_to_pass("BLOCKED") is False
    assert stop_manager.can_transition_to_pass("FAILED") is True
    assert stop_manager.can_transition_to_pass("PLANNED") is True
