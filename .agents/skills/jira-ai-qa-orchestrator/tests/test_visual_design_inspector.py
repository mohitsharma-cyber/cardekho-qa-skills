"""
Unit and Integration Tests for VisualDesignInspector and Visual Quality Audits.
Validates microcopy leak detection, automotive spelling checks, bounding box overlaps,
text truncation, AssertionEngine integration, and QAReporter formatting.
"""

import pytest
from modules.visual.visual_inspector import (
    VisualDesignInspector,
    VisualDefectType,
    VisualSeverity,
    AUTOMOTIVE_TYPO_MAP
)
from modules.assertions.assertion_engine import AssertionEngine
from modules.reporting.qa_reporter import QAReporter


def test_microcopy_template_leaks_detected():
    inspector = VisualDesignInspector()

    # 1. Format string tokens (%s, %d, {name})
    defects = inspector.check_microcopy_tokens("Starting from %s on-road")
    assert len(defects) >= 1
    assert any(d["type"] == VisualDefectType.TEMPLATE_TOKEN_LEAK.value for d in defects)
    assert any(d["severity"] == VisualSeverity.P1.value for d in defects)

    # 2. Null / undefined / NaN
    defects_null = inspector.check_microcopy_tokens("Model: null")
    assert any("null" in d["description"].lower() for d in defects_null)

    defects_nan = inspector.check_microcopy_tokens("Price: ₹ NaN")
    assert any("nan" in d["description"].lower() for d in defects_nan)

    defects_undef = inspector.check_microcopy_tokens("Variant undefined")
    assert any("undefined" in d["description"].lower() for d in defects_undef)

    # 3. Duplicate currency symbol
    defects_curr = inspector.check_microcopy_tokens("Total: ₹₹12,50,000")
    assert any(d["type"] == VisualDefectType.FORMATTING_ANOMALY.value for d in defects_curr)
    assert any("₹₹" in d["actual_value"] for d in defects_curr)


def test_microcopy_spacing_anomalies_and_unit_whitelisting():
    inspector = VisualDesignInspector()

    # Missing space before currency
    defects_price = inspector.check_microcopy_tokens("Special from₹10,00,000")
    assert any("₹" in d["actual_value"] for d in defects_price)

    # Missing space before word
    defects_word = inspector.check_microcopy_tokens("Save up to 50000on Brezza")
    assert any("50000on" in d["actual_value"] for d in defects_word)

    # Whitelisted automotive units should NOT be flagged as missing space
    for valid_unit in ["1200cc engine", "150bhp power", "18kmpl mileage", "240Nm torque", "1000rpm"]:
        defects = inspector.check_microcopy_tokens(valid_unit)
        spacing_issues = [d for d in defects if d["type"] == VisualDefectType.FORMATTING_ANOMALY.value and "Missing space" in d.get("description", "")]
        assert len(spacing_issues) == 0, f"False positive spacing issue on '{valid_unit}'"


def test_automotive_spelling_typos():
    inspector = VisualDesignInspector()

    # Typical typos
    cases = [
        ("Ex-Showrom Price", "Ex-Showroom"),
        ("Desiel Engine Option", "Diesel"),
        ("Automatic Transmision", "Transmission"),
        ("Certified Milage 20.5", "Mileage"),
        ("Zero Downpayment Scheme", "Down Payment"),
        ("EMI Rs 15,000 Per Mounth", "Per Month"),
    ]

    for text, expected_suggestion in cases:
        defects = inspector.check_automotive_spelling(text)
        assert len(defects) >= 1, f"Expected typo detected in '{text}'"
        assert any(expected_suggestion.lower() in d["expected_value"].lower() for d in defects)
        assert defects[0]["type"] == VisualDefectType.TYPO_MISMATCH.value

    # Correct text should produce no defects
    clean_text = "Ex-Showroom Price for Petrol and Diesel Manual Transmission with great Mileage"
    clean_defects = inspector.check_automotive_spelling(clean_text)
    assert len(clean_defects) == 0


def test_text_truncation_detection():
    inspector = VisualDesignInspector()

    elements = [
        {"text": "Book Te...", "resource-id": "com.cardekho.qa:id/btn_book", "class": "android.widget.Button"},
        {"text": "₹ 14,2...", "resource-id": "com.cardekho.qa:id/txt_price", "class": "android.widget.TextView"},
        {"text": "Special offer on selected models…", "resource-id": "com.cardekho.qa:id/txt_info", "class": "android.widget.TextView"},
        {"text": "View All Offers", "resource-id": "com.cardekho.qa:id/btn_offers", "class": "android.widget.Button"}
    ]

    truncations = inspector.check_text_truncation(elements)
    assert len(truncations) == 3

    # Critical CTA and Price should have P1 severity
    p1_truncations = [t for t in truncations if t["severity"] == VisualSeverity.P1.value]
    assert len(p1_truncations) == 2


