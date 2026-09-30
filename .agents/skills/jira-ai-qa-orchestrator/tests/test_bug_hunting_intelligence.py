"""
Tests for Bug-Hunting Intelligence in Jira AI QA Orchestrator.
Validates:
1. Attack Surface Identification & Vector Prioritization
2. Risk Engine Attack Surface Integration & Mission Motto
3. Test Planner Bug-Hunting Scenario & Vulnerability Hypothesis Derivation
4. Defect Reproducibility Validation & Multi-Stage Classification
5. Coverage Engine Risk & Negative/Boundary Coverage
6. QA Reporter Bug-Hunting Metrics & Defect Reporting
"""

import os
import sys

skill_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if skill_root not in sys.path:
    sys.path.insert(0, skill_root)

import pytest
from modules.risk.impact_analyzer import ImpactAnalyzer, ATTACK_VECTORS
from modules.risk.risk_engine import RiskEngine

from modules.planning.test_planner import TestPlanner
from modules.defects.defect_analyzer import DefectAnalyzer, DefectClassification
from modules.defects.duplicate_detector import DuplicateDetector
from modules.jira.jira_client import JiraClient
from modules.coverage.coverage_engine import CoverageEngine, TestStatus
from modules.reporting.qa_reporter import QAReporter


def get_test_analyzer():
    mock_jira = JiraClient(mock_mode=True)
    dup = DuplicateDetector(jira_client=mock_jira)
    return DefectAnalyzer(duplicate_detector=dup)


def test_identify_attack_surface_derivation():
    analyzer = ImpactAnalyzer()
    
    # Lead / Booking ticket
    lead_impact = {
        "summary": "Implement Instant Booking CTA for Tata Punch",
        "description": "User taps 'Book Now' button and submits phone number for booking.",
        "affected_screens": ["model_details", "lead_form"],
        "affected_modules": ["lead_flow"],
        "api_dependencies": ["/api/v1/lead/submit"],
        "is_crash_fix": False,
        "is_lead_impact": True,
        "is_auth_impact": False,
        "is_ui_only": False,
        "platforms": ["Android App"]
    }
    surface = analyzer.identify_attack_surface(lead_impact)
    
    assert "RAPID_ACTIONS_DEBOUNCE" in surface["identified_vectors"]
    assert "INPUT_BOUNDARIES" in surface["identified_vectors"]
    assert "STATE_LIFECYCLE" in surface["identified_vectors"]
    assert "API_FAILURE_SIMULATION" in surface["identified_vectors"]
    assert "DEVICE_SYSTEM_INTERRUPTS" in surface["identified_vectors"]
    assert surface["primary_threat_vector"] == "RAPID_ACTIONS_DEBOUNCE"
    assert surface["bug_hunting_motto"] == "BREAK THE FEATURE BEFORE THE USER DOES."


def test_risk_engine_exposes_attack_surface_and_motto():
    engine = RiskEngine()
    result = engine.classify_ticket(
        summary="Fix Price Display and Raw HTML Tag Leak on Baleno",
        description="HTML <p> tags appearing in price breakdown and app crashes on null price payload."
    )
    
    assert "attack_surface" in result
    assert "DATA_PAYLOAD_ANOMALIES" in result["prioritized_attack_vectors"]
    assert result["primary_threat_vector"] == "DATA_PAYLOAD_ANOMALIES"
    assert result["bug_hunting_motto"] == "BREAK THE FEATURE BEFORE THE USER DOES."


