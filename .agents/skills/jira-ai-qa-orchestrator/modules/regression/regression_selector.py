"""
Advanced Dependency-Aware Targeted Regression Selector for CarDekho & BikeDekho.
Evaluates blast radius across Jira features, screens, modules, APIs, navigation,
business flows, and existing test cases.

Supports 5 Regression Levels:
- NONE
- SMOKE
- TARGETED
- EXTENDED
- FULL (strictly gated: never selected unless justified by risk/impact)

Provides explainable, formatted regression summaries where every selected
scenario has an explicit reason.
"""

from enum import Enum
from typing import Dict, Any, List, Optional, Set
from .dependency_graph import DependencyGraph, NodeType

class RegressionLevel(str, Enum):
    __test__ = False
    NONE = "NONE"
    SMOKE = "SMOKE"
    TARGETED = "TARGETED"
    EXTENDED = "EXTENDED"
    FULL = "FULL"

# Standard scenario templates for regression cases
SCENARIO_TEMPLATES = {
    "lead_form": {
        "title": "Lead Form & Sticky CTA Retest",
        "description": "Verify CTA button triggers lead bottom-sheet without crash and pre-fills vehicle context.",
        "preconditions": "On active model or variant page with sticky CTA visible",
        "reason": "Direct conversion dependency from model and pricing pages"
    },
    "variant_details": {
        "title": "Variant Switching & Specs Integrity",
        "description": "Switch between at least two variants and assert prices and feature matrices re-render accurately.",
        "preconditions": "Variant page opened from Model Overview",
        "reason": "Direct spec and price variation dependency"
    },
    "price_tab": {
        "title": "On-Road Price Breakdown Regression",
        "description": "Open Price tab, assert Ex-Showroom, RTO, Insurance rows calculate and expand correctly.",
        "preconditions": "Model details Price tab active",
        "reason": "Primary monetary calculation verification"
    },
    "emi_calculator": {
        "title": "EMI Calculator Slider Sanity",
        "description": "Adjust loan tenure slider and assert monthly EMI calculation updates dynamically without UI freeze.",
        "preconditions": "EMI calculator accessible from Price section",
        "reason": "Sibling calculation component depending on on-road price"
    },
    "search": {
        "title": "Global Search Autosuggest Regression",
        "description": "Enter top search term and verify instant suggestions appear without keyboard blockage.",
        "preconditions": "Home screen search input active",
        "reason": "Primary discovery entrypoint feeding into model details"
    },
    "change_url": {
        "title": "Server Connectivity & Base URL Retention",
        "description": "Assert app maintains configured target server without reverting to live production.",
        "preconditions": "Change URL screen verified",
        "reason": "Global environment routing integrity"
    },
    "auth": {
        "title": "User Session & Login State Retention",
        "description": "Verify app respects active session or gracefully prompts login modal on gated action.",
        "preconditions": "User interacts with gated feature",
        "reason": "Authentication state gate required for user actions"
    }
}