def test_bounding_box_overlaps_and_overflows():
    inspector = VisualDesignInspector()

    # 1. Overlapping sibling elements
    elem1 = {
        "resource-id": "com.cardekho.qa:id/btn_apply",
        "class": "android.widget.Button",
        "text": "Apply Now",
        "bounds": "[100,200][400,300]"
    }
    elem2 = {
        "resource-id": "com.cardekho.qa:id/badge_new",
        "class": "android.widget.TextView",
        "text": "NEW",
        "bounds": "[150,220][350,280]"  # Significant overlap > 40%
    }
    elem3 = {
        "resource-id": "com.cardekho.qa:id/btn_cancel",
        "class": "android.widget.Button",
        "text": "Cancel",
        "bounds": "[100,350][400,450]"  # No overlap
    }

    overlaps = inspector.check_bounding_box_overlaps([elem1, elem2, elem3], screen_width=1080, screen_height=2400)
    assert len(overlaps) >= 1
    assert any(d["type"] == VisualDefectType.OVERLAPPING_ELEMENTS.value for d in overlaps)

    # 2. Horizontal screen overflow
    elem_overflow = {
        "resource-id": "com.cardekho.qa:id/txt_long_header",
        "class": "android.widget.TextView",
        "text": "CarDekho Premier Auto Fair Thiruvananthapuram Special Edition",
        "bounds": "[800,100][1150,180]"  # screen_width=1080 -> overflow by 70px
    }

    overflows = inspector.check_bounding_box_overlaps([elem_overflow], screen_width=1080, screen_height=2400)
    assert len(overflows) >= 1
    assert any(d["type"] == VisualDefectType.OFFSCREEN_OVERFLOW.value for d in overflows)


def test_parse_hierarchy_xml_and_audit_screen():
    xml_sample = """<?xml version='1.0' encoding='UTF-8' standalone='yes' ?>
    <hierarchy rotation="0">
      <node index="0" text="" resource-id="" class="android.widget.FrameLayout" bounds="[0,0][1080,2400]">
        <node index="0" text="Ex-Showrom Price: %s" resource-id="com.cardekho.qa:id/txt_price" class="android.widget.TextView" bounds="[50,150][600,220]" />
        <node index="1" text="Desiel" resource-id="com.cardekho.qa:id/txt_fuel" class="android.widget.TextView" bounds="[50,230][300,280]" />
        <node index="2" text="Check Off..." resource-id="com.cardekho.qa:id/btn_offers" class="android.widget.Button" bounds="[100,1000][400,1100]" />
        <node index="3" text="₹₹25,000 Off" resource-id="com.cardekho.qa:id/txt_discount" class="android.widget.TextView" bounds="[150,1020][380,1080]" />
      </node>
    </hierarchy>
    """
    inspector = VisualDesignInspector()
    elements = inspector.parse_hierarchy_xml(xml_sample)
    assert len(elements) == 5

    report = inspector.audit_screen(hierarchy_xml=xml_sample, screen_width=1080, screen_height=2400)
    assert report["has_visual_defects"] is True
    assert report["has_blockers"] is True
    assert report["blockers_count"] > 0
    assert report["total_defects"] > 0


def test_assertion_engine_visual_design_audit_clean_screen():
    clean_xml = """<?xml version='1.0' encoding='UTF-8' standalone='yes' ?>
    <hierarchy rotation="0">
      <node index="0" text="" resource-id="" class="android.widget.FrameLayout" bounds="[0,0][1080,2400]">
        <node index="0" text="Ex-Showroom Price: ₹ 12,49,000" resource-id="com.cardekho.qa:id/txt_price" class="android.widget.TextView" bounds="[50,150][600,220]" />
        <node index="1" text="Diesel Manual" resource-id="com.cardekho.qa:id/txt_fuel" class="android.widget.TextView" bounds="[50,250][400,320]" />
        <node index="2" text="Book Test Drive" resource-id="com.cardekho.qa:id/btn_book" class="android.widget.Button" bounds="[50,2100][1030,2250]" />
      </node>
    </hierarchy>
    """
    passed, msg = AssertionEngine.evaluate_assertion(
        assertion_spec={"kind": "VISUAL_DESIGN_AUDIT"},
        evidence_context={"hierarchy_xml": clean_xml, "page_text": "Ex-Showroom Price Diesel Manual Book Test Drive"}
    )
    assert passed is True
    assert "Visual Audit Passed" in msg