def test_test_planner_derives_bug_hunting_scenarios():
    planner = TestPlanner()
    ticket = {
        "key": "MB2C-2026",
        "summary": "Redesign Variant Spec Comparison Table",
        "description": "Users can switch variants and view specs side-by-side."
    }
    analysis = {
        "device_requirement": {"device_required": True},
        "dependencies": {"screens": ["variant_details"], "apis": ["/api/v2/variants"]},
        "risks": {"functional_risks": ["Spec mismatch"], "regression_risks": ["Tab lag"]}
    }
    plan = planner.generate_plan(ticket, analysis, deep_bug_hunting=True)
    
    test_cases = plan["test_cases"]
    assert len(test_cases) >= 6
    
    # Check that all test cases have bug hunting fields
    for tc in test_cases:
        assert "attack_surface" in tc
        assert "bug_target" in tc
        assert "vulnerability_hypothesis" in tc
        assert "breaking_action" in tc

    # Verify specific attack surface test cases exist
    surfaces = [tc["attack_surface"] for tc in test_cases]
    assert "DIRECT_ACCEPTANCE" in surfaces
    assert "DATA_PAYLOAD_ANOMALIES" in surfaces
    assert "STATE_LIFECYCLE" in surfaces
    assert "RAPID_ACTIONS_DEBOUNCE" in surfaces
    assert "API_FAILURE_SIMULATION" in surfaces
    assert "DEVICE_SYSTEM_INTERRUPTS" in surfaces

    # Check strategy metadata
    strat = plan["strategy"]
    assert strat["bug_hunting_mission"] == "BREAK THE FEATURE BEFORE THE USER DOES."
    assert "attack_surfaces_covered" in strat


def test_defect_analyzer_reproducibility_and_classification():
    analyzer = get_test_analyzer()

    # 1. Deterministic Real Defect
    res = analyzer.analyze_failure(
        ticket="MB2C-2026",
        test_case_id="MB2C-2026-TC-02",
        summary="Unescaped <p> tags visible in variant description",
        steps=["Open variant page", "Inspect description"],
        expected="Formatted plain text",
        actual="<p>Raw HTML displayed</p>",
        attack_surface="DATA_PAYLOAD_ANOMALIES",
        bug_target="Unescaped HTML tags",
        retry_results=[True, True, True]  # 100% reproducible
    )
    assert res["classification"] == DefectClassification.REAL_DEFECT.value
    assert res["reproducibility"]["is_deterministic"] is True
    assert res["reproducibility"]["reproducibility_rate"] == 100.0
    assert "100% (Deterministic)" in res["bug_card"]
    assert res["requires_user_approval"] is True

    # 2. Intermittent Issue
    res_intermittent = analyzer.analyze_failure(
        ticket="MB2C-2026",
        test_case_id="MB2C-2026-TC-05",
        summary="UI momentary freeze on rapid double tap",
        steps=["Tap CTA twice"],
        expected="Smooth response",
        actual="UI froze briefly",
        retry_results=[True, False, True]  # 2/3 = 66%
    )
    assert res_intermittent["reproducibility"]["is_deterministic"] is False
    assert "66% (Intermittent)" in res_intermittent["bug_card"]

    # 3. Environment Issue
    res_env = analyzer.analyze_failure(
        ticket="MB2C-2026",
        test_case_id="MB2C-2026-TC-06",
        summary="ADB device offline during execution",
        steps=["Send tap event"],
        expected="Tap executed",
        actual="Device offline connection refused",
        error_message="device offline"
    )
    assert res_env["classification"] == DefectClassification.ENVIRONMENT_DATA_ISSUE.value


def test_coverage_engine_risk_and_negative_coverage():
    cov = CoverageEngine()
    cov.add_requirement("REQ-1", "Verify Variant Specs Display")

    # Register happy path
    cov.register_test_case("TC-01", "Acceptance Spec Table", tc_type="functional", mapped_req_ids=["REQ-1"], attack_surface="DIRECT_ACCEPTANCE")
    # Register breaking/negative
    cov.register_test_case("TC-02", "HTML Tag Sanitization", tc_type="boundary", category="data_payload_anomalies", attack_surface="DATA_PAYLOAD_ANOMALIES")
    cov.register_test_case("TC-03", "Rapid Tab Switching Debounce", tc_type="negative", category="rapid_actions_debounce", attack_surface="RAPID_ACTIONS_DEBOUNCE")

    # Initially not tested
    risk_cov = cov.get_risk_coverage()
    assert risk_cov["total"] == 3
    assert risk_cov["verified"] == 0
    assert risk_cov["percentage"] == 0.0

    neg_cov = cov.get_negative_boundary_coverage()
    assert neg_cov["total_planned"] == 3
    assert neg_cov["percentage"] == 0.0

    # Execute TC-01 and TC-02 successfully
    cov.record_test_result("TC-01", TestStatus.PASS)
    cov.record_test_result("TC-02", TestStatus.PASS)

    # TC-03 remains NOT_TESTED -> signoff claim MUST be rejected
    signoff = cov.evaluate_signoff_claim()
    assert signoff["is_full_coverage"] is False
    assert signoff["final_verdict"] == "PARTIAL"

    # Now execute TC-03 as PASS
    cov.record_test_result("TC-03", TestStatus.PASS)
    signoff_complete = cov.evaluate_signoff_claim()
    assert signoff_complete["is_full_coverage"] is True
    assert signoff_complete["final_verdict"] == "PASS"
    assert signoff_complete["risk_coverage"]["percentage"] == 100.0
    assert signoff_complete["negative_boundary_coverage"]["percentage"] == 100.0


