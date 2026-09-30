"""
Tests for Controlled Learning and Historical Intelligence Engine.
Validates:
1. Memory Separation (knowledge/ vs runtime/)
2. Controlled Learning Pipeline (Observation -> Candidate -> Validation -> Confidence -> Knowledge)
3. Historical QA Intelligence (failure tracking & scenario prioritization)
4. Flaky Test Detection & Reproducibility Gating
5. Factual QA Metrics (clean un-gamed reporting)
6. Safety & Immutability Rules
"""

import os
import sys
import shutil
import pytest
import tempfile
from typing import Dict, Any

skill_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if skill_root not in sys.path:
    sys.path.insert(0, skill_root)

from modules.learning.memory_manager import MemoryManager
from modules.learning.controlled_learner import (
    ControlledLearner,
    LearningType,
    LearningStatus
)
from modules.learning.historical_intelligence import HistoricalIntelligence
from modules.learning.flaky_detector import FlakyDetector, FlakyStatus
from modules.learning.metrics_reporter import MetricsReporter


@pytest.fixture
def temp_memory_dirs():
    """Creates isolated temporary directories for knowledge and runtime."""
    temp_dir = tempfile.mkdtemp()
    k_dir = os.path.join(temp_dir, "knowledge")
    r_dir = os.path.join(temp_dir, "runtime")
    os.makedirs(k_dir, exist_ok=True)
    os.makedirs(r_dir, exist_ok=True)

    manager = MemoryManager(knowledge_dir=k_dir, runtime_dir=r_dir)
    # Seed initial knowledge
    manager.save_persistent_knowledge({
        "version": "2.0.0",
        "device_profiles": {
            "OnePlus_CPH2585": {
                "coordinates": {"home": {"search_bar": [540, 260]}}
            }
        }
    })

    yield manager, k_dir, r_dir
    shutil.rmtree(temp_dir, ignore_errors=True)


# ==============================================================================
# 1. Memory Separation Tests
# ==============================================================================

def test_memory_separation_runtime_does_not_mutate_persistent_knowledge(temp_memory_dirs):
    manager, k_dir, r_dir = temp_memory_dirs

    # Write ephemeral runtime state
    manager.save_runtime_state({"active_ticket": "MB2C-9999", "status": "IN_PROGRESS"})

    # Verify persistent knowledge is completely unaffected
    persisted = manager.get_persistent_knowledge()
    assert "active_ticket" not in persisted
    assert persisted.get("version") == "2.0.0"

    # Verify runtime state was saved in runtime_dir
    runtime_state = manager.get_runtime_state()
    assert runtime_state.get("active_ticket") == "MB2C-9999"

    # Clearing runtime state leaves persistent knowledge intact
    manager.clear_runtime_state()
    assert manager.get_runtime_state() == {}
    assert manager.get_persistent_knowledge().get("version") == "2.0.0"


# ==============================================================================
# 2. Controlled Learning Pipeline Tests
# ==============================================================================

def test_controlled_learning_does_not_promote_on_single_observation(temp_memory_dirs):
    manager, _, _ = temp_memory_dirs
    learner = ControlledLearner(memory_manager=manager, min_observations_threshold=3)

    # 1st observation of new coordinate
    res = learner.record_observation(
        learning_type=LearningType.DEVICE_COORDINATE,
        key="device_profiles.OnePlus_CPH2585.coordinates.home.filter_pill",
        value=[300, 450],
        metadata={"ticket": "MB2C-1001"}
    )

    # Must be recorded as candidate in runtime, NOT promoted to persistent knowledge
    assert res["status"] == LearningStatus.VALIDATED.value
    assert res["observation_count"] == 1
    assert res["promoted_to_persistent_memory"] is False

    # Verify persistent knowledge does NOT have this coordinate yet
    persisted = manager.get_persistent_knowledge()
    coords = persisted["device_profiles"]["OnePlus_CPH2585"]["coordinates"]["home"]
    assert "filter_pill" not in coords


