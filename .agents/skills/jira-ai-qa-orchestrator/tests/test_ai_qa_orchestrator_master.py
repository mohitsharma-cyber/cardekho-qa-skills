import pytest
import os
import sys

# Ensure base dir on path
base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if base_dir not in sys.path:
    sys.path.insert(0, base_dir)

from database.db_manager import DatabaseManager
from modules.planning.test_planner import TestPlanner
from modules.execution.orchestrator import ExecutionStateMachine
from modules.execution.chat_orchestrator import ChatQAOrchestrator


def test_mode_a_detection_and_jira_steps_preservation():
    planner = TestPlanner()
    ticket_with_steps = {
        "key": "MB2C-1001",
        "summary": "Verify Service Cost Ordinal Numbers",
        "description": (
            "Steps to Reproduce:\n"
            "1. Launch the BikeDekho app\n"
            "2. Search for Hero Splendor Plus\n"
            "3. Navigate to Service Cost section\n"
            "4. Observe service sequence\n"
            "Expected Result:\n"
            "Service sequence must display 1st, 2nd, 3rd, 4th service."
        )
    }
    mode = planner.detect_testing_mode(ticket_with_steps)
    assert mode == "MODE_A"

    plan = planner.generate_plan(ticket_with_steps, {"device_requirement": {"device_required": True}}, environment="TESTING")
    assert plan["mode"] == "MODE_A"
    assert "JIRA STEPS" in plan["mode_label"]
    tc01 = plan["test_cases"][0]
    assert tc01["source"] == "JIRA_PROVIDED_STEP"
    assert len(tc01["steps"]) >= 4
    assert tc01["priority"] == "P0"


def test_mode_b_detection_and_ai_generation():
    planner = TestPlanner()
    ticket_without_steps = {
        "key": "MB2C-1002",
        "summary": "Implement Instant Loan Approval Banner",
        "description": "As a user looking for financing, I should see an Instant Loan Approval banner on the model page.",
        "acceptance_criteria": "Banner must be visible and tapping it must navigate to financing form."
    }
    mode = planner.detect_testing_mode(ticket_without_steps)
    assert mode == "MODE_B"

    plan = planner.generate_plan(ticket_without_steps, {"device_requirement": {"device_required": True}}, environment="TESTING")
    assert plan["mode"] == "MODE_B"
    assert "AI TEST GENERATION" in plan["mode_label"]
    tc01 = plan["test_cases"][0]
    assert tc01["source"] == "AI_DERIVED_TEST"
    assert tc01["priority"] == "P0"
    assert any(tc["priority"] == "P1" for tc in plan["test_cases"])
    assert any(tc["priority"] == "P2" for tc in plan["test_cases"])


def test_jira_step_validation_gate_fail_fast_on_ambiguity():
    planner = TestPlanner()
    ticket_ambiguous = {
        "key": "MB2C-1003",
        "summary": "Check general flow",
        "description": (
            "Steps to Reproduce:\n"
            "1. Open the app\n"
            "2. Check everything and ensure it should work fine"
        )
    }
    plan = planner.generate_plan(ticket_ambiguous, {}, environment="TESTING")
    val = plan["step_validation"]
    assert val["is_valid"] is False
    assert val["status"] == "CLARIFICATION_REQUIRED"
    assert len(val["issues"]) > 0
    assert "ambiguous" in val["issues"][0].lower()


def test_jira_step_validation_gate_destructive_requirement_error():
    planner = TestPlanner()
    ticket_destructive = {
        "key": "MB2C-1004",
        "summary": "Delete old data",
        "description": (
            "Steps to Reproduce:\n"
            "1. Open the app\n"
            "2. Delete production customer records"
        )
    }
    plan = planner.generate_plan(ticket_destructive, {}, environment="TESTING")
    val = plan["step_validation"]
    assert val["is_valid"] is False
    assert val["status"] == "REQUIREMENT_ERROR"


def test_dependency_aware_fail_fast_execution():
    db = DatabaseManager()
    sm = ExecutionStateMachine(db=db, mock_mode=True)

    # 1. Run CD-145 and verify dependency links are established
    res = sm.run_full_orchestration(
        ticket_key="CD-145",
        environment="TESTING"
    )
    assert res["overall_status"] in ["PASSED", "FAILED", "AWAITING_BUG_APPROVAL", "COMPLETED"]
    executed = res["report"]["test_cases"]
    tc01 = next(t for t in executed if "TC-01" in t["test_case_id"])
    tc02 = next(t for t in executed if "TC-02" in t["test_case_id"])
    assert tc01["test_case_id"] in tc02["dependencies"]

    # 2. Directly verify fail-fast halting when prerequisite fails
    planner = TestPlanner()
    plan = planner.generate_plan(
        {"key": "TEST-101", "summary": "Dependency Test", "description": "Story without steps", "acceptance_criteria": "AC verified"},
        {"device_requirement": {"device_required": False}}
    )
    tcs = plan["test_cases"]
    assert len(tcs) >= 3
    # Prerequisite is TC-01
    assert tcs[0]["dependencies"] == []
    assert tcs[0]["test_case_id"] in tcs[1]["dependencies"]
    assert tcs[0]["test_case_id"] in tcs[2]["dependencies"]


def test_one_qa_session_authorization_gate():
    db = DatabaseManager()
    sm = ExecutionStateMachine(db=db, mock_mode=True)

    # If qa_session_authorized is False, execution halts before executing device actions
    res = sm.run_full_orchestration(
        ticket_key="MB2C-1974",
        environment="TESTING",
        qa_session_authorized=False
    )
    assert res["status"] == "WAITING_FOR_SESSION_AUTHORIZATION"
    assert sm.current_state == "WAITING_FOR_SESSION_AUTHORIZATION"

    # Authorize session
    auth_res = sm.authorize_qa_session(res["execution_id"])
    assert auth_res["status"] == "SUCCESS"
    assert sm.current_state == "EXECUTING"


def test_chat_orchestrator_commands():
    chat = ChatQAOrchestrator(mock_mode=True)

    # 1. Stop command
    stop_msg = chat.handle_command("Stop testing")
    assert "safely halted" in stop_msg

    # 2. Resume command
    res_msg = chat.handle_command("Resume testing")
    assert "Resuming testing" in res_msg

    # 3. Session authorization command
    chat.current_execution_id = "EXEC-MOCK-123"
    auth_msg = chat.handle_command("Allow QA session")
    assert "QA Session authorized" in auth_msg
