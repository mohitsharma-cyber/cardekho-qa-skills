"""
Duplicate Defect Detector for Jira AI QA Orchestrator.
Compares proposed bug summaries against known open Jira tickets and cached bugs
to prevent redundant Testing Bug creation.
"""

import re
from typing import Dict, Any, List, Optional
from ..jira.jira_client import JiraClient

class DuplicateDetector:
    """Detects potential duplicate Jira bugs using token overlap and similarity heuristics."""

    def __init__(self, jira_client: Optional[JiraClient] = None):
        self.jira_client = jira_client or JiraClient()

    def check_duplicate(
        self,
        summary: str,
        parent_ticket_key: Optional[str] = None,
        existing_bugs: Optional[List[Dict[str, Any]]] = None
    ) -> Dict[str, Any]:
        """
        Checks if a similar defect is already logged in Jira or active cache.
        Returns match status, duplicate candidates, and similarity confidence.
        """
        clean_target = self._normalize(summary)
        duplicates = []

        # 1. Check existing in-memory/passed bug list
        if existing_bugs:
            for bug in existing_bugs:
                cand_summary = bug.get("summary") or bug.get("title") or ""
                sim = self._calculate_similarity(clean_target, self._normalize(cand_summary))
                if sim >= 0.70:
                    duplicates.append({
                        "key": bug.get("key") or bug.get("ticket_key", "UNKNOWN"),
                        "summary": cand_summary,
                        "similarity_score": round(sim, 2),
                        "source": "local_cache"
                    })

        # 2. Check via JiraClient if available
        if self.jira_client and parent_ticket_key:
            try:
                jira_matches = self.jira_client.check_duplicate_bugs(summary, parent_ticket_key=parent_ticket_key)
                for jm in jira_matches:
                    duplicates.append({
                        "key": jm.get("key"),
                        "summary": jm.get("summary"),
                        "similarity_score": jm.get("similarity", 0.85),
                        "source": "jira_query"
                    })
            except Exception:
                pass

        has_duplicate = len(duplicates) > 0
        return {
            "has_duplicate": has_duplicate,
            "is_duplicate": has_duplicate,
            "duplicate_count": len(duplicates),
            "duplicates": duplicates,
            "recommendation": "Review potential duplicate before creating new Testing Bug" if has_duplicate else "No duplicate defect detected"
        }

    def _normalize(self, text: str) -> str:
        words = re.findall(r"\w+", text.lower())
        stopwords = {"a", "an", "the", "in", "on", "at", "for", "to", "of", "and", "is", "when", "with"}
        filtered = [w for w in words if w not in stopwords]
        return " ".join(filtered)

    def _calculate_similarity(self, s1: str, s2: str) -> float:
        set1 = set(s1.split())
        set2 = set(s2.split())
        if not set1 or not set2:
            return 0.0
        intersection = set1.intersection(set2)
        union = set1.union(set2)
        return len(intersection) / len(union)
