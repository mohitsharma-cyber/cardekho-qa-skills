"""
Comparison Engine for Reference Jira and WAP Parity in CarDekho & BikeDekho QA.
Performs deterministic, structured comparisons across all 11 dimensions:
UI, Functionality, Data, CTA, Navigation, Filters, Validation, Loading,
Empty State, Error State, and API Behavior.

Supports explicit statuses:
- PASS
- FAIL
- EXPECTED_PLATFORM_DIFFERENCE
- NOT_TESTED
- BLOCKED
"""

from enum import Enum
from typing import Dict, Any, List, Optional

class ComparisonStatus(str, Enum):
    __test__ = False
    PASS = "PASS"
    FAIL = "FAIL"
    EXPECTED_PLATFORM_DIFFERENCE = "EXPECTED_PLATFORM_DIFFERENCE"
    NOT_TESTED = "NOT_TESTED"
    BLOCKED = "BLOCKED"

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

class ComparisonEngine:
    """Evaluates structured parity between Reference implementation (WAP/Jira) and Android App."""

    def __init__(self):
        pass

    def compare_item(
        self,
        area: str,
        reference: Any,
        android: Any,
        is_platform_difference: bool = False,
        diff_rationale: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Compares a single area/feature and returns structured result:
        {
          "area": "CTA",
          "reference": "Explore Now",
          "android": "Explore Now",
          "status": "PASS"
        }
        """
        # 1. Blocked check
        if reference == "BLOCKED" or android == "BLOCKED":
            return {
                "area": area,
                "reference": str(reference),
                "android": str(android),
                "status": ComparisonStatus.BLOCKED.value,
                "rationale": "Comparison blocked due to prerequisite failure or missing environment."
            }

        # 2. Not tested check
        if reference is None or android is None or reference == "NOT_TESTED" or android == "NOT_TESTED":
            return {
                "area": area,
                "reference": str(reference) if reference is not None else "NOT_PROVIDED",
                "android": str(android) if android is not None else "NOT_TESTED",
                "status": ComparisonStatus.NOT_TESTED.value,
                "rationale": "Value has not been evaluated on Android or reference."
            }

        # 3. Expected Platform Difference check
        if is_platform_difference:
            return {
                "area": area,
                "reference": str(reference),
                "android": str(android),
                "status": ComparisonStatus.EXPECTED_PLATFORM_DIFFERENCE.value,
                "rationale": diff_rationale or "Intentional UX adaptation for Android mobile platform."
            }

        # 4. Equality check (String or Object)
        ref_norm = str(reference).strip().lower()
        and_norm = str(android).strip().lower()

        if ref_norm == and_norm:
            status = ComparisonStatus.PASS.value
            rationale = "Android implementation matches reference exactly."
        else:
            status = ComparisonStatus.FAIL.value
            rationale = f"Mismatch in {area}: Reference expected '{reference}', Android observed '{android}'."

        result = {
            "area": area,
            "reference": reference,
            "android": android,
            "status": status
        }
        if rationale:
            result["rationale"] = rationale

        return result

    def compare_wap_parity(
        self,
        wap_spec: Dict[str, Any],
        android_spec: Dict[str, Any],
        known_differences: Optional[Dict[str, str]] = None
    ) -> Dict[str, Any]:
        """
        Executes a complete 11-dimension parity comparison between WAP and Android.
        """
        known_differences = known_differences or {}
        comparison_items = []

        for area in WAP_DIMENSIONS:
            ref_val = wap_spec.get(area)
            and_val = android_spec.get(area)
            is_diff = area in known_differences
            diff_rationale = known_differences.get(area)

            item = self.compare_item(
                area=area,
                reference=ref_val,
                android=and_val,
                is_platform_difference=is_diff,
                diff_rationale=diff_rationale
            )
            comparison_items.append(item)

        # Calculate metrics
        passed = sum(1 for it in comparison_items if it["status"] == ComparisonStatus.PASS.value)
        failed = sum(1 for it in comparison_items if it["status"] == ComparisonStatus.FAIL.value)
        platform_diff = sum(1 for it in comparison_items if it["status"] == ComparisonStatus.EXPECTED_PLATFORM_DIFFERENCE.value)
        not_tested = sum(1 for it in comparison_items if it["status"] == ComparisonStatus.NOT_TESTED.value)
        blocked = sum(1 for it in comparison_items if it["status"] == ComparisonStatus.BLOCKED.value)

        total_evaluated = passed + failed + platform_diff
        total_dim = len(WAP_DIMENSIONS)

        # Successful parity counts PASS + valid platform differences
        parity_score = round(((passed + platform_diff) / total_dim) * 100.0, 2)

        if failed > 0:
            overall = "FAIL"
        elif blocked > 0:
            overall = "BLOCKED"
        elif not_tested > 0:
            overall = "PARTIAL"
        else:
            overall = "PASS"

        return {
            "overall_status": overall,
            "parity_score_percentage": parity_score,
            "metrics": {
                "total_dimensions": total_dim,
                "passed": passed,
                "failed": failed,
                "expected_platform_differences": platform_diff,
                "not_tested": not_tested,
                "blocked": blocked
            },
            "comparison_results": comparison_items,
            "discrepancies": [it for it in comparison_items if it["status"] == ComparisonStatus.FAIL.value]
        }
