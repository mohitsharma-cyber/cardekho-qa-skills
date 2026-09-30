"""
Tests for Coverage Engine (Phase 1).
Validates separate tracking of Requirement, Execution, and Regression coverage,
statuses (PASS, FAIL, BLOCKED, NOT_TESTED, NOT_APPLICABLE),
and enforces the Golden Honesty Rule: Never claim 100% coverage falsely.
"""

import pytest
import os
import sys

skill_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if skill_root not in sys.path:
    sys.path.insert(0, skill_root)

from modules.coverage.coverage_engine import CoverageEngine, TestStatus


@pytest.fixture
def coverage_engine():
    cov = CoverageEngine()
    # Add 3 distinct requirements
    cov.add_requirement("REQ-01", "Verify On-Road Price breakdown calculates RTO accurately")
    cov.add_requirement("REQ-02", "Verify sticky CTA opens lead bottom sheet")
    cov.add_requirement("REQ-03", "Verify EMI calculator updates on slider change")
    return cov


def test_independent_coverage_tracking(coverage_engine):
    """Verifies that Requirement, Execution, and Regression are tracked independently."""
    # Register test cases
    coverage_engine.register_test_case("TC-01", "Test RTO row", mapped_req_ids=["REQ-01"])
    coverage_engine.register_test_case("TC-02", "Test CTA click", mapped_req_ids=["REQ-02"])
    coverage_engine.register_test_case("TC-03", "Test EMI slider", mapped_req_ids=["REQ-03"])

    # Register targeted regression
    coverage_engine.register_regression_scenario("REG-01", "variant_details", "Specs matrix regression")

    # Initial state
    req_cov = coverage_engine.get_requirement_coverage()
    exec_cov = coverage_engine.get_execution_coverage()
    reg_cov = coverage_engine.get_regression_coverage()

    assert req_cov["total"] == 3
    assert req_cov["verified"] == 0
    assert exec_cov["total_planned"] == 3
    assert exec_cov["executed"] == 0
    assert reg_cov["total_planned"] == 1
    assert reg_cov["executed"] == 0


def test_honest_coverage_rejection_when_untested(coverage_engine):
    """Never claim 100% coverage when requirements or test cases remain untested."""
    coverage_engine.register_test_case("TC-01", "Test RTO row", mapped_req_ids=["REQ-01"])
    coverage_engine.register_test_case("TC-02", "Test CTA click", mapped_req_ids=["REQ-02"])

    # Pass TC-01 and TC-02
    coverage_engine.record_test_result("TC-01", TestStatus.PASS)
    coverage_engine.record_test_result("TC-02", TestStatus.PASS)

    # Even though 100% of executed passed, REQ-03 is untested!
    signoff = coverage_engine.evaluate_signoff_claim()
    assert signoff["is_full_coverage"] is False
    assert signoff["final_verdict"] == "PARTIAL"
    assert "REQ-03" in signoff["untested_requirements"]


def test_honest_coverage_rejection_when_blocked(coverage_engine):
    """Never convert BLOCKED tests into PASS or claim full coverage."""
    coverage_engine.register_test_case("TC-01", "Test RTO row", mapped_req_ids=["REQ-01"])
    coverage_engine.register_test_case("TC-02", "Test CTA click", mapped_req_ids=["REQ-02"])
    coverage_engine.register_test_case("TC-03", "Test EMI slider", mapped_req_ids=["REQ-03"])

    coverage_engine.record_test_result("TC-01", TestStatus.PASS)
    coverage_engine.record_test_result("TC-02", TestStatus.PASS)
    coverage_engine.record_test_result("TC-03", TestStatus.BLOCKED, error="Device screen blocked by overlay")

    signoff = coverage_engine.evaluate_signoff_claim()
    assert signoff["is_full_coverage"] is False
    assert signoff["final_verdict"] == "BLOCKED"
    assert "TC-03" in signoff["blocked_scenarios"]


def test_full_coverage_claim_valid_only_when_all_pass(coverage_engine):
    """Claiming 100% coverage is valid ONLY when all requirements and executions pass."""
    coverage_engine.register_test_case("TC-01", "Test RTO row", mapped_req_ids=["REQ-01"])
    coverage_engine.register_test_case("TC-02", "Test CTA click", mapped_req_ids=["REQ-02"])
    coverage_engine.register_test_case("TC-03", "Test EMI slider", mapped_req_ids=["REQ-03"])

    coverage_engine.record_test_result("TC-01", TestStatus.PASS)
    coverage_engine.record_test_result("TC-02", TestStatus.PASS)
    coverage_engine.record_test_result("TC-03", TestStatus.PASS)

    signoff = coverage_engine.evaluate_signoff_claim()
    assert signoff["is_full_coverage"] is True
    assert signoff["final_verdict"] == "PASS"
    assert signoff["requirement_coverage"]["percentage"] == 100.0
    assert signoff["execution_coverage"]["percentage"] == 100.0


def test_failure_propagates_to_requirement(coverage_engine):
    """Failure in any mapped test case marks the requirement as FAILED."""
    coverage_engine.register_test_case("TC-01A", "Test RTO API", mapped_req_ids=["REQ-01"])
    coverage_engine.register_test_case("TC-01B", "Test RTO UI", mapped_req_ids=["REQ-01"])

    coverage_engine.record_test_result("TC-01A", TestStatus.PASS)
    coverage_engine.record_test_result("TC-01B", TestStatus.FAIL, error="Text mismatch: expected 85000 got 92000")

    req_cov = coverage_engine.get_requirement_coverage()
    assert req_cov["failed"] == 1
    assert coverage_engine.requirements["REQ-01"]["status"] == TestStatus.FAIL
