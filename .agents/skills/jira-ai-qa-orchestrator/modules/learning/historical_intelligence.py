"""
Historical QA Intelligence for CarDekho & BikeDekho QA Orchestrator.
Tracks across historical test executions:
- Frequently failing modules
- Recurring defects
- Flaky scenarios
- Common API failures
- Regression hotspots
- Environment failures
- Device-specific failures

Applies historical intelligence strictly to optimize test prioritization and triage.
Strict Rule: Never alters actual QA verdicts based on historical probability.
"""

import logging
from typing import Dict, Any, List, Optional
from datetime import datetime
from .memory_manager import MemoryManager

logger = logging.getLogger(__name__)

class HistoricalIntelligence:
    """Aggregates and queries historical QA execution patterns."""

    def __init__(self, memory_manager: Optional[MemoryManager] = None):
        self.memory_manager = memory_manager or MemoryManager()

    def record_run(
        self,
        ticket: str,
        module: str,
        environment: str,
        device: str,
        results: Dict[str, str],  # tc_id -> "PASS"|"FAIL"|"BLOCKED"
        defects: Optional[List[Dict[str, Any]]] = None,
        api_results: Optional[List[Dict[str, Any]]] = None,
        is_environment_failure: bool = False,
        env_error_detail: Optional[str] = None
    ) -> bool:
        """
        Updates persistent historical records from a completed test run.
        """
        records = self.memory_manager.get_historical_records()
        records["total_runs"] = records.get("total_runs", 0) + 1

        mod_clean = module.lower().strip()
        dev_clean = device.strip()
        env_clean = environment.lower().strip()

        # 1. Frequently failing modules
        mod_stats = records["frequently_failing_modules"].setdefault(mod_clean, {
            "total_tests": 0,
            "failed_tests": 0,
            "failure_rate": 0.0
        })
        for tc_id, verdict in results.items():
            mod_stats["total_tests"] += 1
            if verdict.upper() == "FAIL":
                mod_stats["failed_tests"] += 1
        if mod_stats["total_tests"] > 0:
            mod_stats["failure_rate"] = round(mod_stats["failed_tests"] / mod_stats["total_tests"], 3)

        # 2. Recurring defects
        defects = defects or []
        for defect in defects:
            summary = defect.get("summary", "").strip()
            layer = defect.get("probable_layer", "UI").upper()
            found = False
            for d in records["recurring_defects"]:
                if d.get("summary") == summary or (d.get("probable_layer") == layer and defect.get("component") == d.get("component")):
                    d["occurrences"] = d.get("occurrences", 1) + 1
                    d["last_seen"] = datetime.now().isoformat()
                    if ticket not in d.get("tickets", []):
                        d.setdefault("tickets", []).append(ticket)
                    found = True
                    break
            if not found and summary:
                records["recurring_defects"].append({
                    "summary": summary,
                    "probable_layer": layer,
                    "component": defect.get("component", mod_clean),
                    "occurrences": 1,
                    "first_seen": datetime.now().isoformat(),
                    "last_seen": datetime.now().isoformat(),
                    "tickets": [ticket]
                })

        # 3. Common API failures
        api_results = api_results or []
        for api in api_results:
            endpoint = api.get("endpoint", "")
            if not endpoint:
                continue
            api_stat = records["common_api_failures"].setdefault(endpoint, {
                "total_calls": 0,
                "failed_calls": 0,
                "failure_rate": 0.0,
                "last_status": 200
            })
            api_stat["total_calls"] += 1
            status = api.get("status", 200)
            api_stat["last_status"] = status
            if status >= 400 or api.get("validation_result") == "FAIL":
                api_stat["failed_calls"] += 1
            api_stat["failure_rate"] = round(api_stat["failed_calls"] / api_stat["total_calls"], 3)

        # 4. Regression hotspots (any failed collateral tests)
        for tc_id, verdict in results.items():
            if tc_id.startswith("REG-") and verdict.upper() == "FAIL":
                hotspot = records["regression_hotspots"].setdefault(mod_clean, 0)
                records["regression_hotspots"][mod_clean] = hotspot + 1

        # 5. Environment failures
        if is_environment_failure:
            env_stat = records["environment_failures"].setdefault(env_clean, {
                "failure_count": 0,
                "recent_errors": []
            })
            env_stat["failure_count"] += 1
            if env_error_detail:
                env_stat["recent_errors"].append({
                    "timestamp": datetime.now().isoformat(),
                    "ticket": ticket,
                    "error": env_error_detail
                })
                if len(env_stat["recent_errors"]) > 10:
                    env_stat["recent_errors"] = env_stat["recent_errors"][-10:]

        # 6. Device-specific failures
        failed_count = sum(1 for v in results.values() if v.upper() == "FAIL")
        if failed_count > 0:
            dev_stat = records["device_specific_failures"].setdefault(dev_clean, {
                "failure_count": 0,
                "failed_tickets": []
            })
            dev_stat["failure_count"] += failed_count
            if ticket not in dev_stat["failed_tickets"]:
                dev_stat["failed_tickets"].append(ticket)

        return self.memory_manager.save_historical_records(records)

    # --------------------------------------------------------------------------
    # Historical Queries
    # --------------------------------------------------------------------------

    def get_top_failing_modules(self, top_n: int = 5) -> List[Dict[str, Any]]:
        """Returns modules with highest failure rates, sorted descending."""
        records = self.memory_manager.get_historical_records()
        mods = records.get("frequently_failing_modules", {})
        ranked = []
        for name, stats in mods.items():
            if stats.get("total_tests", 0) >= 2:
                ranked.append({"module": name, **stats})
        ranked.sort(key=lambda x: (x.get("failure_rate", 0.0), x.get("failed_tests", 0)), reverse=True)
        return ranked[:top_n]

    def get_recurring_defects(self, min_occurrences: int = 2) -> List[Dict[str, Any]]:
        """Returns defects that have been detected repeatedly."""
        records = self.memory_manager.get_historical_records()
        defects = records.get("recurring_defects", [])
        return [d for d in defects if d.get("occurrences", 1) >= min_occurrences]

    def get_common_api_failures(self, min_failures: int = 1) -> List[Dict[str, Any]]:
        """Returns API endpoints with documented failures."""
        records = self.memory_manager.get_historical_records()
        apis = records.get("common_api_failures", {})
        res = []
        for endpoint, stat in apis.items():
            if stat.get("failed_calls", 0) >= min_failures:
                res.append({"endpoint": endpoint, **stat})
        res.sort(key=lambda x: x.get("failure_rate", 0.0), reverse=True)
        return res

    def get_regression_hotspots(self) -> List[Dict[str, Any]]:
        """Returns areas where regression collateral most frequently fails."""
        records = self.memory_manager.get_historical_records()
        hotspots = records.get("regression_hotspots", {})
        ranked = [{"area": k, "failure_count": v} for k, v in hotspots.items()]
        ranked.sort(key=lambda x: x["failure_count"], reverse=True)
        return ranked

    # --------------------------------------------------------------------------
    # Intelligent Test Prioritization (Safe: Reorders execution, never fakes verdict)
    # --------------------------------------------------------------------------

    def prioritize_scenarios(
        self,
        scenarios: List[Dict[str, Any]],
        primary_module: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Reorders test scenarios based on historical risk:
        - High-failure modules and regression hotspots run earlier for fast feedback.
        Strict Rule: Does NOT alter or infer verdicts; strictly adjusts execution order.
        """
        top_failing = {m["module"] for m in self.get_top_failing_modules()}
        hotspots = {h["area"] for h in self.get_regression_hotspots()}
        api_fails = {a["endpoint"] for a in self.get_common_api_failures()}

        def calculate_score(s: Dict[str, Any]) -> int:
            score = 0
            title = s.get("title", "").lower()
            target = s.get("target_area", "").lower()
            endpoint = s.get("endpoint", "")

            # Highest priority: primary module
            if primary_module and primary_module.lower() in target:
                score += 10

            # Historical failure prone
            if target in top_failing or any(tf in title for tf in top_failing):
                score += 5

            # Regression hotspot
            if target in hotspots:
                score += 4

            # Common API failure
            if endpoint in api_fails:
                score += 3

            # Regression scenarios prioritized over cosmetic UI
            if s.get("id", "").startswith("REG-"):
                score += 2

            return score

        # Stable sort preserving original relative order for ties
        prioritized = sorted(scenarios, key=calculate_score, reverse=True)
        return prioritized
