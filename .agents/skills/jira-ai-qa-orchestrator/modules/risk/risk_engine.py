"""
Risk Engine for CarDekho & BikeDekho QA Orchestration.
Classifies Jira tasks into LOW, MEDIUM, HIGH, CRITICAL based on architectural impact,
business blast radius, and failure consequence.
Directly determines testing depth without inventing missing requirements.
"""

import os
import json
from enum import Enum
from typing import Dict, Any, List, Optional
from .impact_analyzer import ImpactAnalyzer

RULES_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "risk_rules.json")

class RiskLevel(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"

class RiskEngine:
    """Evaluates risk score and testing depth for Jira tickets."""

    def __init__(self, rules_path: Optional[str] = None):
        self.rules_path = rules_path or RULES_PATH
        self.rules = self._load_rules()
        self.impact_analyzer = ImpactAnalyzer()

    def _load_rules(self) -> Dict[str, Any]:
        if os.path.exists(self.rules_path):
            try:
                with open(self.rules_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
        return {}

    def classify_ticket(
        self,
        summary: str,
        description: str = "",
        labels: Optional[List[str]] = None,
        components: Optional[List[str]] = None,
        linked_issues: Optional[List[Dict[str, Any]]] = None
    ) -> Dict[str, Any]:
        """
        Computes risk level, score, blast radius, and recommended testing depth.
        """
        impact = self.impact_analyzer.analyze_ticket(
            summary=summary,
            description=description,
            labels=labels,
            components=components,
            linked_issues=linked_issues
        )

        score = 0
        score_breakdown = []

        full_text = f"{summary or ''}\n{description or ''}".lower()
        keyword_weights = self.rules.get("keyword_weights", {})
        module_weights = self.rules.get("module_weights", {})

        # 1. Crash Fix (Automatic High/Critical floor)
        if impact["is_crash_fix"]:
            score += 45
            score_breakdown.append(("crash_fix_detected", 45))

        # 2. Authentication / Session Impact
        if impact["is_auth_impact"]:
            score += 35
            score_breakdown.append(("auth_session_impact", 35))

        # 3. Lead / Revenue Flow Impact
        if impact["is_lead_impact"]:
            score += 35
            score_breakdown.append(("lead_conversion_impact", 35))

        # 4. API / Backend Dependency
        if impact["api_dependencies"]:
            pts = min(30, len(impact["api_dependencies"]) * 15)
            score += pts
            score_breakdown.append(("api_dependencies", pts))

        # 5. Cross-Module Blast Radius
        if impact["cross_module_impact"]:
            score += 20
            score_breakdown.append(("cross_module_impact", 20))

        # 6. Specific Module Weights
        for mod in impact["affected_modules"]:
            if mod in module_weights:
                pts = module_weights[mod]
                score += pts
                score_breakdown.append((f"module_{mod}", pts))

        # 7. Keyword Weight Matching (Bonus nuance)
        matched_keywords = set()
        for kw, wt in keyword_weights.items():
            if kw in full_text and kw not in matched_keywords:
                matched_keywords.add(kw)
                # Apply capped keyword score to prevent unbounded escalation
                score += min(wt, 15)

        # 8. UI-Only Discount
        if impact["is_ui_only"]:
            score = min(score, 15)  # Cap UI-only changes firmly in LOW category
            score_breakdown.append(("ui_only_discount", -10))

        # Classify Level
        if score >= 75 or (impact["is_crash_fix"] and (impact["is_auth_impact"] or impact["is_lead_impact"])):
            level = RiskLevel.CRITICAL
        elif score >= 50 or impact["is_lead_impact"] or impact["is_auth_impact"] or impact["is_crash_fix"]:
            level = RiskLevel.HIGH
        elif score >= 25 or impact["cross_module_impact"]:
            level = RiskLevel.MEDIUM
        else:
            level = RiskLevel.LOW

        level_config = self.rules.get("risk_levels", {}).get(level.value, {
            "testing_depth": "STANDARD",
            "min_test_cases": 4,
            "required_categories": ["positive", "negative", "ui_ux"]
        })

        # Check for missing requirements without inventing
        missing_flags = self._detect_missing_requirements(summary, description, impact)

        return {
            "risk_level": level.value,
            "risk_score": score,
            "score_breakdown": score_breakdown,
            "testing_depth": level_config.get("testing_depth", "STANDARD"),
            "min_test_cases": level_config.get("min_test_cases", 4),
            "required_categories": level_config.get("required_categories", []),
            "affected_screens": impact["affected_screens"],
            "affected_modules": impact["affected_modules"],
            "api_dependencies": impact["api_dependencies"],
            "cross_module_impact": impact["cross_module_impact"],
            "secondary_impacts": impact["secondary_impacts"],
            "is_crash_fix": impact["is_crash_fix"],
            "is_ui_only": impact["is_ui_only"],
            "missing_requirements": missing_flags,
            "attack_surface": impact.get("attack_surface", {}),
            "prioritized_attack_vectors": impact.get("attack_surface", {}).get("identified_vectors", []),
            "primary_threat_vector": impact.get("attack_surface", {}).get("primary_threat_vector", "STATE_LIFECYCLE"),
            "bug_hunting_motto": "BREAK THE FEATURE BEFORE THE USER DOES.",
            "attack_dimensions": impact.get("attack_surface", {}).get("attack_dimensions", {})
        }

    def _detect_missing_requirements(self, summary: str, description: str, impact: Dict[str, Any]) -> List[str]:
        """Identifies gaps without guessing or hallucinating requirements."""
        gaps = []
        combined = f"{summary}\n{description}".lower()

        # Check if steps or expected outcome is missing
        if "step" not in combined and "expected" not in combined and "acceptance" not in combined:
            gaps.append("Ticket lacks explicit Acceptance Criteria or Steps to Reproduce")

        # Check if target model/entity is specified for vehicle pages
        if any(s in impact["affected_screens"] for s in ["model_details", "variant_details", "price_tab"]):
            known_brands = ["hyundai", "maruti", "tata", "mahindra", "kia", "honda", "toyota", "royal enfield", "hero", "bajaj", "tvs", "yamaha"]
            if not any(b in combined for b in known_brands):
                gaps.append("Vehicle model or brand context not explicitly specified in Jira")

        return gaps