def test_qa_reporter_bug_hunting_metrics():
    test_cases = [
        {"test_case_id": "TC-01", "status": "PASSED", "attack_surface": "DIRECT_ACCEPTANCE", "category": "DIRECT"},
        {"test_case_id": "TC-02", "status": "FAILED", "attack_surface": "DATA_PAYLOAD_ANOMALIES", "category": "NEGATIVE_BOUNDARY"},
        {"test_case_id": "TC-03", "status": "PASSED", "attack_surface": "RAPID_ACTIONS_DEBOUNCE", "category": "RAPID_ACTIONS_DEBOUNCE"}
    ]
    failures = [{
        "test_case_id": "TC-02",
        "root_cause_hypothesis": "Unescaped <p> tags rendered in UI",
        "expected": "Plain text",
        "actual": "Raw HTML tags displayed"
    }]
    report = QAReporter.generate_final_report(
        execution={"id": "EXEC-101", "ticket_key": "MB2C-2026", "environment": "TESTING"},
        test_cases=test_cases,
        failures=failures
    )

    assert "bug_hunting" in report
    bh = report["bug_hunting"]
    assert bh["motto"] == "BREAK THE FEATURE BEFORE THE USER DOES."
    assert len(bh["attack_surfaces_tested"]) == 3
    assert bh["negative_and_breaking_tests"]["total"] == 3
    assert bh["defects_discovered_count"] == 1

    jira_comment = QAReporter.format_jira_comment(report)
    assert "BREAK THE FEATURE BEFORE THE USER DOES" in jira_comment
    assert "Attack Surfaces Tested" in jira_comment
    assert "Discovered Defects" in jira_comment
    assert "TC-02" in jira_comment
    assert "Bug Discovery Improvements" in jira_comment
    assert "Scenarios Added" in jira_comment
    assert "Risks Covered" in jira_comment
    assert "Existing Behavior Preserved" in jira_comment


def test_twelve_question_attack_surface_analysis():
    """Validates the 12-question pre-execution bug-hunting risk analysis."""
    analyzer = ImpactAnalyzer()
    ticket_impact = {
        "summary": "Fix On-Road Price Breakdown and Lead CTA for Tata Nexon",
        "description": "User clicks on Price Details, raw <p> tags show in breakdown, and app crashes on null price payload.",
        "affected_screens": ["price_tab", "lead_form"],
        "affected_modules": ["pricing_engine", "lead_flow"],
        "api_dependencies": ["/api/v1/pricing/orp", "/api/v1/lead/submit"],
        "is_crash_fix": True,
        "is_lead_impact": True,
        "is_auth_impact": False,
        "is_ui_only": False,
        "platforms": ["Android App", "WAP"]
    }
    dimensions = analyzer.analyze_attack_dimensions(ticket_impact)

    assert dimensions["total_dimensions_evaluated"] == 12
    assert "what_can_break" in dimensions and len(dimensions["what_can_break"]) > 0
    assert "what_can_crash" in dimensions and any("NullPointer" in c for c in dimensions["what_can_crash"])
    assert "what_can_show_incorrect_data" in dimensions and any("HTML" in d for d in dimensions["what_can_show_incorrect_data"])
    assert "what_happens_with_invalid_missing_null_data" in dimensions
    assert "what_happens_at_boundaries" in dimensions
    assert "what_happens_after_repeated_rapid_actions" in dimensions and any("Rapid double-click" in r for r in dimensions["what_happens_after_repeated_rapid_actions"])
    assert "what_happens_during_loading_empty_error_states" in dimensions and any("10s" in s for s in dimensions["what_happens_during_loading_empty_error_states"])
    assert "what_happens_after_back_refresh_relaunch" in dimensions
    assert "can_ui_and_api_become_inconsistent" in dimensions
    assert "can_app_and_wap_behave_differently" in dimensions and len(dimensions["can_app_and_wap_behave_differently"]) > 0
    assert "what_related_regression_areas_can_be_affected" in dimensions
    assert "are_there_historical_defects_indicating_similar_risks" in dimensions


