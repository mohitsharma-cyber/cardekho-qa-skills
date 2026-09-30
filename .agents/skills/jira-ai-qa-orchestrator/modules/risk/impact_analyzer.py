"""
Impact Analyzer for CarDekho & BikeDekho Jira Tasks.
Performs deterministic impact analysis across screens, modules, APIs, and platforms
without inventing missing requirements.
"""

import re
from typing import Dict, Any, List, Optional, Set, Tuple

ATTACK_VECTORS = {
    "INPUT_BOUNDARIES": {
        "description": "Boundary and limit values, empty inputs, unicode/emojis, max length, invalid formats, SQL/XSS tokens, decimal precision",
        "default_priority": "P1"
    },
    "RAPID_ACTIONS_DEBOUNCE": {
        "description": "Rapid double-taps on CTAs, rapid tab switching, debounce failure on search/inputs, race conditions",
        "default_priority": "P1"
    },
    "STATE_LIFECYCLE": {
        "description": "App background/foreground restoration, screen rotation, back/forward cache state, memory reclamation, session retention",
        "default_priority": "P1"
    },
    "DATA_PAYLOAD_ANOMALIES": {
        "description": "Null/missing JSON fields, unescaped HTML tags (<p>, <b>), malformed data types, zero/negative pricing, empty arrays",
        "default_priority": "P0"
    },
    "API_FAILURE_SIMULATION": {
        "description": "4xx client errors, 5xx server errors, timeout >10s, offline/airplane mode, retry degradation without crashes",
        "default_priority": "P1"
    },
    "PLATFORM_PARITY": {
        "description": "Consistency across Android App vs WAP vs Web in layout, copy, price calculations, and feature availability",
        "default_priority": "P2"
    },
    "DEVICE_SYSTEM_INTERRUPTS": {
        "description": "Keyboard occlusion of CTAs, permissions denial, system alert overlays, low battery dialogs",
        "default_priority": "P2"
    }
}


SCREEN_KEYWORDS = {
    "home": ["home", "homepage", "landing", "main screen", "dashboard"],
    "search": ["search", "auto-suggest", "autosuggest", "query", "filter", "sort"],
    "model_details": ["model page", "model details", "car details", "bike details", "overview tab"],
    "variant_details": ["variant", "variant page", "variant details", "specifications", "specs tab"],
    "price_tab": ["price", "on road price", "orp", "price tab", "price breakdown", "ex-showroom"],
    "lead_form": ["lead", "lead form", "lead popup", "test drive", "booking", "dealer offer", "cta", "contact dealer"],
    "change_url": ["change url", "server switcher", "base url", "base api url", "server configuration"],
    "drawer": ["drawer", "hamburger", "side menu", "navigation menu"],
    "reviews": ["review", "user review", "expert review", "rating"],
    "emi_calculator": ["emi", "calculator", "loan", "down payment", "interest"]
}

MODULE_MAPPING = {
    "auth": ["login", "signup", "sign up", "sign in", "otp", "authentication", "session", "token", "profile"],
    "lead_flow": ["lead", "lead form", "test drive", "booking", "dealer", "seller inquiry", "submit lead"],
    "payment": ["payment", "gateway", "razorpay", "paytm", "transaction", "checkout"],
    "pricing_engine": ["price", "orp", "on-road", "on road", "ex-showroom", "rto", "insurance", "tcs"],
    "search_engine": ["search", "filter", "sort", "autosuggest", "brand filter", "budget filter"],
    "model_page": ["model page", "overview", "gallery", "360 view", "color selector"],
    "variant_page": ["variant", "specifications", "features", "comparison", "compare"],
    "navigation_drawer": ["drawer", "hamburger", "navigation", "deep link", "deeplink"],
    "settings_env": ["change url", "base url", "environment", "staging", "testingpwa"],
    "ui_cosmetics": ["color", "font", "padding", "margin", "typography", "spacing", "alignment", "icon", "banner", "text copy", "typo"]
}

API_PATTERNS = [
    r"/api/[a-zA-Z0-9_\-\./]+",
    r"https?://[a-zA-Z0-9_\-\.]+/api/[a-zA-Z0-9_\-\./]+",
    r"v[1-9]/[a-zA-Z0-9_\-\./]+"
]

