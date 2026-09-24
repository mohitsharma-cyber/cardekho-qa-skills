import os
import sys
import xml.etree.ElementTree as ET
import pytest

base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if base_dir not in sys.path:
    sys.path.insert(0, base_dir)

from modules.android.device_resilience import DeviceResilienceHelper
from modules.android.android_runner import AndroidRunner


def test_device_resilience_mock_mode():
    """Verify DeviceResilienceHelper behaves properly in mock mode."""
    helper = DeviceResilienceHelper(mock_mode=True)

    # 1. Sweep overlays
    sweep = helper.sweep_overlays("mock_serial")
    assert sweep["status"] == "CLEAN"
    assert sweep["focus_restored"] is True

    # 2. Keyboard dismissal
    assert helper.is_keyboard_shown("mock_serial") is False
    assert helper.dismiss_keyboard_if_shown("mock_serial") is True

    # 3. Dynamic Element Resolver
    center = helper.resolve_element_center("mock_serial", text="CHANGE URL")
    assert center == (200, 230)  # bounds [100,200][300,260] -> cx=200, cy=230

    # 4. Fallback coords when not found
    fallback = helper.resolve_element_center("mock_serial", text="DOES_NOT_EXIST", fallback_coords=(540, 1200))
    assert fallback == (540, 1200)

    # 5. Shimmer / Content Poller
    ok, msg = helper.wait_for_content_or_shimmer("mock_serial")
    assert ok is True
    assert "Mock Mode" in msg

    # 6. Logcat Sniffer
    errors = helper.capture_logcat_fatal_errors("mock_serial", "com.girnarsoft.cardekho")
    assert errors == []


def test_android_runner_resilience_delegation():
    """Verify AndroidRunner exposes and delegates to DeviceResilienceHelper cleanly."""
    runner = AndroidRunner(mock_mode=True)
    assert hasattr(runner, "resilience")

    # Delegation checks
    sweep = runner.sweep_overlays("mock_serial")
    assert sweep["status"] == "CLEAN"

    assert runner.dismiss_keyboard_if_shown("mock_serial") is True

    center = runner.resolve_element_center("mock_serial", text="CHANGE URL")
    assert center == (200, 230)

    fallback = runner.resolve_element_center("mock_serial", text="MISSING", fallback_coords=(300, 400))
    assert fallback == (300, 400)

    crashes = runner.capture_logcat_fatal_errors("mock_serial", "com.girnarsoft.cardekho")
    assert crashes == []


def test_dynamic_element_bounds_calculation():
    """Verify element bounding box and center coordinate resolution with various bounds formats."""
    helper = DeviceResilienceHelper(mock_mode=False)

    # Mock dump_ui_xml to return a custom tree
    custom_root = ET.Element("hierarchy")
    ET.SubElement(custom_root, "node", {
        "text": "Submit Review",
        "resource-id": "com.girnarsoft.cardekho:id/btn_submit",
        "bounds": "[150,800][450,900]"
    })
    ET.SubElement(custom_root, "node", {
        "text": "",
        "content-desc": "Hamburger menu",
        "resource-id": "com.girnarsoft.cardekho:id/iv_menu",
        "bounds": "[20,40][120,140]"
    })

    helper.dump_ui_xml = lambda serial: custom_root

    # Search by text
    center_text = helper.resolve_element_center("serial", text="Submit Review")
    assert center_text == (300, 850)  # (150+450)//2 = 300, (800+900)//2 = 850

    # Search by resource_id
    center_id = helper.resolve_element_center("serial", resource_id="btn_submit")
    assert center_id == (300, 850)

    # Search by content_desc
    center_desc = helper.resolve_element_center("serial", content_desc="Hamburger menu")
    assert center_desc == (70, 90)  # (20+120)//2 = 70, (40+140)//2 = 90
