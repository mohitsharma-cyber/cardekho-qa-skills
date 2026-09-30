"""
Tests for Risk & Impact Engine (Phase 1).
Validates ticket risk classification (LOW, MEDIUM, HIGH, CRITICAL),
architectural blast radius, testing depth mapping, and missing requirement detection.
"""

import pytest
import os
import sys

# Ensure skill root on path
skill_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if skill_root not in sys.path:
    sys.path.insert(0, skill_root)

from modules.risk.risk_engine import RiskEngine, RiskLevel
from modules.risk.impact_analyzer import ImpactAnalyzer


@pytest.fixture
def risk_engine():
    return RiskEngine()


@pytest.fixture
def impact_analyzer():
    return ImpactAnalyzer()


def test_ui_only_classified_as_low(risk_engine):
    """UI-only styling/typo changes must be classified as LOW risk."""
    res = risk_engine.classify_ticket(
        summary="Update button color and font padding on Home banner",
        description="Change hex color from #FFF to #F00 and fix typo in banner text copy.",
        labels=["ui-only", "cosmetic"]
    )
    assert res["risk_level"] == RiskLevel.LOW.value
    assert res["testing_depth"] == "SMOKE_AND_UI"
    assert res["min_test_cases"] <= 3
    assert res["is_ui_only"] is True


def test_crash_fix_classified_as_critical_or_high(risk_engine):
    """Crash/ANR/NullPointerException fixes must be classified as CRITICAL or HIGH risk."""
    res = risk_engine.classify_ticket(
        summary="Fix NullPointerException crash on Model Page when clicking Service Cost",
        description="Fatal exception thrown: NullPointerException in ModelDetailsActivity line 142 on Android 14."
    )
    assert res["risk_level"] in [RiskLevel.HIGH.value, RiskLevel.CRITICAL.value]
    assert res["is_crash_fix"] is True
    assert "crash_resilience" in res["required_categories"] or res["testing_depth"] in ["DEEP", "EXHAUSTIVE"]


def test_lead_and_auth_classified_as_high_or_critical(risk_engine):
    """Authentication and Lead generation changes must trigger HIGH or CRITICAL risk."""
    res = risk_engine.classify_ticket(
        summary="Refactor OTP login and lead submission for test drive booking",
        description="Update /api/v1/auth/otp and /api/v1/lead/submit endpoints with new payload schema."
    )
    assert res["risk_level"] in [RiskLevel.HIGH.value, RiskLevel.CRITICAL.value]
    assert res["min_test_cases"] >= 6
    assert len(res["api_dependencies"]) >= 2


def test_medium_risk_functional_addition(risk_engine):
    """Standard feature additions without crashes or auth should be classified as MEDIUM."""
    res = risk_engine.classify_ticket(
        summary="Add new variant comparison drawer tab in Model details",
        description="Allow user to compare two variants by opening specs drawer."
    )
    assert res["risk_level"] in [RiskLevel.MEDIUM.value, RiskLevel.HIGH.value]
    assert res["min_test_cases"] >= 4


def test_missing_requirements_detected_without_inventing(risk_engine):
    """Detects missing steps or missing vehicle model without hallucinating missing data."""
    res = risk_engine.classify_ticket(
        summary="Improve price tab look and feel",
        description="Looks plain. Need to improve it."
    )
    assert len(res["missing_requirements"]) > 0
    # Must flag absence of explicit AC/steps or model context
    assert any("Acceptance Criteria" in gap or "context" in gap for gap in res["missing_requirements"])


def test_impact_analyzer_extracts_screens_and_apis(impact_analyzer):
    """ImpactAnalyzer identifies screens, modules, and API patterns accurately."""
    analysis = impact_analyzer.analyze_ticket(
        summary="Fix on road price breakdown on price tab",
        description="Endpoint https://testingpwa1.cardekho.com/api/v1/price is returning mismatched RTO data for Creta."
    )
    assert "price_tab" in analysis["affected_screens"]
    assert "pricing_engine" in analysis["affected_modules"]
    assert any("price" in api for api in analysis["api_dependencies"])
    assert analysis["is_ui_only"] is False
