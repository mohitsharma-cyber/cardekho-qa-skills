"""
Tests for Reference Jira & WAP Parity Engines (Phase 2).
Validates:
- Valid Reference Jira resolution & behavioral analysis
- Missing Reference Jira handling
- Inaccessible Reference Jira handling
- Incomplete Reference triggering BLOCKED / CLARIFICATION REQUIRED
- WAP parity detection across 11 dimensions
- Intentional platform differences handling
"""

import pytest
import os
import sys
from unittest.mock import MagicMock

skill_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if skill_root not in sys.path:
    sys.path.insert(0, skill_root)

from modules.reference.reference_jira_resolver import ReferenceJiraResolver
from modules.reference.reference_behavior_analyzer import ReferenceBehaviorAnalyzer
from modules.reference.comparison_engine import ComparisonEngine, ComparisonStatus


@pytest.fixture
def mock_jira_client():
    client = MagicMock()
    # Mocking standard valid reference ticket
    client.get_ticket_details.side_effect = lambda key: {
        "key": key,
        "summary": "Implement On-Road Price breakdown accordion",
        "description": "When user clicks on Service Cost Details, should expand accordion showing RTO and Insurance breakdown. Tap 'Explore Now' to view offers.",
        "acceptance_criteria": [
            "Accordion must expand without screen freeze",
            "Price breakdown must show Ex-Showroom, RTO, and Insurance rows"
        ],
        "comments": [{"body": "Design approved by UX team", "author": "Designer"}],
        "attachments": [{"filename": "design_spec.png", "mimeType": "image/png"}],
        "issue_type": "Story"
    } if key == "MB2C-5555" else (
        # Incomplete reference ticket
        {
            "key": "MB2C-6666",
            "summary": "Fix price",
            "description": "Price issue",
            "acceptance_criteria": [],
            "comments": [],
            "attachments": []
        } if key == "MB2C-6666" else None
    )
    return client


def test_detect_reference_jira_from_text():
    """Detects Reference Jira IDs from common phrasing in summary/description."""
    resolver = ReferenceJiraResolver()
    assert resolver.detect_reference_jira_id(summary="Parity with MB2C-1234: Price Tab") == "MB2C-1234"
    assert resolver.detect_reference_jira_id(description="Please implement same as MB2C-9876 in Android app.") == "MB2C-9876"
    assert resolver.detect_reference_jira_id(description="Reference Jira: MB2C-4321") == "MB2C-4321"


def test_valid_reference_jira_resolution_and_analysis(mock_jira_client):
    """Fetches valid Reference Jira and generates numbered Android-specific test scenarios."""
    resolver = ReferenceJiraResolver(jira_client=mock_jira_client)
    analyzer = ReferenceBehaviorAnalyzer()

    ref_data = resolver.fetch_reference_jira("MB2C-5555")
    assert ref_data["status"] == "FETCHED"
    assert ref_data["reference_id"] == "MB2C-5555"

    analysis = analyzer.analyze_reference_jira(ref_data)
    assert analysis["status"] == "ANALYZED"
    assert analysis["is_sufficient"] is True
    assert analysis["verdict"] == "READY_FOR_EXECUTION"
    assert len(analysis["android_test_scenarios"]) >= 2
    assert "TC-REF-01" in [tc["test_case_id"] for tc in analysis["android_test_scenarios"]]


def test_missing_reference_jira():
    """When no Reference Jira ID is provided, returns MISSING_ID deterministically."""
    resolver = ReferenceJiraResolver()
    res = resolver.fetch_reference_jira(None)
    assert res["status"] == "MISSING_ID"
    assert res["reference_id"] is None


def test_inaccessible_reference_jira(mock_jira_client):
    """When Reference Jira cannot be fetched (404/403), returns INACCESSIBLE without guessing."""
    resolver = ReferenceJiraResolver(jira_client=mock_jira_client)
    res = resolver.fetch_reference_jira("MB2C-9999")
    assert res["status"] == "INACCESSIBLE"
    assert "could not be accessed" in res["error"]