class ImpactAnalyzer:
    """Analyzes Jira ticket context to map architectural and functional blast radius."""

    def __init__(self):
        pass

    def analyze_ticket(
        self,
        summary: str,
        description: str = "",
        labels: Optional[List[str]] = None,
        components: Optional[List[str]] = None,
        linked_issues: Optional[List[Dict[str, Any]]] = None
    ) -> Dict[str, Any]:
        """
        Analyzes the ticket to extract affected screens, modules, APIs, and cross-module implications.
        """
        full_text = f"{summary or ''}\n{description or ''}"
        labels = labels or []
        components = components or []
        linked_issues = linked_issues or []

        text_lower = full_text.lower()

        # 1. Detect Affected Screens
        affected_screens = self._detect_screens(text_lower)

        # 2. Detect Affected Modules
        affected_modules = self._detect_modules(text_lower, components)

        # 3. Detect API Dependencies
        api_dependencies = self._extract_apis(full_text)

        # 4. Detect Specific Blast Flags
        is_crash_fix = any(w in text_lower for w in ["crash", "fatal", "anr", "nullpointer", "exception", "force close"])
        is_lead_impact = "lead_flow" in affected_modules
        is_auth_impact = "auth" in affected_modules
        
        # UI-only check: has UI cosmetic keywords but NO backend/API/lead/crash/pricing logic
        has_ui_cosmetic = "ui_cosmetics" in affected_modules
        has_heavy_logic = is_crash_fix or is_lead_impact or is_auth_impact or ("pricing_engine" in affected_modules) or bool(api_dependencies)
        is_ui_only = has_ui_cosmetic and not has_heavy_logic and len(affected_modules) == 1

        # 5. Cross-Module Impact
        cross_module_impact, secondary_impacts = self._evaluate_cross_module(affected_modules, affected_screens)

        # 6. Extract Reference Jira Information
        ref_jira_keys = self._extract_jira_references(full_text, linked_issues)

        # 7. Platforms
        platforms = self._detect_platforms(text_lower, labels, components)

        # 8. Identify Attack Surface
        impact_summary = {
            "summary": summary,
            "description": description,
            "affected_screens": sorted(list(affected_screens)),
            "affected_modules": sorted(list(affected_modules)),
            "api_dependencies": sorted(list(api_dependencies)),
            "is_crash_fix": is_crash_fix,
            "is_lead_impact": is_lead_impact,
            "is_auth_impact": is_auth_impact,
            "is_ui_only": is_ui_only,
            "platforms": platforms
        }
        attack_surface = self.identify_attack_surface(impact_summary)

        return {
            "summary": summary,
            "affected_screens": sorted(list(affected_screens)),
            "affected_modules": sorted(list(affected_modules)),
            "api_dependencies": sorted(list(api_dependencies)),
            "cross_module_impact": cross_module_impact,
            "secondary_impacts": sorted(list(secondary_impacts)),
            "is_crash_fix": is_crash_fix,
            "is_lead_impact": is_lead_impact,
            "is_auth_impact": is_auth_impact,
            "is_ui_only": is_ui_only,
            "reference_jira_keys": ref_jira_keys,
            "platforms": platforms,
            "attack_surface": attack_surface
        }

    def _detect_screens(self, text: str) -> Set[str]:
        screens = set()
        for screen, keywords in SCREEN_KEYWORDS.items():
            for kw in keywords:
                if kw in text:
                    screens.add(screen)
                    break
        if not screens:
            screens.add("home")  # default fallback entrypoint
        return screens

    def _detect_modules(self, text: str, components: List[str]) -> Set[str]:
        modules = set()
        for comp in components:
            comp_lower = comp.lower()
            for mod, keywords in MODULE_MAPPING.items():
                if any(kw in comp_lower for kw in keywords):
                    modules.add(mod)

        for mod, keywords in MODULE_MAPPING.items():
            for kw in keywords:
                if kw in text:
                    modules.add(mod)
                    break

        if not modules:
            modules.add("ui_cosmetics")
        return modules

    def _extract_apis(self, text: str) -> Set[str]:
        apis = set()
        for pattern in API_PATTERNS:
            matches = re.findall(pattern, text)
            for m in matches:
                apis.add(m)
        return apis

    def _evaluate_cross_module(self, modules: Set[str], screens: Set[str]) -> Tuple[bool, Set[str]]:
        secondary = set()
        # Authentication affects user-specific flows
        if "auth" in modules:
            secondary.update(["lead_form", "reviews", "shortlist"])
        # Pricing changes affect Model, Variant, and Lead CTA
        if "pricing_engine" in modules:
            secondary.update(["model_details", "variant_details", "lead_form"])
        # Search engine changes affect suggestions and landing pages
        if "search_engine" in modules:
            secondary.update(["home", "model_details"])
        # Environment settings affect all backend API calls
        if "settings_env" in modules:
            secondary.update(["api_connectivity", "auth"])

        # Filter out primary affected screens to keep only secondary blast radius
        secondary = secondary.difference(screens)
        cross_module = len(modules) > 1 or bool(secondary)
        return cross_module, secondary

    def _extract_jira_references(self, text: str, linked_issues: List[Dict[str, Any]]) -> List[str]:
        keys = set()
        # From linked issues structure
        for issue in linked_issues:
            key = issue.get("key") or issue.get("id")
            if key:
                keys.add(str(key))

        # Regex scan in description / text
        jira_pattern = r"\b([A-Z]{2,10}-[0-9]+)\b"
        found = re.findall(jira_pattern, text)
        for k in found:
            keys.add(k)

        return sorted(list(keys))

    def _detect_platforms(self, text: str, labels: List[str], components: List[str]) -> List[str]:
        platforms = set()
        combined = (text + " " + " ".join(labels) + " " + " ".join(components)).lower()

        if any(w in combined for w in ["android", "apk", "mobile app", "app"]):
            platforms.add("Android App")
        if any(w in combined for w in ["wap", "mweb", "mobile web"]):
            platforms.add("WAP")
        if any(w in combined for w in ["web", "desktop", "pwa", "browser"]) and "wap" not in combined:
            platforms.add("Web")
        if any(w in combined for w in ["api", "backend", "endpoint", "service"]):
            platforms.add("API")

        if not platforms:
            platforms.add("Android App")  # Skill default target
        return sorted(list(platforms))

    def identify_attack_surface(self, impact: Dict[str, Any]) -> Dict[str, Any]:
        """
        Derives targeted attack surface vectors for bug-hunting exploration.
        Motto: 'BREAK THE FEATURE BEFORE THE USER DOES.'
        """
        full_text = f"{impact.get('summary', '')}\n{impact.get('description', '')}".lower()
        modules = set(impact.get("affected_modules", []))
        screens = set(impact.get("affected_screens", []))
        apis = impact.get("api_dependencies", [])
        is_lead = impact.get("is_lead_impact", False)
        is_auth = impact.get("is_auth_impact", False)
        is_crash = impact.get("is_crash_fix", False)
        platforms = impact.get("platforms", [])

        identified_vectors = []
        vector_details = {}

        # 1. INPUT_BOUNDARIES
        input_keywords = ["search", "input", "form", "filter", "query", "otp", "phone", "mobile", "price", "budget", "emi"]
        has_input = any(k in full_text for k in input_keywords) or bool({"auth", "lead_flow", "search_engine", "pricing_engine"}.intersection(modules))
        if has_input:
            identified_vectors.append("INPUT_BOUNDARIES")
            vulnerabilities = [
                "Empty, whitespace-only, and null input strings",
                "Extreme character counts, multi-byte unicode, emojis, and RTL strings",
                "HTML/XSS injection tokens (<script>, alert(), <p>) in text fields",
                "Negative, zero, and boundary numeric amounts (e.g. 0, -1, 999999999)"
            ]
            vector_details["INPUT_BOUNDARIES"] = {
                "applicable": True,
                "priority": "P0" if is_lead or is_auth else "P1",
                "vulnerability_targets": vulnerabilities,
                "recommended_tests": ["Submit form with empty and boundary payload", "Verify field limits and sanitization"]
            }

        # 2. RAPID_ACTIONS_DEBOUNCE
        cta_keywords = ["cta", "button", "click", "submit", "tap", "tab", "filter", "sort", "book", "offer"]
        has_cta = any(k in full_text for k in cta_keywords) or bool({"lead_flow", "auth", "search_engine", "model_page", "variant_page"}.intersection(modules))
        if has_cta:
            identified_vectors.append("RAPID_ACTIONS_DEBOUNCE")
            vulnerabilities = [
                "Rapid double-click on submit/lead/booking CTAs causing duplicate submissions",
                "Rapid tab switching between Model, Variants, and Price tabs causing race conditions or stale render",
                "Rapid filter toggles leading to out-of-order API response overwrite"
            ]
            vector_details["RAPID_ACTIONS_DEBOUNCE"] = {
                "applicable": True,
                "priority": "P0" if is_lead else "P1",
                "vulnerability_targets": vulnerabilities,
                "recommended_tests": ["Rapid double-tap CTA debounce assertion", "Rapid tab cycling state stability"]
            }

        # 3. STATE_LIFECYCLE
        identified_vectors.append("STATE_LIFECYCLE")
        vector_details["STATE_LIFECYCLE"] = {
            "applicable": True,
            "priority": "P1",
            "vulnerability_targets": [
                "State corruption when app is backgrounded and resumed during user interaction",
                "Back navigation from child views causing state loss or unexpected reload",
                "Session retention and cache invalidation on screen transitions"
            ],
            "recommended_tests": ["Background app for 3s, resume, and assert screen state", "Navigate back and assert filter/data preservation"]
        }

        # 4. DATA_PAYLOAD_ANOMALIES
        data_keywords = ["price", "cost", "spec", "variant", "review", "tag", "html", "pwa", "api"]
        has_data = any(k in full_text for k in data_keywords) or bool(apis) or ("pricing_engine" in modules) or ("variant_page" in modules)
        if has_data or is_crash:
            identified_vectors.append("DATA_PAYLOAD_ANOMALIES")
            vulnerabilities = [
                "Unescaped HTML tags (<p>, </p>, <b>, &nbsp;) leaking into UI strings",
                "Null, empty, or missing JSON fields triggering NullPointerException or silent view collapse",
                "Currency calculation rounding errors, missing rupee symbol (₹), or NaN values"
            ]
            vector_details["DATA_PAYLOAD_ANOMALIES"] = {
                "applicable": True,
                "priority": "P0" if is_crash or "pricing_engine" in modules else "P1",
                "vulnerability_targets": vulnerabilities,
                "recommended_tests": ["Inspect rendered UI for raw HTML tag leaks", "Verify response data null safety and currency formatting"]
            }

        # 5. API_FAILURE_SIMULATION
        if bool(apis) or not impact.get("is_ui_only", False):
            identified_vectors.append("API_FAILURE_SIMULATION")
            vector_details["API_FAILURE_SIMULATION"] = {
                "applicable": True,
                "priority": "P1",
                "vulnerability_targets": [
                    "Unhandled 500/502/503 server error rendering blank screen or crashing app",
                    "Network timeout (>10s) remaining in indefinite shimmer without retry CTA",
                    "Offline mode / connection loss during action without user feedback"
                ],
                "recommended_tests": ["Simulate or assert error state fallback and retry CTA", "Verify 10s shimmer timeout threshold"]
            }

        # 6. PLATFORM_PARITY
        if len(platforms) > 1 or any(p in platforms for p in ["WAP", "Web"]):
            identified_vectors.append("PLATFORM_PARITY")
            vector_details["PLATFORM_PARITY"] = {
                "applicable": True,
                "priority": "P2",
                "vulnerability_targets": [
                    "Feature parity discrepancy between Android App and WAP/Web",
                    "Discrepant pricing or offer numbers across platforms",
                    "Inconsistent naming, label hierarchy, or button positioning"
                ],
                "recommended_tests": ["Cross-verify App vs WAP layout and values", "Validate uniform business logic across endpoints"]
            }

        # 7. DEVICE_SYSTEM_INTERRUPTS
        if "Android App" in platforms:
            identified_vectors.append("DEVICE_SYSTEM_INTERRUPTS")
            vector_details["DEVICE_SYSTEM_INTERRUPTS"] = {
                "applicable": True,
                "priority": "P2",
                "vulnerability_targets": [
                    "Soft keyboard occluding bottom action CTA or Next button",
                    "System dialog / overlay interrupting ongoing user flow",
                    "Permission denial causing unhandled crash"
                ],
                "recommended_tests": ["Verify keyboard dismisses cleanly on tap/back", "Verify runtime permissions auto-grant without crash"]
            }

        # Prioritize primary threat vector
        primary_vector = identified_vectors[0] if identified_vectors else "STATE_LIFECYCLE"
        if "DATA_PAYLOAD_ANOMALIES" in identified_vectors and (is_crash or "<p>" in full_text or "tag" in full_text):
            primary_vector = "DATA_PAYLOAD_ANOMALIES"
        elif "RAPID_ACTIONS_DEBOUNCE" in identified_vectors and is_lead:
            primary_vector = "RAPID_ACTIONS_DEBOUNCE"
        elif "INPUT_BOUNDARIES" in identified_vectors and (is_auth or "search" in full_text):
            primary_vector = "INPUT_BOUNDARIES"

        # 12 Intelligent Pre-Execution Attack Questions (Bug-Hunting Engine)
        twelve_attack_dimensions = self.analyze_attack_dimensions(impact)

        return {
            "identified_vectors": identified_vectors,
            "vector_details": vector_details,
            "total_vectors_identified": len(identified_vectors),
            "primary_threat_vector": primary_vector,
            "bug_hunting_motto": "BREAK THE FEATURE BEFORE THE USER DOES.",
            "attack_dimensions": twelve_attack_dimensions
        }

    def analyze_attack_dimensions(self, impact: Dict[str, Any]) -> Dict[str, Any]:
        """
        Intelligently analyzes the 12 bug-hunting risk questions before execution:
        1. What can break?
        2. What can crash?
        3. What can show incorrect data?
        4. What happens with invalid/missing/null data?
        5. What happens at boundaries?
        6. What happens after repeated/rapid actions?
        7. What happens during loading/empty/error states?
        8. What happens after back/refresh/relaunch?
        9. Can UI and API become inconsistent?
        10. Can App and WAP behave differently?
        11. What related regression areas can be affected?
        12. Are there historical defects indicating similar risks?
        """
        full_text = f"{impact.get('summary', '')}\n{impact.get('description', '')}".lower()
        modules = set(impact.get("affected_modules", []))
        screens = set(impact.get("affected_screens", []))
        apis = impact.get("api_dependencies", [])
        platforms = impact.get("platforms", [])
        is_crash = impact.get("is_crash_fix", False)
        is_lead = impact.get("is_lead_impact", False)
        is_auth = impact.get("is_auth_impact", False)

        # 1. What can break?
        break_risks = []
        if is_lead or "lead_flow" in modules:
            break_risks.append("Lead form submission pipeline, OTP trigger, dealer assignment flow")
        if "pricing_engine" in modules or "price" in full_text:
            break_risks.append("On-road price calculation accordion, EMI modal, breakdown line items")
        if "variant_page" in modules or "spec" in full_text:
            break_risks.append("Variant switcher tabs, comparison matrix cells, spec table collapse")
        if not break_risks:
            break_risks.append(f"Primary interaction flow and element rendering on {', '.join(screens) if screens else 'target screen'}")

        # 2. What can crash?
        crash_risks = []
        if is_crash or "crash" in full_text or "fatal" in full_text or "nullpointer" in full_text:
            crash_risks.append("NullPointerException on unhandled null object fields in backend payload")
        if bool(apis):
            crash_risks.append("Malformed JSON response parsing or unexpected HTTP 500 payload crash")
        if "Android App" in platforms:
            crash_risks.append("Unhandled activity lifecycle kill on background memory reclaim or runtime permission revoke")
        if not crash_risks:
            crash_risks.append("Array index out of bounds or missing key dereference during view binding")

        # 3. What can show incorrect data?
        incorrect_data_risks = []
        if "<p>" in full_text or "html" in full_text or "tag" in full_text:
            incorrect_data_risks.append("Raw unescaped HTML tags (<p>, </p>, <b>, &nbsp;) rendered visibly in UI")
        if "price" in full_text or "pricing_engine" in modules or "cost" in full_text:
            incorrect_data_risks.append("Mismatched ex-showroom/RTO calculation, missing rupee symbol (₹), or NaN pricing")
        if "variant" in full_text or "spec" in full_text:
            incorrect_data_risks.append("Stale variant attributes or specs leaking between consecutive variant tab selections")
        if not incorrect_data_risks:
            incorrect_data_risks.append("Stale cached data or inaccurate label copy across state changes")

        # 4. What happens with invalid/missing/null data?
        null_data_risks = [
            "Missing optional JSON fields causing silent UI section collapse or blank white cards",
            "Null numeric values rendering as 'null', 'undefined', or 'NaN'",
            "Empty string inputs bypassing validation or producing malformed API payloads"
        ]

        # 5. What happens at boundaries?
        boundary_risks = [
            "Numeric boundary values: 0, negative values (-1), extreme large amounts (e.g. ₹99,99,99,999)",
            "Text field limits: 0 chars, 1 char, maximum character limit overflows, multi-byte emojis, and RTL text",
            "Filter boundaries: all filters deselected, extreme budget slider positions, min/max count pagination"
        ]

        # 6. What happens after repeated/rapid actions?
        rapid_action_risks = [
            "Rapid double-click on primary CTA causing duplicate API submissions or duplicate leads",
            "High-frequency tab switching causing race condition state overwrites or out-of-order response rendering",
            "Rapid toggle on accordion/filters freezing UI thread or triggering ANR"
        ]

        # 7. What happens during loading/empty/error states?
        state_risks = [
            "Shimmer loading state exceeding 10s threshold without timing out",
            "Empty API array rendering blank unresponsive container without friendly zero-state illustration",
            "HTTP 4xx/5xx network failure without functional retry CTA"
        ]

        # 8. What happens after back/refresh/relaunch?
        lifecycle_risks = [
            "Android back navigation dropping user selections, entered form data, or active tab state",
            "App backgrounding (HOME key) for 3s and foreground restore corrupting resumed view state",
            "Hard back/refresh loop trapping user on child screen"
        ]

        # 9. Can UI and API become inconsistent?
        ui_api_desync_risks = [
            "Optimistic UI update showing success when network request times out or returns error",
            "Discrepancy between API payload values and formatted UI text on screen",
            "Out-of-sync status flags between client cache and server response"
        ]

        # 10. Can App and WAP behave differently?
        parity_risks = []
        if len(platforms) > 1 or any(p in platforms for p in ["WAP", "Web"]):
            parity_risks.append("Feature disparity: feature available on WAP but missing/unimplemented in Native App (or vice-versa)")
            parity_risks.append("Calculation differences: differing RTO or insurance calculation logic between App API and WAP")
            parity_risks.append("UI layout disparity: CTA positioning, button labels, or accordion hierarchy mismatch")
        else:
            parity_risks.append("Single platform scope; ensure native touch interactions match platform conventions")

        # 11. What related regression areas can be affected?
        regression_risks = []
        if "pricing_engine" in modules:
            regression_risks.extend(["Model Details Overview", "Variant Spec Table", "Lead Booking Modal"])
        if "lead_flow" in modules:
            regression_risks.extend(["Dealer Offer Banners", "Test Drive Booking", "User Profile / Lead History"])
        if "search_engine" in modules:
            regression_risks.extend(["Homepage Autosuggest", "Model Search Results", "Filter Chips"])
        if not regression_risks:
            regression_risks.extend(["Adjacent navigation drawer", "Global search bar", "Recent views history"])

        # 12. Are there historical defects indicating similar risks?
        historical_risks = []
        ref_keys = impact.get("reference_jira_keys", [])
        if ref_keys:
            historical_risks.append(f"Linked reference tickets ({', '.join(ref_keys)}) indicate recurring defect patterns")
        if is_crash:
            historical_risks.append("Past crash history detected in module; risk of regression on edge-case data")
        if "pricing_engine" in modules or "price" in full_text:
            historical_risks.append("Known historical regressions in price formatting and accordion expansion latency")
        if not historical_risks:
            historical_risks.append("Standard historical module stability baseline applied")

        return {
            "what_can_break": break_risks,
            "what_can_crash": crash_risks,
            "what_can_show_incorrect_data": incorrect_data_risks,
            "what_happens_with_invalid_missing_null_data": null_data_risks,
            "what_happens_at_boundaries": boundary_risks,
            "what_happens_after_repeated_rapid_actions": rapid_action_risks,
            "what_happens_during_loading_empty_error_states": state_risks,
            "what_happens_after_back_refresh_relaunch": lifecycle_risks,
            "can_ui_and_api_become_inconsistent": ui_api_desync_risks,
            "can_app_and_wap_behave_differently": parity_risks,
            "what_related_regression_areas_can_be_affected": regression_risks,
            "are_there_historical_defects_indicating_similar_risks": historical_risks,
            "total_dimensions_evaluated": 12
        }