def test_test_scenario_seven_tuple_contract():
    """Asserts every generated test scenario satisfies the 7-tuple contract:
    Requirement → Risk → Attack Scenario → Bug Discovery Target → Expected → Actual → Evidence
    """
    planner = TestPlanner()
    ticket = {
        "key": "MB2C-3050",
        "summary": "Implement Instant Loan Calculator with Down Payment Slider",
        "description": "Users can drag slider to adjust loan amount and see real-time EMI recalculation.",
        "acceptance_criteria": "Slider moves smoothly, EMI recalculates in real-time, no NaN values."
    }
    analysis = {
        "device_requirement": {"device_required": True},
        "dependencies": {"screens": ["emi_calculator"], "apis": ["/api/v1/emi"]},
        "risks": {"functional_risks": ["Rounding error"], "regression_risks": ["Price tab lag"]}
    }
    plan = planner.generate_plan(ticket, analysis, deep_bug_hunting=True)
    test_cases = plan["test_cases"]

    for tc in test_cases:
        # Mandatory 7-Tuple Internal Contract
        assert "requirement" in tc and len(tc["requirement"]) > 0, f"Missing requirement in {tc['test_case_id']}"
        assert "risk" in tc and len(tc["risk"]) > 0, f"Missing risk in {tc['test_case_id']}"
        assert "attack_scenario" in tc and len(tc["attack_scenario"]) > 0, f"Missing attack_scenario in {tc['test_case_id']}"
        assert "bug_discovery_target" in tc and len(tc["bug_discovery_target"]) > 0, f"Missing bug_discovery_target in {tc['test_case_id']}"
        assert "expected" in tc and len(tc["expected"]) > 0, f"Missing expected in {tc['test_case_id']}"
        assert "actual" in tc, f"Missing actual in {tc['test_case_id']}"
        assert "evidence" in tc and isinstance(tc["evidence"], list), f"Missing evidence in {tc['test_case_id']}"

        # Backwards compatibility check
        assert "expected_result" in tc
        assert "actual_result" in tc
        assert "breaking_action" in tc
        assert "bug_target" in tc


def test_anomaly_lifecycle_pipeline():
    """Validates the complete 7-step anomaly verification pipeline:
    Detect → Reproduce → Investigate → Classify → Duplicate Check → Evidence → Bug Card
    """
    analyzer = get_test_analyzer()
    anomaly_context = {
        "ticket": "MB2C-3050",
        "test_case_id": "TC-02",
        "summary": "Slider displays NaN when dragged to 0 down payment",
        "steps": ["Open Loan Calculator", "Drag slider to extreme left (₹0)"],
        "expected": "EMI calculated with 0 down payment, displaying valid currency value",
        "actual": "EMI card renders 'NaN / month' and NaN in monthly interest",
        "environment": "TESTING",
        "device": "OnePlus 12R",
        "build": "#145",
        "evidence_path": "evidence/EXEC-1/TC-02_nan_slider.png",
        "error_message": "NaN display in TextView",
        "logcat_snippet": "NumberFormatException: For input string 'NaN'",
        "api_status": 200,
        "attack_surface": "INPUT_BOUNDARIES",
        "bug_target": "NaN value calculation at 0 down payment boundary",
        "retry_results": [True, True, True]
    }

    result = analyzer.process_anomaly(anomaly_context)

    # Validate all 7 lifecycle stages exist and are documented
    lifecycle = result["anomaly_lifecycle"]
    assert "stage_1_detect" in lifecycle
    assert "stage_2_reproduce" in lifecycle
    assert "stage_3_investigate" in lifecycle
    assert "stage_4_classify" in lifecycle
    assert "stage_5_duplicate_check" in lifecycle
    assert "stage_6_evidence" in lifecycle
    assert "stage_7_bug_card" in lifecycle
    assert lifecycle["lifecycle_pipeline"] == "Detect → Reproduce → Investigate → Classify → Duplicate Check → Evidence → Bug Card"

    # Stage checks
    assert result["classification"] == DefectClassification.REAL_DEFECT.value
    assert result["is_reportable_defect"] is True
    assert result["requires_user_approval"] is True
    assert "NaN" in result["bug_card"]
    assert result["reproducibility"]["is_deterministic"] is True


