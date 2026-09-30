"""
Tests for Evidence Manager (Phase 4).
Validates 9 metadata fields across all 4 evidence types:
screenshot, logcat, api_response, and execution_log.
Validates mandatory capture triggers and fast-mode screenshot suppression.
"""

import pytest
import os
import sys

skill_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if skill_root not in sys.path:
    sys.path.insert(0, skill_root)

from modules.evidence.evidence_manager import EvidenceManager

REQUIRED_METADATA_FIELDS = [
    "ticket",
    "test_case",
    "step",
    "timestamp",
    "device",
    "android_version",
    "build",
    "environment",
    "result"
]

@pytest.fixture
def evidence_mgr(tmp_path):
    return EvidenceManager(evidence_dir=str(tmp_path))


def test_screenshot_maintains_all_9_metadata_fields(evidence_mgr):
    """Screenshot records contain all 9 required metadata fields."""
    rec = evidence_mgr.record_screenshot(
        ticket="MB2C-1001",
        test_case="TC-01",
        step="Verify Home Screen Search Bar",
        device="OnePlus 12R (CPH2585)",
        android_version="Android 14",
        build="#142",
        environment="TESTING",
        result="PASS",
        is_fast_mode=False
    )

    assert rec is not None
    assert rec["evidence_type"] == "screenshot"
    for field in REQUIRED_METADATA_FIELDS:
        assert field in rec, f"Missing required metadata field: {field}"
        assert rec[field] is not None


def test_logcat_maintains_all_9_metadata_fields(evidence_mgr):
    """Logcat records contain all 9 required metadata fields and sanitized snippets."""
    rec = evidence_mgr.record_logcat(
        ticket="MB2C-1001",
        test_case="TC-02",
        step="Click Service Cost Details",
        device="OnePlus 12R (CPH2585)",
        android_version="Android 14",
        build="#142",
        environment="TESTING",
        result="FAIL"
    )

    assert rec["evidence_type"] == "logcat"
    for field in REQUIRED_METADATA_FIELDS:
        assert field in rec, f"Missing required metadata field: {field}"
    assert rec["is_sanitized"] is True


def test_api_response_maintains_all_9_metadata_fields(evidence_mgr):
    """API response records contain all 9 metadata fields and sanitized payload."""
    rec = evidence_mgr.record_api_response(
        ticket="MB2C-1001",
        test_case="TC-03",
        step="Query On-Road Price API",
        device="OnePlus 12R (CPH2585)",
        android_version="Android 14",
        build="#142",
        environment="TESTING",
        result="PASS",
        endpoint="https://testingpwa1.cardekho.com/api/v1/price",
        status_code=200,
        response_time_ms=185.0,
        response_payload={"model": "Creta", "token": "SecretSessionToken999"}
    )

    assert rec["evidence_type"] == "api_response"
    for field in REQUIRED_METADATA_FIELDS:
        assert field in rec, f"Missing required metadata field: {field}"
    assert rec["sanitized_response"]["token"] == "[REDACTED_SECRET]"


def test_execution_log_maintains_all_9_metadata_fields(evidence_mgr):
    """Execution log records contain all 9 metadata fields."""
    rec = evidence_mgr.record_execution_log(
        ticket="MB2C-1001",
        test_case="TC-04",
        step="Tap Update Environment Button",
        device="OnePlus 12R (CPH2585)",
        android_version="Android 14",
        build="#142",
        environment="TESTING",
        result="PASS",
        message="Successfully updated BASE URL to testingpwa1"
    )

    assert rec["evidence_type"] == "execution_log"
    for field in REQUIRED_METADATA_FIELDS:
        assert field in rec, f"Missing required metadata field: {field}"


def test_fast_mode_screenshot_suppression_and_mandatory_failure_trigger(evidence_mgr):
    """Fast mode suppresses routine screenshots but captures mandatory failure evidence."""
    # Routine gesture in fast mode: suppressed (returns None)
    routine_item = evidence_mgr.record_screenshot(
        ticket="MB2C-1001",
        test_case="TC-05",
        step="Scroll to overview specs",
        device="OnePlus 12R",
        android_version="Android 14",
        build="#142",
        environment="TESTING",
        result="PASS",
        is_fast_mode=True,
        is_mandatory=False
    )
    assert routine_item is None

    # Failure in fast mode: mandatory capture executes
    failure_bundle = evidence_mgr.capture_mandatory_failure_evidence(
        ticket="MB2C-1001",
        test_case="TC-06",
        step="Assert RTO price breakdown",
        device="OnePlus 12R",
        android_version="Android 14",
        build="#142",
        environment="TESTING",
        error_message="Assertion failed: RTO row missing"
    )
    assert failure_bundle["screenshot"] is not None
    assert failure_bundle["logcat"] is not None
    assert failure_bundle["execution_log"] is not None
    assert failure_bundle["screenshot"]["result"] == "FAIL"