def test_assertion_engine_visual_design_audit_failing_screen():
    dirty_xml = """<?xml version='1.0' encoding='UTF-8' standalone='yes' ?>
    <hierarchy rotation="0">
      <node index="0" text="" resource-id="" class="android.widget.FrameLayout" bounds="[0,0][1080,2400]">
        <node index="0" text="Price: %s" resource-id="com.cardekho.qa:id/txt_price" class="android.widget.TextView" bounds="[50,150][600,220]" />
      </node>
    </hierarchy>
    """
    passed, msg = AssertionEngine.evaluate_assertion(
        assertion_spec={"kind": "VISUAL_DESIGN_AUDIT"},
        evidence_context={"hierarchy_xml": dirty_xml, "page_text": "Price: %s"}
    )
    assert passed is False
    assert "Visual Blocker Detected" in msg


def test_assertion_engine_no_template_leaks():
    clean_passed, clean_msg = AssertionEngine.evaluate_assertion(
        assertion_spec={"kind": "NO_TEMPLATE_LEAKS"},
        evidence_context={"page_text": "Price is ₹ 12,50,000 for Maruti Brezza ZXi"}
    )
    assert clean_passed is True

    leaky_passed, leaky_msg = AssertionEngine.evaluate_assertion(
        assertion_spec={"kind": "NO_TEMPLATE_LEAKS"},
        evidence_context={"page_text": "Error: Model is %s and price is null"}
    )
    assert leaky_passed is False
    assert "Template Token Leak" in leaky_msg


def test_qa_reporter_with_visual_audit():
    test_cases = [
        {"test_case_id": "TC-01", "title": "Check Home Page", "status": "PASSED", "priority": "P1"},
        {"test_case_id": "TC-02", "title": "Visual Design Audit", "status": "PASSED", "priority": "P1"}
    ]
    visual_audit_data = {
        "elements_audited": 42,
        "total_anomalies": 1,
        "blocker_count": 0,
        "polish_count": 1,
        "template_leak_free": True,
        "status": "PASS"
    }
    report = QAReporter.generate_final_report(
        execution={"id": "EXEC-VISUAL-1", "ticket_key": "MB2C-9999", "environment": "TESTING"},
        test_cases=test_cases,
        failures=[],
        visual_audit=visual_audit_data
    )

    assert "visual_audit" in report
    va = report["visual_audit"]
    assert va["elements_audited"] == 42
    assert va["blocker_count"] == 0
    assert va["template_leak_free"] is True

    jira_comment = QAReporter.format_jira_comment(report)
    assert "Visual & Micro-Copy Quality Audit" in jira_comment
    assert "UI Elements Audited | 42" in jira_comment
    assert "Template Leak Free: (/) YES" in jira_comment


def test_domain_terminology_leak_cardekho_and_bikedekho():
    inspector = VisualDesignInspector()

    # 1. CarDekho with 2-wheeler terminology
    cd_text = "Smart Shortlist: Based on your budget and riding needs. Wear a helmet for safety."
    cd_defects = inspector.check_domain_terminology(cd_text, brand="cardekho")
    assert len(cd_defects) >= 2
    assert any("riding needs" in d["actual_value"] for d in cd_defects)
    assert any(d["expected_value"] == "driving needs" for d in cd_defects)
    assert any(d["type"] == VisualDefectType.DOMAIN_COPY_LEAK.value for d in cd_defects)

    # 2. BikeDekho with 4-wheeler terminology
    bd_text = "Choose your two-wheeler based on driving needs and boot space."
    bd_defects = inspector.check_domain_terminology(bd_text, brand="bikedekho")
    assert len(bd_defects) >= 2
    assert any("driving needs" in d["actual_value"] for d in bd_defects)
    assert any("boot space" in d["actual_value"] for d in bd_defects)


def test_runtime_error_toast_detected():
    inspector = VisualDesignInspector()

    failing_screen_text = "Ask Expert: An Error Occurred, Please Try Again."
    defects = inspector.check_runtime_error_toasts(failing_screen_text)
    assert len(defects) >= 2
    assert any(d["type"] == VisualDefectType.RUNTIME_ERROR_TOAST.value for d in defects)
    assert any("an error occurred" in d["actual_value"] for d in defects)
    assert any("please try again" in d["actual_value"] for d in defects)