def test_filter_unverified_and_expected_behavior():
    """Asserts that expected behavior and 0% reproducible unverified observations are NOT reported as defects."""
    analyzer = get_test_analyzer()

    # Case 1: Expected Behavior (e.g. valid business error or expected redirect)
    res_expected = analyzer.analyze_failure(
        ticket="MB2C-3050",
        test_case_id="TC-03",
        summary="User entering 9-digit phone sees invalid mobile number toast",
        steps=["Enter 9 digits in mobile field", "Tap Proceed"],
        expected="Invalid mobile number toast displayed",
        actual="Invalid mobile number toast displayed (as designed)",
        retry_results=[True, True]
    )
    assert res_expected["classification"] == DefectClassification.EXPECTED_BEHAVIOR.value
    assert res_expected["is_reportable_defect"] is False
    assert res_expected["requires_user_approval"] is False
    assert "No Jira Testing Bug required" in res_expected["approval_prompt"]

    # Case 2: Unverified / Non-reproducible Observation (0% reproduction)
    res_unverified = analyzer.analyze_failure(
        ticket="MB2C-3050",
        test_case_id="TC-04",
        summary="Transient render glitch observed during rapid scroll",
        steps=["Scroll down rapidly"],
        expected="Smooth render",
        actual="Momentary flicker observed once",
        retry_results=[False, False, False]  # 0% reproduced
    )
    assert res_unverified["classification"] == DefectClassification.UNCONFIRMED_ISSUE.value
    assert res_unverified["is_reportable_defect"] is False
    assert res_unverified["requires_user_approval"] is False
    assert "No Jira Testing Bug required" in res_unverified["approval_prompt"]


def test_enhanced_signoff_report_structure():
    """Verifies that the final report and Jira markup contain the 6 mandatory sign-off sections."""
    test_cases = [
        {"test_case_id": "TC-01", "status": "PASSED", "title": "Acceptance Happy Path", "priority": "P0", "attack_surface": "DIRECT_ACCEPTANCE"},
        {"test_case_id": "TC-02", "status": "PASSED", "title": "HTML Tag Sanitization", "priority": "P1", "attack_surface": "DATA_PAYLOAD_ANOMALIES"},
        {"test_case_id": "TC-03", "status": "PASSED", "title": "Rapid Tap Debounce", "priority": "P1", "attack_surface": "RAPID_ACTIONS_DEBOUNCE"}
    ]
    report = QAReporter.generate_final_report(
        execution={"id": "EXEC-202", "ticket_key": "MB2C-3050", "environment": "TESTING"},
        test_cases=test_cases,
        failures=[]
    )

    # Verify structured sections in report dictionary
    assert "signoff_sections" in report
    secs = report["signoff_sections"]
    assert "bug_discovery_improvements" in secs
    assert "scenarios_added" in secs and len(secs["scenarios_added"]) == 3
    assert "risks_covered" in secs
    assert "defects_found" in secs
    assert "untested_blocked_risks" in secs
    assert "existing_behavior_preserved" in secs

    # Verify markdown headers in Jira comment
    comment = QAReporter.format_jira_comment(report)
    assert "🎯 Bug Discovery Improvements" in comment
    assert "🧪 Scenarios Added" in comment
    assert "🛡️ Risks Covered" in comment
    assert "⚠️ Defects Found" in comment
    assert "🚫 Untested/Blocked Risks" in comment
    assert "✅ Existing Behavior Preserved" in comment

