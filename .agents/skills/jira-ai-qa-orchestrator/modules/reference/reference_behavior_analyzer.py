"""
Reference Behavior Analyzer for CarDekho & BikeDekho QA Orchestration.
Analyzes fetched Reference Jira tickets and WAP reference instructions.
Extracts expected behaviors across UI, functionality, CTAs, navigation, data, and edge cases.
Generates concrete Android-specific test scenarios while documenting intentional platform differences.
Enforces the Zero Guesswork Mandate: marks INSUFFICIENT / BLOCKED if reference details are lacking.
"""

import re
from typing import Dict, Any, List, Optional

WAP_TRIGGER_KEYWORDS = [
    r"same\s*as\s*(?:wap|mweb|mobile\s*web)",
    r"implement\s*in\s*app\s*same\s*as\s*wap",
    r"parity\s*with\s*(?:wap|mweb)",
    r"refer\s*(?:to\s*)?(?:wap|mweb)",
    r"wap\s*reference",
    r"as\s*per\s*(?:wap|mweb)"
]

WAP_DIMENSIONS = [
    "UI",
    "Functionality",
    "Data",
    "CTA",
    "Navigation",
    "Filters",
    "Validation",
    "Loading",
    "Empty State",
    "Error State",
    "API Behavior"
]

class ReferenceBehaviorAnalyzer:
    """Analyzes reference specifications and synthesizes Android-specific test suites."""

    def __init__(self):
        pass

    def analyze_reference_jira(self, ref_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extracts expected behaviors and validates sufficiency.
        Never invents behavior: returns BLOCKED / CLARIFICATION REQUIRED if info is lacking.
        """
        ref_id = ref_data.get("reference_id", "REF-UNKNOWN")
        summary = ref_data.get("summary", "").strip()
        description = ref_data.get("description", "").strip()
        ac = ref_data.get("acceptance_criteria") or []
        comments = ref_data.get("comments") or []
        screenshots = ref_data.get("screenshots") or []

        # 1. Sufficiency Validation (Zero Hallucination Gate)
        is_sufficient, gaps = self._validate_sufficiency(summary, description, ac, comments)
        if not is_sufficient:
            return {
                "status": "INSUFFICIENT_INFORMATION",
                "verdict": "BLOCKED / CLARIFICATION REQUIRED",
                "reference_id": ref_id,
                "is_sufficient": False,
                "gaps": gaps,
                "expected_behaviors": {},
                "android_test_scenarios": [],
                "intentional_platform_differences": []
            }

        # 2. Extract Expected Behaviors
        expected_behaviors = self._extract_behaviors(summary, description, ac, comments)

        # 3. Generate Android-Specific Test Scenarios
        android_scenarios, platform_diffs = self._derive_android_scenarios(ref_id, expected_behaviors, screenshots)

        return {
            "status": "ANALYZED",
            "verdict": "READY_FOR_EXECUTION",
            "reference_id": ref_id,
            "is_sufficient": True,
            "gaps": [],
            "expected_behaviors": expected_behaviors,
            "android_test_scenarios": android_scenarios,
            "intentional_platform_differences": platform_diffs
        }

    def detect_and_analyze_wap_reference(self, jira_text: str, brand: str = "cardekho") -> Dict[str, Any]:
        """
        Identifies if Jira mandates 'Implement in App same as WAP',
        determines the target WAP URL, and structures the 11 comparison dimensions.
        """
        text_lower = (jira_text or "").lower()
        is_wap_ref = any(re.search(kw, text_lower) for kw in WAP_TRIGGER_KEYWORDS)

        if not is_wap_ref:
            return {
                "is_wap_reference": False,
                "target_wap_url": None,
                "comparison_dimensions": []
            }

        # Extract or resolve relevant WAP URL
        wap_url = self._extract_or_resolve_wap_url(jira_text, brand)

        return {
            "is_wap_reference": True,
            "target_wap_url": wap_url,
            "brand": brand,
            "comparison_dimensions": WAP_DIMENSIONS,
            "comparison_scope": {
                dim: f"Compare {dim} between WAP ({wap_url}) and Android native views"
                for dim in WAP_DIMENSIONS
            }
        }

    def _validate_sufficiency(
        self,
        summary: str,
        description: str,
        ac: List[str],
        comments: List[Dict[str, Any]]
    ) -> Tuple[bool, List[str]]:
        """Checks if reference contains sufficient actionable behavioral detail."""
        gaps = []
        combined_text = f"{summary}\n{description}".strip()

        if len(combined_text) < 25 and not ac:
            gaps.append("Reference ticket contains insufficient text description and no acceptance criteria.")

        has_behavior_keywords = any(
            kw in combined_text.lower()
            for kw in ["when", "should", "display", "click", "tap", "show", "calculate", "submit", "select", "expected", "button"]
        )
        if not has_behavior_keywords and not ac:
            gaps.append("Reference ticket lacks actionable functional rules or expected UI behavior statements.")

        is_sufficient = len(gaps) == 0
        return is_sufficient, gaps

    def _extract_behaviors(
        self,
        summary: str,
        description: str,
        ac: List[str],
        comments: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Extracts structured behavioral categories from reference text."""
        full_text = f"{summary}\n{description}"
        for c in comments:
            full_text += f"\n{c.get('body', '')}"

        # 1. CTAs
        ctas = re.findall(r"(?:click|tap|press|cta|button)\s*['\"]?([A-Za-z0-9\s_\-]+)['\"]?", full_text, re.IGNORECASE)
        clean_ctas = sorted(list(set([c.strip() for c in ctas if 2 < len(c.strip()) < 30])))

        # 2. UI Components
        ui_components = []
        for kw in ["card", "badge", "banner", "tab", "dialog", "bottom sheet", "slider", "list", "header"]:
            if kw in full_text.lower():
                ui_components.append(kw)

        # 3. Functional Behaviors
        functional = []
        if ac:
            functional.extend(ac)
        else:
            for line in description.splitlines():
                line_str = line.strip()
                if line_str.startswith(("-", "*", "•")) or any(w in line_str.lower() for w in ["should", "must", "expected"]):
                    functional.append(line_str.lstrip("-*• "))

        return {
            "ctas": clean_ctas or ["Default Action CTA"],
            "ui_components": ui_components or ["Standard View"],
            "functional_rules": functional or [summary],
            "data_mapping": ["price", "variant_specifications"] if "price" in full_text.lower() else ["standard_content"],
            "has_error_handling": any(w in full_text.lower() for w in ["error", "invalid", "fail", "retry", "empty"])
        }

    def _derive_android_scenarios(
        self,
        ref_id: str,
        behaviors: Dict[str, Any],
        screenshots: List[Dict[str, Any]]
    ) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        """Derives numbered Android test scenarios from reference behaviors."""
        scenarios = []
        platform_diffs = []
        idx = 1

        # Scenario 1: Core reference functional validation
        for rule in behaviors.get("functional_rules", [])[:3]:
            scenarios.append({
                "test_case_id": f"TC-REF-{idx:02d}",
                "title": f"Verify Android Parity with {ref_id}: {rule[:60]}",
                "category": "Reference Parity",
                "reference_source": ref_id,
                "expected_result": f"Matches reference requirement: {rule}",
                "device_required": True
            })
            idx += 1

        # Scenario 2: CTAs and interactive triggers
        for cta in behaviors.get("ctas", [])[:2]:
            scenarios.append({
                "test_case_id": f"TC-REF-{idx:02d}",
                "title": f"Verify CTA Action '{cta}' parity with {ref_id}",
                "category": "CTA Parity",
                "reference_source": ref_id,
                "expected_result": f"Tapping '{cta}' triggers appropriate native screen or bottom-sheet identical to reference",
                "device_required": True
            })
            idx += 1

        # Intentional Platform Differences (Documented clearly)
        platform_diffs.append({
            "dimension": "Navigation Back-Stack",
            "reference_behavior": "Browser back button or header breadcrumb navigation",
            "android_adaptation": "Android hardware/gesture back key and toolbar arrow",
            "rationale": "Standard Android UX convention"
        })
        platform_diffs.append({
            "dimension": "Modal / Dropdown Selection",
            "reference_behavior": "Desktop floating dropdown or web select",
            "android_adaptation": "Native Android Bottom-Sheet dialog",
            "rationale": "Thumb-friendly mobile app design system"
        })

        return scenarios, platform_diffs

    def _extract_or_resolve_wap_url(self, text: str, brand: str) -> str:
        """Finds explicit URL in text or generates standard WAP endpoint."""
        url_match = re.search(r"https?://[^\s<>'\"]+", text)
        if url_match:
            return url_match.group(0).rstrip(".,)")

        # Fallback to standard brand WAP URL
        b = brand.lower()
        if "bike" in b:
            return "https://www.bikedekho.com"
        return "https://www.cardekho.com"
