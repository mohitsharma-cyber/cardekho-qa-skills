"""
Controlled Learning Engine for CarDekho & BikeDekho QA Orchestrator.
Implements the 5-stage learning pipeline:
Observation ➔ Candidate Learning ➔ Validation ➔ Confidence/Approval ➔ Persistent Knowledge

Rules:
- Never automatically convert a single observation into permanent truth.
- Requires repeated confirmations (min_observations=3) and validation checks.
- High-impact changes require explicit approval.
- Isolates candidate learnings in runtime/ before promotion to knowledge/.
"""

import os
import json
import logging
from enum import Enum
from typing import Dict, Any, List, Optional
from datetime import datetime
from .memory_manager import MemoryManager

logger = logging.getLogger(__name__)

class LearningType(str, Enum):
    DEVICE_COORDINATE = "DEVICE_COORDINATE"
    WORKFLOW_PATTERN = "WORKFLOW_PATTERN"
    RECOVERY_ACTION = "RECOVERY_ACTION"
    ENVIRONMENT_BEHAVIOR = "ENVIRONMENT_BEHAVIOR"
    CONFIRMED_TEST_PATTERN = "CONFIRMED_TEST_PATTERN"

class LearningStatus(str, Enum):
    CANDIDATE = "CANDIDATE"
    VALIDATED = "VALIDATED"
    PROMOTED = "PROMOTED"
    REJECTED = "REJECTED"

class CandidateLearning:
    def __init__(
        self,
        candidate_id: str,
        learning_type: LearningType,
        key: str,
        proposed_value: Any,
        observation_count: int = 1,
        confidence_score: float = 0.33,
        status: LearningStatus = LearningStatus.CANDIDATE,
        requires_approval: bool = False,
        validation_errors: Optional[List[str]] = None,
        history: Optional[List[Dict[str, Any]]] = None
    ):
        self.candidate_id = candidate_id
        self.learning_type = learning_type
        self.key = key
        self.proposed_value = proposed_value
        self.observation_count = observation_count
        self.confidence_score = confidence_score
        self.status = status
        self.requires_approval = requires_approval
        self.validation_errors = validation_errors or []
        self.history = history or []
        self.first_observed_at = datetime.now().isoformat()
        self.last_observed_at = datetime.now().isoformat()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "candidate_id": self.candidate_id,
            "learning_type": self.learning_type.value if isinstance(self.learning_type, LearningType) else self.learning_type,
            "key": self.key,
            "proposed_value": self.proposed_value,
            "observation_count": self.observation_count,
            "confidence_score": self.confidence_score,
            "status": self.status.value if isinstance(self.status, LearningStatus) else self.status,
            "requires_approval": self.requires_approval,
            "validation_errors": self.validation_errors,
            "history": self.history,
            "first_observed_at": self.first_observed_at,
            "last_observed_at": self.last_observed_at
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'CandidateLearning':
        c = cls(
            candidate_id=data["candidate_id"],
            learning_type=LearningType(data["learning_type"]),
            key=data["key"],
            proposed_value=data["proposed_value"],
            observation_count=data.get("observation_count", 1),
            confidence_score=data.get("confidence_score", 0.33),
            status=LearningStatus(data.get("status", LearningStatus.CANDIDATE.value)),
            requires_approval=data.get("requires_approval", False),
            validation_errors=data.get("validation_errors", []),
            history=data.get("history", [])
        )
        c.first_observed_at = data.get("first_observed_at", c.first_observed_at)
        c.last_observed_at = data.get("last_observed_at", c.last_observed_at)
        return c