def test_controlled_learning_promotes_after_threshold_confirmations(temp_memory_dirs):
    manager, _, _ = temp_memory_dirs
    learner = ControlledLearner(memory_manager=manager, min_observations_threshold=3)
    target_key = "device_profiles.OnePlus_CPH2585.coordinates.home.filter_pill"
    target_val = [300, 450]

    # Observation 1
    res1 = learner.record_observation(LearningType.DEVICE_COORDINATE, target_key, target_val)
    assert res1["promoted_to_persistent_memory"] is False

    # Observation 2
    res2 = learner.record_observation(LearningType.DEVICE_COORDINATE, target_key, target_val)
    assert res2["promoted_to_persistent_memory"] is False
    assert res2["observation_count"] == 2

    # Observation 3 -> Meets threshold!
    res3 = learner.record_observation(LearningType.DEVICE_COORDINATE, target_key, target_val)
    assert res3["promoted_to_persistent_memory"] is True
    assert res3["observation_count"] == 3

    # Verify persistent memory now contains the promoted coordinate!
    persisted = manager.get_persistent_knowledge()
    coords = persisted["device_profiles"]["OnePlus_CPH2585"]["coordinates"]["home"]
    assert coords["filter_pill"] == [300, 450]


def test_controlled_learning_validates_and_rejects_invalid_values(temp_memory_dirs):
    manager, _, _ = temp_memory_dirs
    learner = ControlledLearner(memory_manager=manager)

    # 1. Invalid coordinate (outside screen bounds)
    res_coord = learner.record_observation(
        learning_type=LearningType.DEVICE_COORDINATE,
        key="device_profiles.OnePlus_CPH2585.coordinates.home.invalid",
        value=[99999, -50]
    )
    assert res_coord["status"] == LearningStatus.REJECTED.value
    assert res_coord["promoted_to_persistent_memory"] is False

    # 2. Unsafe recovery command
    res_cmd = learner.record_observation(
        learning_type=LearningType.RECOVERY_ACTION,
        key="recovery.anr_handler",
        value="adb shell rm -rf /data/data"
    )
    assert res_cmd["status"] == LearningStatus.REJECTED.value

    # 3. Disapproved external environment URL
    res_env = learner.record_observation(
        learning_type=LearningType.ENVIRONMENT_BEHAVIOR,
        key="environments.cardekho.malicious",
        value="https://unknown-malicious-domain.com"
    )
    assert res_env["status"] == LearningStatus.REJECTED.value


def test_approval_gate_blocks_auto_promotion(temp_memory_dirs):
    manager, _, _ = temp_memory_dirs
    learner = ControlledLearner(memory_manager=manager, min_observations_threshold=2)

    # Record 2 observations of high-impact item requiring explicit approval
    learner.record_observation(
        learning_type=LearningType.ENVIRONMENT_BEHAVIOR,
        key="environments.cardekho.new_server",
        value="https://testingpwa9.cardekho.com",
        requires_approval=True
    )
    res = learner.record_observation(
        learning_type=LearningType.ENVIRONMENT_BEHAVIOR,
        key="environments.cardekho.new_server",
        value="https://testingpwa9.cardekho.com",
        requires_approval=True
    )

    # Observations met, but approval gate prevents promotion
    assert res["promoted_to_persistent_memory"] is False
    assert "approval" in res["promotion_detail"]["reason"].lower()

    # User explicitly approves -> Promotion succeeds
    candidate_id = res["candidate_id"]
    approval_res = learner.evaluate_promotion(candidate_id, force_approve=True)
    assert approval_res["promoted"] is True


# ==============================================================================
# 3. Historical QA Intelligence Tests
# ==============================================================================

def test_historical_intelligence_tracking_and_prioritization(temp_memory_dirs):
    manager, _, _ = temp_memory_dirs
    history = HistoricalIntelligence(memory_manager=manager)

    # Record historical runs with failures in 'price_tab' module
    history.record_run(
        ticket="MB2C-7001",
        module="price_tab",
        environment="testingpwa1",
        device="OnePlus_CPH2585",
        results={"TC-PRICE-01": "FAIL", "REG-01": "FAIL"},
        defects=[{"summary": "RTO Calculation Mismatch", "probable_layer": "Data", "component": "price_tab"}],
        api_results=[{"endpoint": "/api/v1/price", "status": 500, "validation_result": "FAIL"}]
    )
    history.record_run(
        ticket="MB2C-7002",
        module="price_tab",
        environment="testingpwa1",
        device="OnePlus_CPH2585",
        results={"TC-PRICE-01": "FAIL"}
    )
    history.record_run(
        ticket="MB2C-7003",
        module="gallery",
        environment="testingpwa1",
        device="OnePlus_CPH2585",
        results={"TC-GALLERY-01": "PASS"}
    )

    # 1. Frequently failing modules query
    top_failing = history.get_top_failing_modules()
    assert len(top_failing) >= 1
    assert top_failing[0]["module"] == "price_tab"
    assert top_failing[0]["failed_tests"] >= 2

    # 2. Common API failures
    api_failures = history.get_common_api_failures()
    assert len(api_failures) >= 1
    assert api_failures[0]["endpoint"] == "/api/v1/price"

    # 3. Prioritize scenarios: price_tab test case must be prioritized ahead of low-risk gallery
    scenarios = [
        {"id": "TC-01", "title": "Check gallery image swiping", "target_area": "gallery"},
        {"id": "TC-02", "title": "Assert on-road price taxes", "target_area": "price_tab", "endpoint": "/api/v1/price"}
    ]
    prioritized = history.prioritize_scenarios(scenarios)
    assert prioritized[0]["id"] == "TC-02"


