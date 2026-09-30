"""
Tests for Targeted Regression Engine (Phase 1).
Validates DependencyGraph traversals, targeted scenario selection,
avoidance of full-suite regression, and Reference Jira link handling.
"""

import pytest
import os
import sys

skill_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if skill_root not in sys.path:
    sys.path.insert(0, skill_root)

from modules.regression.dependency_graph import DependencyGraph, NodeType, RelationType
from modules.regression.regression_selector import RegressionSelector, RegressionLevel


@pytest.fixture
def regression_selector():
    return RegressionSelector()


def test_dependency_graph_traversal():
    """Graph accurately locates downstream dependencies up to specified depth."""
    graph = DependencyGraph()
    # "price_tab" connects downstream to "lead_form", "variant_details", "emi_calculator"
    impacts = graph.get_downstream_impacts(["price_tab"], max_depth=1)
    assert "lead_form" in impacts or "variant_details" in impacts or "emi_calculator" in impacts


def test_targeted_regression_selection_does_not_run_full(regression_selector):
    """Regression selector chooses targeted 1st-degree collateral without full regression."""
    res = regression_selector.select_regression(
        affected_screens=["price_tab"],
        affected_modules=["pricing_engine"]
    )
    assert res["full_regression_executed"] is False
    assert 1 <= res["selected_count"] <= 4
    # Unrelated screens like "change_url" or "auth" must not be included
    target_areas = [s["target_area"] for s in res["scenarios"]]
    assert "change_url" not in target_areas
    assert "auth" not in target_areas


def test_isolated_change_has_zero_collateral(regression_selector):
    """Cosmetic or terminal leaf nodes produce zero or minimal targeted regression."""
    res = regression_selector.select_regression(
        affected_screens=["thank_you_screen"],
        affected_modules=["ui_cosmetics"]
    )
    assert res["full_regression_executed"] is False
    assert res["selected_count"] == 0
    assert "empty" in res["rationale"].lower() or "0" in str(res["selected_count"])


def test_reference_jira_inclusion(regression_selector):
    """Linked Jira ticket references generate targeted regression checks."""
    res = regression_selector.select_regression(
        affected_screens=["model_details"],
        affected_modules=["model_page"],
        reference_jira_keys=["MB2C-8891", "MB2C-9012"]
    )
    assert res["selected_count"] >= 2
    # Verify presence of reference Jira scenario
    ref_scenarios = [s for s in res["scenarios"] if s["target_area"] == "reference_jira"]
    assert len(ref_scenarios) >= 1
    assert "MB2C-8891" in ref_scenarios[0]["title"]


# ==============================================================================
# Advanced Targeted Regression Intelligence Tests
# ==============================================================================

def test_gallery_change_hierarchy_selection(regression_selector):
    """
    Validates exact prompt specification:
    Model Detail
     ├── Gallery
     ├── Colours
     ├── Videos
     ├── Variants
     ├── Price
     └── Lead CTA

    If Gallery changes (Risk: MEDIUM):
    - Regression Level: TARGETED
    - Selected: Gallery, Colours, Videos, Model navigation, Relevant API
    - Excluded: Unrelated Home modules, News, Used Cars
    """
    res = regression_selector.select_regression(
        changed_area="Gallery",
        risk_level="MEDIUM"
    )

    assert res["changed_area"] == "Gallery"
    assert res["risk_level"] == "MEDIUM"
    assert res["regression_level"] == "TARGETED"
    assert res["full_regression_executed"] is False

    # Check selected items
    selected_names = [it["name"] for it in res["selected_items"]]
    assert "Gallery" in selected_names
    assert "Colours" in selected_names
    assert "Videos" in selected_names
    assert "Model navigation" in selected_names
    assert "Relevant API" in selected_names

    # Check excluded items
    assert "Unrelated Home modules" in res["excluded_items"]
    assert "News" in res["excluded_items"]
    assert "Used Cars" in res["excluded_items"]

    # Verify explainability: Every selected item must have a non-empty reason
    for item in res["selected_items"]:
        assert "name" in item
        assert "reason" in item
        assert len(item["reason"].strip()) > 10

    # Verify formatted output block structure
    formatted = res["formatted_output"]
    assert "Changed Area:\nGallery" in formatted
    assert "Risk:\nMEDIUM" in formatted
    assert "Regression Level:\nTARGETED" in formatted
    assert "Selected:\nGallery\nColours\nVideos\nModel navigation\nRelevant API" in formatted
    assert "Excluded:\nUnrelated Home modules\nNews\nUsed Cars" in formatted


def test_regression_levels_mapping(regression_selector):
    """Validates all 5 regression levels: NONE, SMOKE, TARGETED, EXTENDED, FULL."""
    # 1. NONE: isolated copy/typo or cosmetic leaf
    assert regression_selector.determine_regression_level(
        risk_level="LOW",
        changed_area="Header typo fix",
        has_downstream=False
    ) == RegressionLevel.NONE

    # 2. SMOKE: LOW risk UI-only
    assert regression_selector.determine_regression_level(
        risk_level="LOW",
        changed_area="Button border radius",
        has_downstream=True
    ) == RegressionLevel.SMOKE

    # 3. TARGETED: MEDIUM risk functional feature
    assert regression_selector.determine_regression_level(
        risk_level="MEDIUM",
        changed_area="Gallery slider",
        has_downstream=True
    ) == RegressionLevel.TARGETED

    # 4. EXTENDED: HIGH risk multi-screen or core feature
    assert regression_selector.determine_regression_level(
        risk_level="HIGH",
        changed_area="Pricing Breakdown Module",
        has_downstream=True
    ) == RegressionLevel.EXTENDED

    # 5. FULL: CRITICAL risk with global architectural impact
    assert regression_selector.determine_regression_level(
        risk_level="CRITICAL",
        changed_area="Global App Navigation & Auth Rewrite",
        is_global_impact=True
    ) == RegressionLevel.FULL


def test_strict_full_regression_gating(regression_selector):
    """Strict Gate: Never selects FULL unless justified by CRITICAL risk and global impact."""
    # MEDIUM risk cannot trigger FULL, even if global is requested
    assert regression_selector.determine_regression_level(
        risk_level="MEDIUM",
        changed_area="Home module",
        is_global_impact=True
    ) != RegressionLevel.FULL

    # HIGH risk cannot trigger FULL
    assert regression_selector.determine_regression_level(
        risk_level="HIGH",
        changed_area="Search engine overhaul",
        is_global_impact=True
    ) != RegressionLevel.FULL

    # CRITICAL risk without global impact is downgraded to EXTENDED, NOT FULL
    assert regression_selector.determine_regression_level(
        risk_level="CRITICAL",
        changed_area="Isolated native crash in review tab",
        is_global_impact=False
    ) == RegressionLevel.EXTENDED


def test_dependency_graph_hierarchy_inspection():
    """DependencyGraph returns parent, siblings, apis, navigation, and children accurately."""
    graph = DependencyGraph()
    hierarchy = graph.get_feature_hierarchy("gallery")

    assert hierarchy["name"] == "gallery"
    assert hierarchy["parent"] == "model_details"
    assert "Colours" in hierarchy["siblings"]
    assert "Videos" in hierarchy["siblings"]
    assert "/api/v1/model/gallery" in hierarchy["apis"]
    assert "Model navigation" in hierarchy["navigation"]

