"""
Memory Manager for CarDekho & BikeDekho QA Orchestrator.
Enforces strict separation between:
1. `knowledge/`: Persistent, validated, long-term intelligence (immutable during standard runs).
2. `runtime/`: Ephemeral execution state, active session buffers, candidate learnings.

Guarantees that runtime state never directly mutates permanent learned memory
without passing through the controlled learning validation pipeline.
"""

import os
import json
import logging
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)

class MemoryManager:
    """Manages isolated persistent knowledge and ephemeral runtime state."""

    def __init__(
        self,
        knowledge_dir: Optional[str] = None,
        runtime_dir: Optional[str] = None
    ):
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        self.knowledge_dir = knowledge_dir or os.path.join(base_dir, "knowledge")
        self.runtime_dir = runtime_dir or os.path.join(base_dir, "runtime")

        # Persistent knowledge paths
        self.persistent_memory_path = os.path.join(self.knowledge_dir, "learned_memory.json")
        self.historical_records_path = os.path.join(self.knowledge_dir, "historical_records.json")

        # Runtime ephemeral paths
        self.active_session_path = os.path.join(self.runtime_dir, "active_session.json")
        self.candidate_learnings_path = os.path.join(self.runtime_dir, "candidate_learnings.json")
        self.test_run_history_path = os.path.join(self.runtime_dir, "test_run_history.json")

        self._ensure_directories()

    def _ensure_directories(self):
        """Ensures knowledge and runtime directories exist."""
        os.makedirs(self.knowledge_dir, exist_ok=True)
        os.makedirs(self.runtime_dir, exist_ok=True)

    # --------------------------------------------------------------------------
    # Persistent Knowledge (Validated & Long-Term)
    # --------------------------------------------------------------------------

    def get_persistent_knowledge(self) -> Dict[str, Any]:
        """Loads validated persistent memory from knowledge/learned_memory.json."""
        if not os.path.exists(self.persistent_memory_path):
            return {}
        try:
            with open(self.persistent_memory_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Failed to read persistent knowledge: {e}")
            return {}

    def save_persistent_knowledge(self, data: Dict[str, Any]) -> bool:
        """
        Atomically saves validated persistent knowledge to knowledge/learned_memory.json.
        Must only be invoked by ControlledLearner after confidence threshold/approval.
        """
        try:
            temp_path = self.persistent_memory_path + ".tmp"
            with open(temp_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            os.replace(temp_path, self.persistent_memory_path)
            return True
        except Exception as e:
            logger.error(f"Failed to save persistent knowledge: {e}")
            return False

    def get_historical_records(self) -> Dict[str, Any]:
        """Loads historical aggregated QA records from knowledge/historical_records.json."""
        if not os.path.exists(self.historical_records_path):
            return {
                "frequently_failing_modules": {},
                "recurring_defects": [],
                "flaky_scenarios": {},
                "common_api_failures": {},
                "regression_hotspots": {},
                "environment_failures": {},
                "device_specific_failures": {},
                "total_runs": 0
            }
        try:
            with open(self.historical_records_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Failed to read historical records: {e}")
            return {}

    def save_historical_records(self, data: Dict[str, Any]) -> bool:
        """Saves validated historical records to knowledge/historical_records.json."""
        try:
            temp_path = self.historical_records_path + ".tmp"
            with open(temp_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            os.replace(temp_path, self.historical_records_path)
            return True
        except Exception as e:
            logger.error(f"Failed to save historical records: {e}")
            return False

    # --------------------------------------------------------------------------
    # Ephemeral Runtime State (Execution-Only)
    # --------------------------------------------------------------------------

    def get_runtime_state(self) -> Dict[str, Any]:
        """Loads active execution session state from runtime/active_session.json."""
        if not os.path.exists(self.active_session_path):
            return {}
        try:
            with open(self.active_session_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Failed to read runtime state: {e}")
            return {}

    def save_runtime_state(self, state: Dict[str, Any]) -> bool:
        """Writes current execution state to runtime/active_session.json."""
        try:
            with open(self.active_session_path, "w", encoding="utf-8") as f:
                json.dump(state, f, indent=2, ensure_ascii=False)
            return True
        except Exception as e:
            logger.error(f"Failed to save runtime state: {e}")
            return False

    def clear_runtime_state(self) -> bool:
        """Cleans active execution session state. Leaves persistent knowledge untouched."""
        try:
            if os.path.exists(self.active_session_path):
                os.remove(self.active_session_path)
            return True
        except Exception as e:
            logger.error(f"Failed to clear runtime state: {e}")
            return False

    def get_candidate_learnings(self) -> List[Dict[str, Any]]:
        """Reads candidate learnings currently in validation pipeline from runtime/."""
        if not os.path.exists(self.candidate_learnings_path):
            return []
        try:
            with open(self.candidate_learnings_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Failed to read candidate learnings: {e}")
            return []

    def save_candidate_learnings(self, candidates: List[Dict[str, Any]]) -> bool:
        """Writes candidate learnings to runtime/candidate_learnings.json."""
        try:
            with open(self.candidate_learnings_path, "w", encoding="utf-8") as f:
                json.dump(candidates, f, indent=2, ensure_ascii=False)
            return True
        except Exception as e:
            logger.error(f"Failed to save candidate learnings: {e}")
            return False

    def get_execution_history(self) -> List[Dict[str, Any]]:
        """Reads raw recent test run execution records from runtime/test_run_history.json."""
        if not os.path.exists(self.test_run_history_path):
            return []
        try:
            with open(self.test_run_history_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Failed to read test run history: {e}")
            return []

    def append_execution_history(self, record: Dict[str, Any]) -> bool:
        """Appends a test execution record to runtime/test_run_history.json."""
        try:
            history = self.get_execution_history()
            history.append(record)
            # Maintain a bounded sliding window of recent runs (e.g. last 1000)
            if len(history) > 1000:
                history = history[-1000:]
            with open(self.test_run_history_path, "w", encoding="utf-8") as f:
                json.dump(history, f, indent=2, ensure_ascii=False)
            return True
        except Exception as e:
            logger.error(f"Failed to append execution history: {e}")
            return False