class RegressionSelector:
    """Dependency-aware regression selector ensuring targeted, explainable test suites."""

    def __init__(self, graph: Optional[DependencyGraph] = None):
        self.graph = graph or DependencyGraph()

    def determine_regression_level(
        self,
        risk_level: str = "MEDIUM",
        changed_area: str = "",
        affected_modules: Optional[List[str]] = None,
        is_global_impact: bool = False,
        has_downstream: bool = True
    ) -> RegressionLevel:
        """
        Determines the appropriate regression level based on risk and blast radius.
        Strict Gate: Never selects FULL unless justified by risk/impact.
        """
        rl = risk_level.upper().strip()
        ca = changed_area.lower().strip()
        modules = [m.lower().strip() for m in (affected_modules or [])]

        # 1. NONE: Isolated copy/typo, cosmetic, or zero-downstream leaf nodes
        if "ui_cosmetics" in modules or any(w in ca for w in ["typo", "text copy", "copy update", "banner text", "cosmetic", "thank_you"]):
            return RegressionLevel.NONE
        if rl == "LOW" and not has_downstream:
            return RegressionLevel.NONE

        # 2. SMOKE: UI-only cosmetic changes
        if rl == "LOW":
            return RegressionLevel.SMOKE

        # 3. TARGETED: Standard functional features / single screen modules
        if rl == "MEDIUM":
            return RegressionLevel.TARGETED

        # 4. EXTENDED: High-risk multi-screen, pricing, or search changes
        if rl == "HIGH":
            return RegressionLevel.EXTENDED

        # 5. FULL: Gated strictly to CRITICAL global architectural changes
        if rl == "CRITICAL":
            if is_global_impact or any(w in ca for w in ["global", "core auth", "payment gateway", "base network", "app architecture"]):
                return RegressionLevel.FULL
            return RegressionLevel.EXTENDED

        return RegressionLevel.TARGETED

    def select_regression(
        self,
        affected_screens: Optional[List[str]] = None,
        affected_modules: Optional[List[str]] = None,
        api_dependencies: Optional[List[str]] = None,
        reference_jira_keys: Optional[List[str]] = None,
        changed_area: Optional[str] = None,
        risk_level: str = "MEDIUM",
        is_global_impact: bool = False
    ) -> Dict[str, Any]:
        """
        Builds explainable targeted regression suite.
        Supports both legacy parameters and advanced hierarchical feature selection.
        """
        affected_screens = affected_screens or []
        affected_modules = affected_modules or []
        api_dependencies = api_dependencies or []
        reference_jira_keys = reference_jira_keys or []

        # Derive primary changed area
        primary_area = changed_area or (affected_screens[0] if affected_screens else (affected_modules[0] if affected_modules else "Model Detail"))
        clean_primary = primary_area.replace("_", " ").title()

        # Check downstream impacts in graph
        primary_nodes = list(set([s.lower() for s in affected_screens] + [m.lower() for m in affected_modules]))
        downstream = self.graph.get_downstream_impacts(primary_nodes or [primary_area.lower()], max_depth=1)
        primary_set = set(primary_nodes or [primary_area.lower()])
        collateral_nodes = [node for node in downstream if node not in primary_set]
        has_downstream = bool(collateral_nodes)

        # Determine regression level
        level = self.determine_regression_level(
            risk_level=risk_level,
            changed_area=primary_area,
            affected_modules=affected_modules,
            is_global_impact=is_global_impact,
            has_downstream=has_downstream
        )

        # Query graph hierarchy for primary area
        hierarchy = self.graph.get_feature_hierarchy(primary_area)
        unrelated_modules = self.graph.get_unrelated_modules(primary_area)

        selected_items = []
        excluded_items = []
        selected_scenarios = []
        scenario_counter = 1

        if level == RegressionLevel.NONE:
            excluded_items = ["All application regression suites"]
            rationale = "Change is isolated with 0 downstream impacts. No regression suite needed (empty)."
        elif level == RegressionLevel.SMOKE:
            selected_items.append({"name": clean_primary, "reason": "Primary changed UI sanity verification"})
            excluded_items = unrelated_modules
            rationale = f"Smoke regression: validating {clean_primary} view rendering only."
        else:
            # TARGETED or EXTENDED
            # 1. Primary changed feature
            selected_items.append({"name": clean_primary, "reason": "Primary modified feature verification"})

            # 2. Immediate siblings in hierarchy (e.g. Gallery -> Colours, Videos)
            if hierarchy.get("siblings"):
                for sib in hierarchy["siblings"]:
                    # Limit to relevant siblings based on cluster
                    if "gallery" in primary_area.lower() and sib.lower() in ["colours", "videos"]:
                        selected_items.append({
                            "name": sib,
                            "reason": f"Sibling visual media component sharing container state with {clean_primary}"
                        })
                    elif "price" in primary_area.lower() and sib.lower() in ["variants", "emi calculator"]:
                        selected_items.append({
                            "name": sib,
                            "reason": f"Sibling pricing/variant component depending on {clean_primary}"
                        })

            # 3. Navigation components
            for nav in hierarchy.get("navigation", []):
                selected_items.append({
                    "name": nav,
                    "reason": f"Navigation container maintaining tab routing and backstack for {clean_primary}"
                })

            # 4. Relevant API
            if hierarchy.get("apis") or api_dependencies:
                selected_items.append({
                    "name": "Relevant API",
                    "reason": f"Backend API data contract validation ({', '.join(hierarchy.get('apis', [])[:1] or api_dependencies[:1])})"
                })

            # 5. Build Collateral Scenarios for backwards compatibility
            primary_nodes = list(set([s.lower() for s in affected_screens] + [m.lower() for m in affected_modules]))
            downstream = self.graph.get_downstream_impacts(primary_nodes or [primary_area.lower()], max_depth=1)
            primary_set = set(primary_nodes or [primary_area.lower()])
            collateral_nodes = [node for node in downstream if node not in primary_set]

            for node in sorted(collateral_nodes):
                if node in SCENARIO_TEMPLATES:
                    tmpl = SCENARIO_TEMPLATES[node]
                    selected_scenarios.append({
                        "id": f"REG-{scenario_counter:02d}",
                        "target_area": node,
                        "title": tmpl["title"],
                        "description": tmpl["description"],
                        "preconditions": tmpl["preconditions"],
                        "rationale": tmpl.get("reason", f"Collateral impact from {clean_primary}")
                    })
                    scenario_counter += 1

            # Excluded modules
            excluded_items = unrelated_modules
            rationale = (
                f"Selected {len(selected_items)} targeted component(s) based on 1st-degree relationships from {clean_primary}. "
                f"Excluded non-impacted subsystems to maintain fast, lean execution."
            )

        # Reference Jira Handling
        if reference_jira_keys:
            for ref_key in reference_jira_keys[:2]:
                selected_scenarios.append({
                    "id": f"REG-{scenario_counter:02d}",
                    "target_area": "reference_jira",
                    "title": f"Reference Jira Validation ({ref_key})",
                    "description": f"Verify surrounding workflow related to linked issue {ref_key} has not regressed.",
                    "preconditions": f"Ticket linked to {ref_key}",
                    "rationale": f"Explicit reference link in Jira ticket {ref_key}"
                })
                scenario_counter += 1

        # Format exact requested output string
        formatted_output = self._format_output_block(
            changed_area=clean_primary,
            risk_level=risk_level.upper(),
            regression_level=level.value,
            selected_items=[it["name"] for it in selected_items],
            excluded_items=excluded_items
        )

        return {
            "changed_area": clean_primary,
            "risk_level": risk_level.upper(),
            "regression_level": level.value,
            "selected_items": selected_items,
            "excluded_items": excluded_items,
            "selected_count": len(selected_scenarios) or len(selected_items),
            "scenarios": selected_scenarios,
            "collateral_areas": [it["name"] for it in selected_items],
            "rationale": rationale,
            "formatted_output": formatted_output,
            "full_regression_executed": level == RegressionLevel.FULL
        }

    def _format_output_block(
        self,
        changed_area: str,
        risk_level: str,
        regression_level: str,
        selected_items: List[str],
        excluded_items: List[str]
    ) -> str:
        """
        Formats regression selection matching user requested structure:
        Changed Area:
        Gallery

        Risk:
        MEDIUM

        Regression Level:
        TARGETED

        Selected:
        Gallery
        Colours
        Videos
        Model navigation
        Relevant API

        Excluded:
        Unrelated Home modules
        News
        Used Cars
        """
        sel_str = "\n".join(selected_items) if selected_items else "None"
        excl_str = "\n".join(excluded_items) if excluded_items else "None"

        return (
            f"Changed Area:\n"
            f"{changed_area}\n\n"
            f"Risk:\n"
            f"{risk_level}\n\n"
            f"Regression Level:\n"
            f"{regression_level}\n\n"
            f"Selected:\n"
            f"{sel_str}\n\n"
            f"Excluded:\n"
            f"{excl_str}"
        )