class ControlledLearner:
    """Orchestrates safe, validated learning from QA execution observations."""

    def __init__(
        self,
        memory_manager: Optional[MemoryManager] = None,
        min_observations_threshold: int = 3,
        min_confidence_threshold: float = 0.9
    ):
        self.memory_manager = memory_manager or MemoryManager()
        self.min_observations_threshold = min_observations_threshold
        self.min_confidence_threshold = min_confidence_threshold

    # --------------------------------------------------------------------------
    # Stage 1: Observation & Candidate Registration
    # --------------------------------------------------------------------------

    def record_observation(
        self,
        learning_type: LearningType,
        key: str,
        value: Any,
        metadata: Optional[Dict[str, Any]] = None,
        requires_approval: bool = False
    ) -> Dict[str, Any]:
        """
        Registers an observed behavior into runtime candidate storage.
        Never directly mutates persistent knowledge on a single observation.
        """
        metadata = metadata or {}
        candidates = self._load_candidates()

        # Find matching candidate
        candidate = None
        for c in candidates:
            if c.learning_type == learning_type and c.key == key and c.status != LearningStatus.PROMOTED:
                candidate = c
                break

        if candidate is None:
            # Create new candidate
            candidate_id = f"CAND-{learning_type.value[:4]}-{len(candidates) + 1:04d}"
            candidate = CandidateLearning(
                candidate_id=candidate_id,
                learning_type=learning_type,
                key=key,
                proposed_value=value,
                observation_count=1,
                confidence_score=round(1.0 / self.min_observations_threshold, 2),
                status=LearningStatus.CANDIDATE,
                requires_approval=requires_approval,
                history=[{"timestamp": datetime.now().isoformat(), "metadata": metadata}]
            )
            candidates.append(candidate)
        else:
            # Existing candidate: verify consistency
            if candidate.proposed_value == value:
                candidate.observation_count += 1
                candidate.confidence_score = min(
                    1.0,
                    round(candidate.observation_count / self.min_observations_threshold, 2)
                )
                candidate.last_observed_at = datetime.now().isoformat()
                candidate.history.append({"timestamp": datetime.now().isoformat(), "metadata": metadata})
            else:
                # Contradictory observation: decrement confidence or reset
                candidate.confidence_score = max(0.1, round(candidate.confidence_score - 0.25, 2))
                candidate.validation_errors.append(
                    f"Conflicting value observed at {datetime.now().isoformat()}: {value} != {candidate.proposed_value}"
                )

        # Stage 2: Validation
        self.validate_candidate(candidate)

        # Save to runtime
        self._save_candidates(candidates)

        # Stage 3 & 4: Evaluate Promotion
        promotion_result = self.evaluate_promotion(candidate.candidate_id)

        return {
            "candidate_id": candidate.candidate_id,
            "status": candidate.status.value,
            "observation_count": candidate.observation_count,
            "confidence_score": candidate.confidence_score,
            "promoted_to_persistent_memory": promotion_result.get("promoted", False),
            "promotion_detail": promotion_result
        }

    # --------------------------------------------------------------------------
    # Stage 2: Validation
    # --------------------------------------------------------------------------

    def validate_candidate(self, candidate: CandidateLearning) -> bool:
        """Applies structural and safety validation to candidate learning."""
        errors = []

        if candidate.learning_type == LearningType.DEVICE_COORDINATE:
            coords = candidate.proposed_value
            if not isinstance(coords, (list, tuple)) or len(coords) != 2:
                errors.append(f"Invalid coordinate format: {coords}. Must be [x, y].")
            else:
                x, y = coords[0], coords[1]
                if not (isinstance(x, (int, float)) and isinstance(y, (int, float))):
                    errors.append(f"Coordinate points must be numeric: {coords}")
                elif x <= 0 or y <= 0 or x > 3840 or y > 3840:
                    errors.append(f"Coordinates outside reasonable screen bounds (0-3840): {coords}")

        elif candidate.learning_type == LearningType.ENVIRONMENT_BEHAVIOR:
            val = str(candidate.proposed_value).lower()
            if not (val.startswith("https://") or val.startswith("http://")):
                errors.append(f"Environment URL must have http/https scheme: {val}")
            if not any(d in val for d in ["cardekho.com", "bikedekho.com", "girnarsoft.com", "localhost", "127.0.0.1"]):
                errors.append(f"Environment URL must belong to approved domains: {val}")

        elif candidate.learning_type == LearningType.RECOVERY_ACTION:
            action = str(candidate.proposed_value).lower()
            destructive_tokens = ["rm -rf", "format", "wipe", "factory", "reboot bootloader", "install-existing"]
            if any(tok in action for tok in destructive_tokens):
                errors.append(f"Destructive or unsafe recovery command detected: {action}")

        elif candidate.learning_type == LearningType.WORKFLOW_PATTERN:
            pattern = candidate.proposed_value
            if not isinstance(pattern, list) or len(pattern) == 0:
                errors.append("Workflow pattern must be a non-empty list of steps.")

        candidate.validation_errors = errors
        if errors:
            candidate.status = LearningStatus.REJECTED
            return False
        else:
            if candidate.status != LearningStatus.PROMOTED:
                candidate.status = LearningStatus.VALIDATED
            return True

    # --------------------------------------------------------------------------
    # Stage 3 & 4: Confidence Gate & Promotion to Persistent Knowledge
    # --------------------------------------------------------------------------

    def evaluate_promotion(
        self,
        candidate_id: str,
        force_approve: bool = False
    ) -> Dict[str, Any]:
        """
        Evaluates whether a validated candidate meets the confidence threshold
        or user approval to be promoted into persistent knowledge/learned_memory.json.
        """
        candidates = self._load_candidates()
        candidate = next((c for c in candidates if c.candidate_id == candidate_id), None)

        if not candidate:
            return {"promoted": False, "reason": f"Candidate {candidate_id} not found."}

        if candidate.status == LearningStatus.PROMOTED:
            return {"promoted": False, "reason": "Candidate has already been promoted."}

        if candidate.status == LearningStatus.REJECTED:
            return {"promoted": False, "reason": f"Candidate rejected due to errors: {candidate.validation_errors}"}

        # Check approval gate
        if candidate.requires_approval and not force_approve:
            return {
                "promoted": False,
                "reason": "Requires explicit user approval before permanent promotion."
            }

        # Check multi-observation confidence threshold
        if (
            candidate.observation_count >= self.min_observations_threshold
            and candidate.confidence_score >= self.min_confidence_threshold
            and candidate.status == LearningStatus.VALIDATED
        ):
            # Promote to persistent knowledge
            promoted = self._apply_to_persistent_knowledge(candidate)
            if promoted:
                candidate.status = LearningStatus.PROMOTED
                self._save_candidates(candidates)
                return {
                    "promoted": True,
                    "key": candidate.key,
                    "promoted_value": candidate.proposed_value,
                    "confidence_score": candidate.confidence_score,
                    "observations": candidate.observation_count
                }
            else:
                return {"promoted": False, "reason": "Failed to persist to knowledge/."}

        return {
            "promoted": False,
            "reason": (
                f"Threshold not met: {candidate.observation_count}/{self.min_observations_threshold} observations, "
                f"confidence {candidate.confidence_score}/{self.min_confidence_threshold}"
            )
        }

    def _apply_to_persistent_knowledge(self, candidate: CandidateLearning) -> bool:
        """Applies validated candidate value into persistent learned_memory.json."""
        knowledge = self.memory_manager.get_persistent_knowledge()
        if not knowledge:
            knowledge = {"version": "2.1.0", "learning_mode": "ACTIVE"}

        # Navigate dotted path (e.g. device_profiles.OnePlus_CPH2585.coordinates.home.search_bar)
        keys = candidate.key.split(".")
        curr = knowledge
        for k in keys[:-1]:
            if k not in curr or not isinstance(curr[k], dict):
                curr[k] = {}
            curr = curr[k]

        curr[keys[-1]] = candidate.proposed_value
        knowledge["last_updated"] = datetime.now().isoformat()

        return self.memory_manager.save_persistent_knowledge(knowledge)

    def _load_candidates(self) -> List[CandidateLearning]:
        data = self.memory_manager.get_candidate_learnings()
        return [CandidateLearning.from_dict(d) for d in data]

    def _save_candidates(self, candidates: List[CandidateLearning]):
        data = [c.to_dict() for c in candidates]
        self.memory_manager.save_candidate_learnings(data)