def test_incomplete_reference_triggers_blocked_clarification(mock_jira_client):
    """Incomplete reference lacking acceptance criteria or functional detail is marked BLOCKED."""
    resolver = ReferenceJiraResolver(jira_client=mock_jira_client)
    analyzer = ReferenceBehaviorAnalyzer()

    ref_data = resolver.fetch_reference_jira("MB2C-6666")
    analysis = analyzer.analyze_reference_jira(ref_data)

    assert analysis["status"] == "INSUFFICIENT_INFORMATION"
    assert analysis["verdict"] == "BLOCKED / CLARIFICATION REQUIRED"
    assert analysis["is_sufficient"] is False
    assert len(analysis["gaps"]) > 0


def test_wap_parity_detection_and_dimension_mapping():
    """Identifies 'Implement in App same as WAP' and maps 11 comparison dimensions."""
    analyzer = ReferenceBehaviorAnalyzer()
    res = analyzer.detect_and_analyze_wap_reference(
        jira_text="Implement in App same as WAP: https://www.cardekho.com/overview",
        brand="cardekho"
    )
    assert res["is_wap_reference"] is True
    assert "cardekho.com" in res["target_wap_url"]
    assert len(res["comparison_dimensions"]) == 11
    assert "UI" in res["comparison_dimensions"]
    assert "CTA" in res["comparison_dimensions"]
    assert "API Behavior" in res["comparison_dimensions"]


def test_structured_comparison_model_pass_and_fail():
    """ComparisonEngine returns structured comparison model with PASS and FAIL statuses."""
    comp = ComparisonEngine()

    item_pass = comp.compare_item(area="CTA", reference="Explore Now", android="Explore Now")
    assert item_pass["area"] == "CTA"
    assert item_pass["reference"] == "Explore Now"
    assert item_pass["android"] == "Explore Now"
    assert item_pass["status"] == ComparisonStatus.PASS.value

    item_fail = comp.compare_item(area="CTA", reference="Explore Now", android="Book Now")
    assert item_fail["status"] == ComparisonStatus.FAIL.value
    assert "Mismatch in CTA" in item_fail["rationale"]


def test_intentional_platform_differences():
    """Intentional mobile UX adaptations are marked EXPECTED_PLATFORM_DIFFERENCE."""
    comp = ComparisonEngine()

    item = comp.compare_item(
        area="Navigation",
        reference="Desktop top navigation bar",
        android="Android native bottom drawer",
        is_platform_difference=True,
        diff_rationale="Android mobile app uses bottom navigation for thumb accessibility."
    )
    assert item["status"] == ComparisonStatus.EXPECTED_PLATFORM_DIFFERENCE.value
    assert "thumb accessibility" in item["rationale"]


def test_complete_wap_parity_evaluation():
    """Evaluates complete 11-dimension parity comparison between WAP and Android specs."""
    comp = ComparisonEngine()

    wap_spec = {
        "UI": "Card grid with 12dp elevation",
        "Functionality": "Calculates on-road price dynamically",
        "Data": "Creta SX (O) Diesel - ₹ 19.20 Lakh",
        "CTA": "View Offers",
        "Navigation": "Opens price tab",
        "Filters": "Fuel type filter",
        "Validation": "Pincode mandatory",
        "Loading": "Shimmer skeleton",
        "Empty State": "No models found graphic",
        "Error State": "Retry connection banner",
        "API Behavior": "GET /api/v1/price 200 OK"
    }

    android_spec = dict(wap_spec)
    # Introduce one intentional difference and one failure
    known_diffs = {"Navigation": "Android uses native back key navigation instead of breadcrumb"}
    android_spec["CTA"] = "Check Details"  # Discrepancy

    eval_result = comp.compare_wap_parity(wap_spec, android_spec, known_differences=known_diffs)
    assert eval_result["overall_status"] == "FAIL"  # Because CTA failed
    assert eval_result["metrics"]["failed"] == 1
    assert eval_result["metrics"]["expected_platform_differences"] == 1
    assert eval_result["metrics"]["passed"] == 9
    assert len(eval_result["discrepancies"]) == 1
    assert eval_result["discrepancies"][0]["area"] == "CTA"
