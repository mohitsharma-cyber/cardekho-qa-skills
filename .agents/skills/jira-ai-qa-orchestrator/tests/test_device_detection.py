import pytest
import os
import sys

base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if base_dir not in sys.path:
    sys.path.insert(0, base_dir)

from modules.android.android_runner import AndroidRunner
from modules.ai.context_analyzer import RequirementAnalyzer


def test_mock_device_detection():
    runner = AndroidRunner(mock_mode=True)
    device = runner.detect_device()
    assert device is not None
    assert "serial" in device
    assert device["connection_status"] == "Connected"


def test_device_requirement_heuristic():
    analyzer = RequirementAnalyzer()

    # Case 1: Standard web filter issue -> Device NOT required
    ticket_web = {
        "key": "CD-145",
        "summary": "Search filter price range slider reset issue",
        "description": "Resetting price range retains chips",
        "acceptance_criteria": "Filter chips reset properly"
    }
    analysis_web = analyzer.analyze(ticket_web)
    assert analysis_web["device_requirement"]["device_required"] is False

    # Case 2: Hardware dual camera crash -> Device IS required
    ticket_hw = {
        "key": "CD-167",
        "summary": "Compare details crash on dual camera hardware",
        "description": "Opening camera view crashes app without permission",
        "acceptance_criteria": "Prompt permission safely"
    }
    analysis_hw = analyzer.analyze(ticket_hw)
    assert analysis_hw["device_requirement"]["device_required"] is True