# ==============================================================================
# 4. Flaky Test Detection & Reproducibility Tests
# ==============================================================================

def test_flaky_test_detection_intermittent_pattern(temp_memory_dirs):
    manager, _, _ = temp_memory_dirs
    detector = FlakyDetector(memory_manager=manager)
    tc = "TC-LEAD-FORM-SUBMIT"

    # Feed sequence: PASS -> PASS -> FAIL -> PASS -> FAIL (exact prompt example)
    pattern = ["PASS", "PASS", "FAIL", "PASS", "FAIL"]
    for verdict in pattern:
        analysis = detector.record_execution(test_case_id=tc, verdict=verdict)

    # Must classify as POTENTIALLY_FLAKY
    assert analysis["status"] == FlakyStatus.POTENTIALLY_FLAKY.value
    assert analysis["flakiness_score"] > 0.4
    assert analysis["pass_count"] == 3
    assert analysis["fail_count"] == 2
    assert analysis["transitions"] == 3
    assert "reproducibility" in analysis["recommendation"].lower()


def test_reproducibility_gating_distinguishes_defect_from_flaky(temp_memory_dirs):
    manager, _, _ = temp_memory_dirs
    detector = FlakyDetector(memory_manager=manager)
    tc = "TC-SEARCH-AUTOSUGGEST"

    # Case A: Fails intermittently during retries (e.g. 1 PASS, 1 FAIL) -> Flaky scenario
    res_flaky = detector.evaluate_reproducibility(
        test_case_id=tc,
        consecutive_retry_verdicts=["PASS", "FAIL"]
    )
    assert res_flaky["is_reproducible"] is False
    assert res_flaky["classification"] == "FLAKY_SCENARIO"
    assert "do not file" in res_flaky["action"].lower()

    # Case B: Consistently reproduces across all retries -> Confirmed product defect
    res_defect = detector.evaluate_reproducibility(
        test_case_id=tc,
        consecutive_retry_verdicts=["FAIL", "FAIL"]
    )
    assert res_defect["is_reproducible"] is True
    assert res_defect["classification"] == "REPRODUCIBLE_DEFECT"
    assert "defect card" in res_defect["action"].lower()


# ==============================================================================
# 5. QA Metrics Reporter Tests
# ==============================================================================

def test_qa_metrics_reporter_factual_metrics_without_quality_scores():
    reporter = MetricsReporter()

    report = reporter.compute_metrics(
        ticket="MB2C-8812",
        requirements=["AC1: Display on-road price", "AC2: Support variant switch", "AC3: Form validation"],
        covered_requirements=["AC1: Display on-road price", "AC2: Support variant switch", "AC3: Form validation"],
        planned_cases=[
            {"id": "TC-01", "title": "Check on-road price"},
            {"id": "TC-02", "title": "Variant switcher"},
            {"id": "REG-01", "title": "EMI collateral sanity"}
        ],
        executed_results={"TC-01": "PASS", "TC-02": "PASS", "REG-01": "PASS"},
        step_execution_times_ms=[120.5, 140.0, 110.2],
        flaky_scenarios=[],
        defects_found=[]
    )

    data = report.to_dict()
    assert data["requirement_coverage"] == "3/3 (100.0%)"
    assert data["execution_coverage"] == "3/3 (100.0%)"
    assert data["regression_coverage"] == "1/1 (100.0%)"
    assert data["defect_count"] == 0
    assert data["blocked_tests"] == 0
    assert data["flaky_tests"] == 0
    assert data["average_execution_time_ms"] > 100.0
    assert data["final_verdict"] == "PASS"

    # Verify no arbitrary quality score in text output
    summary = report.format_summary_card()
    assert "Quality Score" not in summary
    assert "Rank" not in summary
    assert "Requirement Coverage" in summary
    assert "Execution Coverage" in summary
    assert "Regression Coverage" in summary
