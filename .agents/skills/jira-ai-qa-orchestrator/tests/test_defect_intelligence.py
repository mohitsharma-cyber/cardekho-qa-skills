"""
Tests for Defect Intelligence & Bug Card Generation (Phase 4).
Validates:
- Probable Layer classification (UI, API, Backend, Data, Configuration, Environment)
- Severity and Priority suggestion
- Duplicate bug detection
- Standard Bug Card formatting
- Critical Safety Rule: Explicit user approval required before bug creation
"""

import pytest
import os
import sys

skill_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if skill_root not in sys.path:
    sys.path.insert(0, skill_root)

from modules.defects.defect_analyzer import DefectAnalyzer
from modules.defects.duplicate_detector import DuplicateDetector
from modules.defects.severity_classifier import SeverityClassifier
from modules.jira.jira_client import JiraClient


@pytest.fixture
def defect_analyzer():
    mock_jira = JiraClient(mock_mode=True)
    dup_detector = DuplicateDetector(jira_client=mock_jira)
    return DefectAnalyzer(duplicate_detector=dup_detector)


def test_probable_layer_classification(defect_analyzer):
    """Accurately identifies the probable layer of failure."""
    # 1. UI Layer
    ui_defect = defect_analyzer.analyze_failure(
        ticket="MB2C-2001", test_case_id="TC-01", summary="CTA button missing",
        steps=["Open page"], expected="View Offers button visible", actual="Button missing from view hierarchy",
        error_message="NoSuchElementException: View with id btn_offers not found"
    )
    assert ui_defect["probable_layer"] == "UI"

    # 2. API Layer
    api_defect = defect_analyzer.analyze_failure(
        ticket="MB2C-2001", test_case_id="TC-02", summary="Search API 400 error",
        steps=["Search 'Creta'"], expected="Results displayed", actual="API returned 400 Bad Request",
        api_status=400, error_message="API status 400"
    )
    assert api_defect["probable_layer"] == "API"

    # 3. Backend Layer
    backend_defect = defect_analyzer.analyze_failure(
        ticket="MB2C-2001", test_case_id="TC-03", summary="Server 500 on Lead Submit",
        steps=["Submit lead"], expected="Lead created", actual="Internal Server Error",
        api_status=500, error_message="500 Internal Server Error in MySQL connection"
    )
    assert backend_defect["probable_layer"] == "Backend"

    # 4. Data Layer
    data_defect = defect_analyzer.analyze_failure(
        ticket="MB2C-2001", test_case_id="TC-04", summary="Price calculation error",
        steps=["Open price tab"], expected="RTO ₹ 1,50,000", actual="RTO calculated as ₹ 90,000",
        error_message="Price mismatch: calculation formula discrepancy"
    )
    assert data_defect["probable_layer"] == "Data"

    # 5. Configuration Layer
    config_defect = defect_analyzer.analyze_failure(
        ticket="MB2C-2001", test_case_id="TC-05", summary="App pointing to wrong server",
        steps=["Check Change URL"], expected="testingpwa1", actual="staging.cardekho.com",
        error_message="Wrong base URL configured"
    )
    assert config_defect["probable_layer"] == "Configuration"

    # 6. Environment Layer
    env_defect = defect_analyzer.analyze_failure(
        ticket="MB2C-2001", test_case_id="TC-06", summary="Device offline during testing",
        steps=["Execute tap"], expected="Device responds", actual="ADB device offline",
        error_message="device offline: connection refused"
    )
    assert env_defect["probable_layer"] == "Environment"


def test_severity_classification():
    """SeverityClassifier maps fatal crashes to Blocker and cosmetic issues to Minor."""
    sev1, prio1 = SeverityClassifier.classify(
        summary="Fatal NullPointerException on Service Cost click",
        error_message="FATAL EXCEPTION: main NullPointerException"
    )
    assert sev1 == "Blocker"
    assert prio1 == "Highest"

    sev2, prio2 = SeverityClassifier.classify(
        summary="Minor text alignment discrepancy on footer label",
        error_message="Padding is 8dp instead of 12dp",
        probable_layer="UI"
    )
    assert sev2 == "Minor"
    assert prio2 == "Low"


def test_duplicate_defect_detection():
    """DuplicateDetector flags matching existing bugs and provides candidates."""
    detector = DuplicateDetector()
    existing = [
        {"ticket_key": "MB2C-1500", "summary": "NullPointerException crash on Model Page when clicking Service Cost"}
    ]

    dup_res = detector.check_duplicate(
        summary="NullPointerException crash on Model Page clicking Service Cost Details",
        existing_bugs=existing
    )
    assert dup_res["has_duplicate"] is True
    assert dup_res["duplicate_count"] >= 1
    assert dup_res["duplicates"][0]["key"] == "MB2C-1500"


def test_bug_card_structure_and_mandatory_approval_gate(defect_analyzer):
    """Bug Card contains all required sections and enforces explicit human approval."""
    defect = defect_analyzer.analyze_failure(
        ticket="MB2C-3001",
        test_case_id="TC-08",
        summary="On-Road Price accordion fails to expand on tap",
        steps=["Launch CarDekho App", "Search 'Creta'", "Go to Price tab", "Click Service Cost Details"],
        expected="Service Cost accordion expands smoothly displaying RTO and Insurance breakdown",
        actual="Accordion does not expand; UI remains frozen",
        environment="testingpwa1",
        device="OnePlus 12R (CPH2585)",
        build="#142",
        evidence_path="reports/evidence/screenshots/MB2C-3001_FAIL.png",
        error_message="AssertionError: View did not expand within 5s timeout"
    )

    card = defect["bug_card"]

    # Verify all required Bug Card sections
    required_sections = [
        "Summary:",
        "Environment:",
        "Device:",
        "Build:",
        "Steps:",
        "Expected:",
        "Actual:",
        "Evidence:",
        "Probable Layer:",
        "Severity/Priority suggestion:"
    ]
    for sec in required_sections:
        assert sec in card, f"Bug Card missing section: {sec}"

    # Critical Safety Gate Validation
    assert defect["requires_user_approval"] is True
    assert "Kya is bug ko Jira mein 'Testing Bug' create karke" in defect["approval_prompt"]
    assert "Approve / Reject" in defect["approval_prompt"]
