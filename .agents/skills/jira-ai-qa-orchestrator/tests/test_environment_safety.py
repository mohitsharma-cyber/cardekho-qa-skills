import pytest
import os
import sys

base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if base_dir not in sys.path:
    sys.path.insert(0, base_dir)

from modules.environment.env_manager import EnvironmentManager, EnvironmentSafetyError


def test_testing_profile():
    mgr = EnvironmentManager()
    profile = mgr.get_profile("TESTING")
    assert profile["base_url"] == "https://testingpwa2.cardekho.com"
    assert profile["base_api_url"] == "https://testingpwa2.cardekho.com/api"


def test_staging_profile():
    mgr = EnvironmentManager()
    profile = mgr.get_profile("STAGING")
    assert profile["base_url"] == "https://staging.cardekho.com"


def test_production_url_is_strictly_blocked():
    mgr = EnvironmentManager()
    with pytest.raises(EnvironmentSafetyError) as exc_info:
        mgr.validate_environment_safety("https://www.cardekho.com/new-cars")
    assert "STRICTLY BLOCKED by Rule 6" in str(exc_info.value)


def test_mock_app_configuration():
    mgr = EnvironmentManager()
    ok, msg = mgr.configure_android_app_environment("TESTING", mock_mode=True)
    assert ok is True
    assert "TESTING" in msg


def test_bikedekho_testing_profile_urls():
    mgr = EnvironmentManager()
    profile = mgr.get_profile("TESTING", deployment_target="testingapi2", is_bikedekho=True)
    assert profile["base_url"] == "https://testing2.bikedekho.com"
    assert profile["base_api_url"] == "https://testingapi2.bikedekho.com"
    assert profile["my_account_url"] == "https://qa-apis.bikedekho.com/f8"


def test_bikedekho_staging_profile_urls():
    mgr = EnvironmentManager()
    profile = mgr.get_profile("STAGING", is_bikedekho=True)
    assert profile["base_url"] == "https://alpha.bikedekho.com"
    assert profile["base_api_url"] == "https://alphaapi.bikedekho.com"
    assert profile["my_account_url"] == "https://uat-apis.bikedekho.com/f8"

