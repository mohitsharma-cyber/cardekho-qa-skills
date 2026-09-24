import pytest
import os
import sys

base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if base_dir not in sys.path:
    sys.path.insert(0, base_dir)

from modules.deployment.jenkins_deployer import JenkinsDeployer


def test_api_branch_detection():
    deployer = JenkinsDeployer()
    ticket = {
        "key": "DB2C-9133",
        "description": "App team requires an API to enable the feature 'Report incorrect Price' in APP.\nCD API Branch Name = DB2C-ReportIncorrect_App_pageType",
        "comments": []
    }
    info = deployer.extract_branch_info(ticket)
    assert info["has_branch"] is True
    assert info["branch_type"] == "API"
    assert info["primary_branch"] == "DB2C-ReportIncorrect_App_pageType"
    assert "testingpwa2" in info["target_server"]


def test_pwa_branch_detection():
    deployer = JenkinsDeployer()
    ticket = {
        "key": "MB2C-1971",
        "description": "Empty state review bug\nApp branch: MB2C-1971_reviewsTabBlankState",
        "comments": []
    }
    info = deployer.extract_branch_info(ticket)
    assert info["has_branch"] is True
    assert info["primary_branch"] == "MB2C-1971_reviewsTabBlankState"


def test_mock_jenkins_deployment():
    deployer = JenkinsDeployer()
    res = deployer.trigger_deployment(
        branch_name="DB2C-ReportIncorrect_App_pageType",
        branch_type="API",
        target_env="testingpwa2",
        mock_mode=True
    )
    assert res["status"] == "SUCCESS"
    assert res["branch"] == "DB2C-ReportIncorrect_App_pageType"
    assert res["target_env"] == "testingpwa2"
    assert "142" in res["build_url"]


def test_bikedekho_branch_detection():
    deployer = JenkinsDeployer()
    ticket = {
        "key": "BDCV-5902",
        "summary": "BikeDekho new model price card revision",
        "description": "Please verify on testing server.\nAPI branch: BDCV-5902_price_card_revamp",
        "comments": []
    }
    info = deployer.extract_branch_info(ticket)
    assert info["has_branch"] is True
    assert info["is_bikedekho"] is True
    assert info["brand"] == "BikeDekho"
    assert info["requires_server_choice"] is True
    assert "testingapi5" in info["suggested_servers"]
    assert "bikedekho.com" in info["target_url"]


def test_bikedekho_custom_server_deployment():
    deployer = JenkinsDeployer()
    res = deployer.trigger_deployment(
        branch_name="BDCV-5902_price_card_revamp",
        branch_type="API",
        target_env="testingpwa1",
        is_bikedekho=True,
        mock_mode=True
    )
    assert res["status"] == "SUCCESS"
    assert res["target_env"] == "testingpwa1"
    assert "testingpwa1.bikedekho.com" in res["target_url"]

