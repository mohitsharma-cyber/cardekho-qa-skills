"""
Tests for Smart Wait Engine (Phase 1).
Validates condition-based polling, text discovery, activity assertion,
screen change detection, and element coordinate extraction.
"""

import pytest
import os
import sys

skill_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if skill_root not in sys.path:
    sys.path.insert(0, skill_root)

from modules.execution.wait_engine import WaitEngine

SAMPLE_XML = """<?xml version='1.0' encoding='UTF-8' standalone='yes' ?>
<hierarchy rotation="0">
  <node index="0" text="" resource-id="com.girnarsoft.cardekho:id/main_content" bounds="[0,0][1080,2376]">
    <node index="0" text="Hyundai Creta" resource-id="com.girnarsoft.cardekho:id/tv_model_title" bounds="[48,150][600,220]" />
    <node index="1" text="₹ 11.00 Lakh" resource-id="com.girnarsoft.cardekho:id/tv_price" bounds="[48,230][450,290]" />
    <node index="2" text="VIEW OFFERS" resource-id="com.girnarsoft.cardekho:id/btn_offers" bounds="[600,2200][1032,2320]" />
  </node>
</hierarchy>"""

SAMPLE_DUMPSYS = """
  mCurrentFocus=Window{8291f04 u0 com.girnarsoft.cardekho.qa/com.cardekho.app.activity.ModelDetailsActivity}
  mFocusedApp=ActivityRecord{3821a8a u0 com.girnarsoft.cardekho.qa/com.cardekho.app.activity.ModelDetailsActivity t128}
"""


def test_wait_for_condition_success():
    """Condition that turns true after attempts must succeed within timeout."""
    counter = 0
    def condition():
        nonlocal counter
        counter += 1
        return counter >= 3

    waiter = WaitEngine()
    ok = waiter.wait_for_condition(condition, timeout=2.0, poll_interval=0.05)
    assert ok is True
    assert counter >= 3


def test_wait_for_condition_timeout():
    """Condition that never turns true must gracefully time out and return False."""
    waiter = WaitEngine()
    ok = waiter.wait_for_condition(lambda: False, timeout=0.2, poll_interval=0.05)
    assert ok is False


def test_wait_for_text_matching():
    """wait_for_text discovers target strings within XML hierarchy."""
    def mock_adb(cmd: str) -> str:
        if "cat" in cmd or "dump" in cmd:
            return SAMPLE_XML
        return ""

    waiter = WaitEngine(adb_executor=mock_adb)
    assert waiter.wait_for_text("Hyundai Creta", timeout=1.0, poll_interval=0.05) is True
    assert waiter.wait_for_text("VIEW OFFERS", timeout=1.0, poll_interval=0.05) is True
    assert waiter.wait_for_text("NonExistentString", timeout=0.1, poll_interval=0.05) is False


def test_wait_for_activity_detection():
    """wait_for_activity detects target activity in dumpsys."""
    def mock_adb(cmd: str) -> str:
        if "dumpsys window" in cmd:
            return SAMPLE_DUMPSYS
        return ""

    waiter = WaitEngine(adb_executor=mock_adb)
    assert waiter.wait_for_activity("ModelDetailsActivity", timeout=1.0, poll_interval=0.05) is True
    assert waiter.wait_for_activity("PaymentActivity", timeout=0.1, poll_interval=0.05) is False


def test_wait_for_screen_change():
    """wait_for_screen_change asserts focus deviation from previous fingerprint."""
    initial = "Window{111 u0 com.girnarsoft.cardekho/HomeActivity}"
    def mock_adb(cmd: str) -> str:
        return SAMPLE_DUMPSYS

    waiter = WaitEngine(adb_executor=mock_adb)
    assert waiter.wait_for_screen_change(prev_fingerprint=initial, timeout=1.0, poll_interval=0.05) is True


def test_wait_for_element_bounds_calculation():
    """wait_for_element returns (True, (center_x, center_y)) calculated from XML bounds."""
    def mock_adb(cmd: str) -> str:
        return SAMPLE_XML

    waiter = WaitEngine(adb_executor=mock_adb)
    found, center = waiter.wait_for_element("btn_offers", timeout=1.0, poll_interval=0.05)
    assert found is True
    assert center is not None
    # bounds: [600,2200][1032,2320] -> center_x = (600+1032)//2 = 816, center_y = (2200+2320)//2 = 2260
    assert center == (816, 2260)


def test_wait_for_idle_shimmer_clearance():
    """wait_for_idle resolves once loading shimmers disappear."""
    calls = 0
    def mock_adb(cmd: str) -> str:
        nonlocal calls
        calls += 1
        if calls <= 2:
            return "<hierarchy><node text='ShimmerLoadingView' /></hierarchy>"
        return SAMPLE_XML

    waiter = WaitEngine(adb_executor=mock_adb)
    assert waiter.wait_for_idle(timeout=1.0, poll_interval=0.05) is True
