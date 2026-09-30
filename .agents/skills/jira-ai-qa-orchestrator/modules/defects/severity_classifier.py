"""
Severity & Priority Classifier for Defect Intelligence in Jira AI QA Orchestrator.
Classifies failures into Blocker, Critical, Major, Medium, and Minor
based on blast radius, error signatures, and business impact.
"""

from typing import Dict, Any, Tuple

CRITICAL_SIGNATURES = [
    "fatal exception", "anr", "nullpointerexception", "sigsegv",
    "crash", "force close", "out of memory", "oom", "securityexception",
    "login failed", "payment failed", "lead submission blocked"
]

MAJOR_SIGNATURES = [
    "500 internal server error", "price mismatch", "calculation error",
    "cta unresponsive", "endpoint returned 5", "data loss", "corrupted json"
]

MEDIUM_SIGNATURES = [
    "filter not applying", "sorting mismatch", "shimmer timeout",
    "404 not found", "empty search results"
]

class SeverityClassifier:
    """Classifies defect severity and suggests priority for Jira defect cards."""

    @staticmethod
    def classify(
        summary: str,
        error_message: str = "",
        logcat_snippet: str = "",
        probable_layer: str = "UI"
    ) -> Tuple[str, str]:
        """
        Returns (severity, priority_suggestion).
        """
        combined = f"{summary} {error_message} {logcat_snippet}".lower()

        # 1. Critical / Blocker: Crash, ANR, payment, authentication
        if any(sig in combined for sig in CRITICAL_SIGNATURES):
            return "Blocker", "Highest"

        # 2. Major: Pricing, 500 errors, broken core CTAs
        if any(sig in combined for sig in MAJOR_SIGNATURES) or probable_layer in ["Backend", "Data"]:
            return "Major", "High"

        # 3. Medium: Functional edge-cases, filters, timeouts
        if any(sig in combined for sig in MEDIUM_SIGNATURES) or probable_layer in ["API", "Configuration"]:
            return "Medium", "Medium"

        # 4. Minor: UI cosmetic, layout styling, label typo
        return "Minor", "Low"
