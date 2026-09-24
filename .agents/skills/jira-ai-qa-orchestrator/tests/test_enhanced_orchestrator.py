"""
Comprehensive test suite for Enhanced Jira AI QA Orchestrator:
- Jenkins build completion polling & independent deployment verification
- Environment vs Deployment Target separation
- Android device listing & permission pre-granting
- Deterministic shimmer handling & timeout classification
- Duplicate bug protection in JiraClient
- Chat-native QA command dispatcher
"""

import pytest
import os
import sys

# Ensure module path
current_dir = os.path.dirname(os.path.abspath(__file__))
skill_root = os.path.dirname(current_dir)
if skill_root not in sys.path:
    sys.path.insert(0, skill_root)

from modules.deployment.jenkins_deployer import JenkinsDeployer
from modules.environment.env_manager import EnvironmentManager, EnvironmentSafetyError
from modules.android.android_runner import AndroidRunner
from modules.jira.jira_client import JiraClient
from modules.execution.chat_orchestrator import ChatQAOrchestrator


def test_jenkins_build_completion_mock():
    """Verify JenkinsDeployer polls build completion and returns SUCCESS."""
    deployer = JenkinsDeployer()
    res = deployer.wait_for_build_completion(
        queue_url="http://mock/queue/123",
        job_name="Bikedekho-Build-Deploy-Desktop-Testing-API-Latest",
        mock_mode=True
    )
    assert res["status"] == "SUCCESS"
    assert res["build_number"] == 142
    assert res["result"] == "SUCCESS"


def test_jenkins_target_deployment_verification_mock():
    """Verify independent deployment verification on target server."""
    deployer = JenkinsDeployer()
    res = deployer.verify_target_deployment(
        target_server="testingapi2",
        is_bikedekho=True,
        mock_mode=True
    )
    assert res["verified"] is True
    assert "testingapi2.bikedekho.com" in res["target_url"]
    assert res["http_status"] == 200


def test_environment_and_target_separation_bikedekho():
    """Verify Environment (TESTING) vs Deployment Target (testingapi3) separation for BikeDekho."""
    mgr = EnvironmentManager()
    profile = mgr.get_profile("TESTING", deployment_target="testingapi3", is_bikedekho=True)
    assert profile["name"] == "TESTING"
    assert profile["deployment_target"] == "testingapi3"
    assert profile["base_url"] == "https://testing3.bikedekho.com"
    assert profile["base_api_url"] == "https://testingapi3.bikedekho.com"
    assert profile["brand"] == "BikeDekho"


def test_environment_and_target_separation_cardekho():
    """Verify Environment (TESTING) vs Deployment Target (testingpwa2) separation for CarDekho."""
    mgr = EnvironmentManager()
    profile = mgr.get_profile("TESTING", deployment_target="testingpwa2", is_bikedekho=False)
    assert profile["name"] == "TESTING"
    assert profile["deployment_target"] == "testingpwa2"
    assert profile["base_url"] == "https://testingpwa2.cardekho.com"
    assert profile["base_api_url"] == "https://testingpwa2.cardekho.com/api"
    assert profile["brand"] == "CarDekho"


def test_production_safety_blocking_bikedekho():
    """Verify production URL is strictly blocked even for BikeDekho."""
    mgr = EnvironmentManager()
    with pytest.raises(EnvironmentSafetyError) as exc_info:
        mgr.validate_environment_safety("https://api.bikedekho.com")
    assert "CRITICAL VIOLATION" in str(exc_info.value)


def test_android_device_listing_and_permissions_mock():
    """Verify device listing and runtime permission pre-granting."""
    runner = AndroidRunner(mock_mode=True)
    devices = runner.list_connected_devices()
    assert len(devices) > 0
    assert devices[0]["serial"] is not None

    perms = runner.grant_required_permissions("mock_serial", "com.girnarsoft.bikedekho")
    assert perms.get("POST_NOTIFICATIONS") == "Granted"
    assert perms.get("ACCESS_FINE_LOCATION") == "Granted"
    assert perms.get("CAMERA") == "Granted"


def test_shimmer_wait_mock():
    """Verify shimmer wait completes successfully in mock mode."""
    runner = AndroidRunner(mock_mode=True)
    ok, msg = runner.wait_for_shimmer_to_disappear("mock_serial", timeout_secs=5)
    assert ok is True
    assert "Content rendered" in msg


def test_duplicate_bug_detection_mock():
    """Verify duplicate bug detection logic on JiraClient."""
    client = JiraClient(mock_mode=True)
    # Testing with a ticket that has linked issues
    duplicates = client.check_duplicate_bugs(
        summary="Service number sequence ordinal fix",
        parent_ticket_key="MB2C-1974"
    )
    assert isinstance(duplicates, list)


def test_chat_orchestrator_list_assigned_tickets():
    """Verify ChatQAOrchestrator lists assigned tickets properly in chat markdown."""
    chat = ChatQAOrchestrator(mock_mode=True)
    output = chat.list_assigned_tickets()
    assert "My Assigned Jira Tickets" in output
    assert "Which Jira ticket do you want to test?" in output


def test_chat_orchestrator_command_dispatch():
    """Verify natural chat command dispatching."""
    chat = ChatQAOrchestrator(mock_mode=True)
    # 1. List tickets
    res = chat.handle_command("Show my Jira tickets")
    assert "My Assigned Jira Tickets" in res

    # 2. Run ticket testing
    res_ticket = chat.handle_command("Test CD-145")
    assert "QA Execution Report: [CD-145]" in res_ticket
    assert "Execution ID" in res_ticket
