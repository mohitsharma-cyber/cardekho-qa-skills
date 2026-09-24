import pytest
import os
import sys

base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if base_dir not in sys.path:
    sys.path.insert(0, base_dir)

from modules.android.build_installer import BuildInstaller


def test_build_detection_in_description():
    installer = BuildInstaller()
    ticket = {
        "key": "MB2C-2001",
        "description": "Please verify fix on build: https://artifacts.girnarsoft.com/android/builds/app-debug-v2.1.apk",
        "comments": [],
        "attachments": []
    }
    info = installer.extract_build_info(ticket)
    assert info["has_build"] is True
    assert info["source_type"] == "DIRECT_APK"
    assert "app-debug-v2.1.apk" in info["filename"]


def test_build_detection_in_comments():
    installer = BuildInstaller()
    ticket = {
        "key": "MB2C-2002",
        "description": "App crash on login",
        "comments": [
            {"author": "dev", "body": "Fixed in build: https://install.appcenter.ms/orgs/cardekho/apps/android"},
            {"author": "qa", "body": "Checking now"}
        ],
        "attachments": []
    }
    info = installer.extract_build_info(ticket)
    assert info["has_build"] is True
    assert info["source_type"] == "CI_DISTRIBUTION"


def test_mock_build_installation():
    installer = BuildInstaller()
    ok, msg = installer.install_build_on_device("mock_app.apk", "MOCK_DEVICE_101", mock_mode=True)
    assert ok is True
    assert "MOCK_DEVICE_101" in msg
