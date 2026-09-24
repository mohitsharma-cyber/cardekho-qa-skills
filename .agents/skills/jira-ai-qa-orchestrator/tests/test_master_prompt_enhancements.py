"""
Unit tests for AI Jira Android QA Orchestrator Master Prompt Enhancements.
"""

import os
import sys
import pytest

base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if base_dir not in sys.path:
    sys.path.insert(0, base_dir)

from modules.jira.jira_client import JiraClient
from modules.ai.context_analyzer import RequirementAnalyzer
from modules.planning.test_planner import TestPlanner
from modules.deployment.jenkins_deployer import JenkinsDeployer
from modules.reporting.qa_reporter import QAReporter
from modules.execution.chat_orchestrator import ChatQAOrchestrator
from modules.execution.orchestrator import ExecutionStateMachine
from database.db_manager import DatabaseManager


def test_jira_queue_numbered_selection():
    chat = ChatQAOrchestrator(mock_mode=True)
    # 1. List queue
    queue_text = chat.handle_command("Start QA")
    assert "YOUR QA QUEUE" in queue_text
    assert "1. CD-123" in queue_text

    # 2. Select by number
    res_text = chat.handle_command("1")
    assert "Selected Jira" in res_text
    assert "CD-123" in res_text

    # 3. Refresh queue
    ref_text = chat.handle_command("Refresh Jira")
    assert "Jira queue refreshed" in ref_text


def test_brand_identification_and_testing_mode():
    analyzer = RequirementAnalyzer()

    # BikeDekho ticket
    bd_ticket = {"key": "MB2C-1974", "summary": "[BD APP] Service ordinal fix", "description": "Bike details", "labels": ["bike"]}
    brand, certain = analyzer.identify_brand(bd_ticket)
    assert brand == "BIKEDEKHO"
    assert certain is True

    # CarDekho ticket
    cd_ticket = {"key": "CD-145", "summary": "Car overview price", "description": "Car model", "labels": []}
    brand, certain = analyzer.identify_brand(cd_ticket)
    assert brand == "CARDEKHO"
    assert certain is True

    # Mode classification
    assert analyzer.classify_jira_type({"summary": "Prod bug in price", "issue_type": "Bug"}) == "PROD BUG"
    assert analyzer.classify_jira_type({"summary": "Testing bug in search", "issue_type": "Testing Bug"}) == "TESTING BUG"
    assert analyzer.classify_jira_type({"summary": "New feature for booking", "issue_type": "Feature"}) == "FEATURE"
    assert analyzer.classify_jira_type({"summary": "General task", "issue_type": "Task"}) == "TASK"


def test_deployment_server_selection_and_banner():
    banner = JenkinsDeployer.format_deployment_verified_banner(
        ticket_key="MB2C-1974",
        branch="feature/service-ordinal-fix",
        commit="c4f7a12",
        build_num=142,
        server="testingapi2"
    )
    assert "DEPLOYMENT SUCCESSFUL & VERIFIED" in banner
    assert "MB2C-1974" in banner
    assert "testingapi2" in banner
    assert "VERIFIED" in banner


def test_mode_b_ai_strategy_and_scenarios():
    planner = TestPlanner()
    analyzer = RequirementAnalyzer()

    task_ticket = {
        "key": "MB2C-2012",
        "summary": "New Service Flow Calculator Integration",
        "description": "Implement new service flow for bike servicing with live estimation calculation.",
        "acceptance_criteria": "Calculator must compute total price, display breakdown, and handle error responses.",
        "issue_type": "Task"
    }

    mode = planner.detect_testing_mode(task_ticket)
    assert mode == "MODE_B"

    analysis = analyzer.analyze(task_ticket)
    plan = planner.generate_plan(task_ticket, analysis)

    assert plan["mode"] == "MODE_B"
    assert "strategy" in plan
    strat = plan["strategy"]
    assert "requirement_understanding" in strat
    assert "impact_analysis" in strat
    assert "risk_analysis" in strat
    assert strat["priority_breakdown"]["P0"] >= 1
    assert strat["priority_breakdown"]["P1"] >= 1
    assert strat["priority_breakdown"]["P2"] >= 1
    assert strat["priority_breakdown"]["P3"] >= 1


def test_master_report_and_signoff_formats():
    report_data = {
        "ticket_key": "MB2C-1974",
        "brand": "BikeDekho",
        "jira_type": "Testing Bug",
        "testing_mode": "Jira Steps",
        "environment": "TESTING",
        "overall_status": "PASSED",
        "metrics": {"generated": 4, "passed": 4, "failed": 0, "blocked": 0, "skipped": 0},
        "deployment": {"branch": "fix/ordinal", "build_number": 142, "target_env": "testingapi2", "status": "VERIFIED"}
    }

    report_str = QAReporter.format_master_qa_report(report_data)
    assert "QA EXECUTION REPORT" in report_str
    assert "MB2C-1974" in report_str
    assert "BikeDekho" in report_str
    assert "PASSED" in report_str

    signoff_str = QAReporter.format_master_signoff(report_data)
    assert "QA SIGN-OFF" in signoff_str
    assert "[POST QA SIGN-OFF TO JIRA]" in signoff_str


def test_master_bug_draft_format():
    bug_data = {
        "summary": "[BikeDekho App] Testing Bug: Service sequence incorrect",
        "description": "Observed ordinal sequence mismatch",
        "environment": "TESTING",
        "expected_result": "1st, 2nd, 3rd, 4th Service",
        "actual_result": "1st, 3st, 4st",
        "priority": "P1",
        "parent_ticket": "MB2C-1974"
    }

    draft_str = QAReporter.format_master_bug_draft(bug_data)
    assert "TESTING BUG DRAFT READY" in draft_str
    assert "MB2C-1974" in draft_str
    assert "[APPROVE & CREATE BUG]" in draft_str
