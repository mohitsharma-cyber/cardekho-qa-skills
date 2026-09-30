"""
Learning and Historical Intelligence Module for CarDekho & BikeDekho QA Orchestrator.
Provides:
- Memory separation (knowledge/ vs runtime/)
- Controlled learning pipeline (Observation -> Candidate -> Validation -> Confidence -> Knowledge)
- Historical QA intelligence (failure patterns, regression hotspots, test prioritization)
- Flaky test detection and reproducibility gating
- Objective QA metrics calculation
"""

from .memory_manager import MemoryManager
from .controlled_learner import ControlledLearner, CandidateLearning, LearningType, LearningStatus
from .historical_intelligence import HistoricalIntelligence
from .flaky_detector import FlakyDetector, TestExecutionRecord, FlakyStatus
from .metrics_reporter import MetricsReporter, QAMetricsReport

__all__ = [
    "MemoryManager",
    "ControlledLearner",
    "CandidateLearning",
    "LearningType",
    "LearningStatus",
    "HistoricalIntelligence",
    "FlakyDetector",
    "TestExecutionRecord",
    "FlakyStatus",
    "MetricsReporter",
    "QAMetricsReport"
]
