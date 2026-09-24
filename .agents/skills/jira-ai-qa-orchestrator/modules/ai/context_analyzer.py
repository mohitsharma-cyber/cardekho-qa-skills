"""
AI Requirement & Context Analyzer for Jira AI QA Orchestrator.
Performs deterministic and heuristic extraction of requirements, risks, ambiguities, and device dependencies.
Follows Rule 5: If requirement is ambiguous, do not guess.
"""

import re
from typing import Any, Dict, List, Optional


class RequirementAnalyzer:
    def __init__(self):
        # Keywords indicating device-specific native hardware or OS features
        self.device_indicators = [
            "camera", "hardware", "bluetooth", "location", "gps", "push notification",
            "fcm", "os permission", "sensor", "biometric", "fingerprint", "physical device",
            "deep link native", "android 14", "android 13", "sdk 34",
            "app", "android app", "bikedekho app", "cardekho app", "mobile app"
        ]

    def analyze(self, ticket: Dict[str, Any]) -> Dict[str, Any]:
        """Perform comprehensive requirement, risk, and dependency analysis on a Jira ticket."""
        summary = ticket.get("summary", "")
        description = ticket.get("description", "")
        ac = ticket.get("acceptance_criteria", "")
        labels = [l.lower() for l in ticket.get("labels", [])]
        combined_text = f"{summary} {description} {ac} {' '.join(labels)}".lower()

        # 1. Ambiguity Detection
        ambiguities = self._detect_ambiguities(summary, description, ac)

        # 2. Scope definition
        in_scope = [
            f"Functional validation of '{summary}'",
            "Validation of primary UI element rendering & interactions",
            "Verification of underlying business API status and schema"
        ]
        out_of_scope = [
            "Load testing and stress testing under concurrent user volume",
            "Back-office administrative database schema modifications"
        ]

        # 3. Risk Analysis
        functional_risks = []
        regression_risks = []
        security_risks = []

        if any(w in combined_text for w in ["login", "token", "session", "auth", "password", "otp"]):
            security_risks.append("Session hijacking or invalid token persistence vulnerability")
            functional_risks.append("User session invalidated prematurely or refresh token loop failure")

        if any(w in combined_text for w in ["filter", "search", "slider", "sort", "pagination"]):
            functional_risks.append("State inconsistency when applying and clearing multi-select filters")
            regression_risks.append("Search result pagination and model overview deep link breakage")

        if any(w in combined_text for w in ["price", "offer", "discount", "emi", "quote"]):
            functional_risks.append("Numerical or currency formatting truncation across responsive layouts")
            regression_risks.append("Lead generation payload calculation distortion")

        if not functional_risks:
            functional_risks.append("UI state regression or unhandled null response")
        if not regression_risks:
            regression_risks.append("Impact on adjacent navigation and layout rendering")

        # 4. Dependency Identification
        screens = self._extract_dependencies(combined_text)
        apis = self._extract_apis(combined_text)

        # 5. Brand Identification (Master Prompt Section 7)
        brand, brand_certain = self.identify_brand(ticket)

        # 6. Jira Testing Mode Classification (Master Prompt Section 8)
        jira_mode = self.classify_jira_type(ticket)

        # 7. Device Requirement Detection (Rule 7)
        device_required = False
        device_reason = "Standard Web/PWA or API automation is sufficient. No native OS/hardware dependencies found."
        matched_indicators = [ind for ind in self.device_indicators if ind in combined_text]
        if matched_indicators or (brand in ["BIKEDEKHO", "CARDEKHO"] and ("app" in combined_text or ticket.get("project_key") in ["MB2C", "CD", "BD"])):
            device_required = True
            device_reason = f"Physical Android device required due to native app dependencies: {', '.join(matched_indicators) if matched_indicators else 'Android App QA'}."

        clarification_required = len(ambiguities) > 0 or not brand_certain

        return {
            "ticket_key": ticket.get("key"),
            "brand": brand,
            "brand_certain": brand_certain,
            "jira_mode": jira_mode,
            "clarification_required": clarification_required,
            "ambiguities": ambiguities,
            "scope": {
                "in_scope": in_scope,
                "out_of_scope": out_of_scope
            },
            "risks": {
                "functional_risks": functional_risks,
                "regression_risks": regression_risks,
                "security_risks": security_risks,
                "destructive_actions": self._check_destructive_actions(combined_text)
            },
            "dependencies": {
                "screens": screens,
                "apis": apis,
                "linked_tickets": [link.get("key") for link in ticket.get("linked_issues", [])]
            },
            "device_requirement": {
                "device_required": device_required,
                "reason": device_reason
            }
        }

    def identify_brand(self, ticket: Dict[str, Any]) -> Tuple[str, bool]:
        """
        Deterministically identifies whether Jira belongs to CARDEKHO or BIKEDEKHO (Master Prompt Section 7).
        Returns (brand_name, is_certain). If uncertain, returns ("UNKNOWN", False).
        """
        key = (ticket.get("key") or "").upper()
        summary = (ticket.get("summary") or "").lower()
        desc = (ticket.get("description") or "").lower()
        labels = [l.lower() for l in ticket.get("labels", [])]
        combined = f"{summary} {desc} {' '.join(labels)}"

        # 1. Clear project prefix mappings
        if key.startswith("BDCV") or key.startswith("BD-") or key.startswith("BIKE"):
            return "BIKEDEKHO", True
        if key.startswith("DB2C") or key.startswith("CD-") or key.startswith("CAR"):
            return "CARDEKHO", True

        # 2. MB2C or generic projects: analyze content keywords
        is_bike = any(w in combined for w in ["bikedekho", "bd app", "[bd app]", "bike", "scooter", "motorcycle", "two-wheeler", "hero", "yamaha", "splendor", "royalenfield"])
        is_car = any(w in combined for w in ["cardekho", "cd app", "[cd app]", "car", "four-wheeler", "sedan", "suv", "hyundai", "creta", "maruti", "tata"])

        if is_bike and not is_car:
            return "BIKEDEKHO", True
        if is_car and not is_bike:
            return "CARDEKHO", True

        # Fallback check summary tag e.g. [BD APP] or [CD APP]
        if "[bd app]" in summary or "bikedekho" in summary:
            return "BIKEDEKHO", True
        if "[cd app]" in summary or "cardekho" in summary:
            return "CARDEKHO", True

        # If indeterminate, prompt user (Section 7)
        return "UNKNOWN", False

    def classify_jira_type(self, ticket: Dict[str, Any]) -> str:
        """
        Classifies Jira testing mode (Master Prompt Section 8):
        PROD BUG, TESTING BUG, TASK, FEATURE, ENHANCEMENT, OTHER.
        """
        issue_type = (ticket.get("issue_type") or "").strip().lower()
        summary = (ticket.get("summary") or "").lower()
        labels = [l.lower() for l in ticket.get("labels", [])]
        combined = f"{issue_type} {summary} {' '.join(labels)}"

        if "prod bug" in combined or "production bug" in combined or "live bug" in combined or "prod" in labels:
            return "PROD BUG"
        if "testing bug" in combined or "qa bug" in combined or "staging bug" in combined:
            return "TESTING BUG"
        if "bug" in issue_type or "defect" in issue_type:
            # Check if mentions production environment in description
            desc = (ticket.get("description") or "").lower()
            if "live" in desc or "production" in desc or "prod" in desc:
                return "PROD BUG"
            return "TESTING BUG"
        if "enhancement" in issue_type or "improvement" in issue_type:
            return "ENHANCEMENT"
        if "feature" in issue_type or "story" in issue_type:
            return "FEATURE"
        if "task" in issue_type or "sub-task" in issue_type:
            return "TASK"
        return "OTHER"

    def assess_deployment_requirement(self, ticket: Dict[str, Any], branch_info: Dict[str, Any]) -> Dict[str, Any]:
        """
        Assesses whether API/PWA deployment is strictly required (Master Prompt Section 9).
        Do NOT deploy if it's pure requirement analysis or already deployed.
        """
        has_branch = branch_info.get("has_branch", False)
        branch_type = branch_info.get("branch_type", "")
        primary_branch = branch_info.get("primary_branch", "")

        if not has_branch or not primary_branch:
            return {
                "deployment_required": False,
                "reason": "No API or PWA git branch detected in Jira ticket."
            }

        # If branch is specifically API or PWA, server deployment is required
        if branch_type in ["API", "PWA"]:
            return {
                "deployment_required": True,
                "reason": f"Detected {branch_type} branch '{primary_branch}' affecting backend/PWA runtime services."
            }

        return {
            "deployment_required": True,
            "reason": f"Git branch '{primary_branch}' detected for requirement."
        }

    def _detect_ambiguities(self, summary: str, description: str, ac: str) -> List[str]:
        ambiguities = []
        if len(description.strip()) < 15:
            ambiguities.append("Ticket description is excessively brief and lacks concrete context.")
        if not ac or len(ac.strip()) < 5:
            ambiguities.append("Acceptance Criteria (AC) is missing or underspecified in ticket.")
        if "?" in description or "tbd" in description.lower() or "to be decided" in description.lower():
            ambiguities.append("Ticket contains unresolved questions or TBD markers.")
        return ambiguities

    def _extract_dependencies(self, text: str) -> List[str]:
        screens = []
        screen_map = {
            "home": "Home Screen",
            "search": "Search & Filter Listing",
            "overview": "Model Overview Screen",
            "variant": "Variant & Price Screen",
            "compare": "Compare Details Screen",
            "review": "User Reviews Widget",
            "news": "News Details Screen",
            "service": "Service Cost Calculator"
        }
        for kw, name in screen_map.items():
            if kw in text:
                screens.append(name)
        return screens or ["Main Application Screen"]

    def _extract_apis(self, text: str) -> List[str]:
        apis = []
        api_map = {
            "search": "/api/v1/search/filter",
            "model": "/api/v1/model/details",
            "compare": "/api/v1/compare/specs",
            "review": "/api/v1/reviews/list",
            "price": "/api/v1/pricing/quote",
            "auth": "/api/v1/user/session"
        }
        for kw, endpoint in api_map.items():
            if kw in text:
                apis.append(endpoint)
        return apis or ["/api/v1/health"]

    def _check_destructive_actions(self, text: str) -> bool:
        destructive_kws = ["delete", "drop", "reset all", "purge", "format data", "wipe"]
        return any(k in text for k in destructive_kws)
