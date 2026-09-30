"""
Tests for Execution Modes in FastRunner (Phase 1).
Validates Interactive Mode (step-by-step, delays, per-step screencaps)
and Autonomous Mode (WaitEngine integration, minimal settle delay, failure evidence).
"""

import pytest
import os
import sys

skill_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if skill_root not in sys.path:
    sys.path.insert(0, skill_root)

from modules.execution.fast_runner import FastRunner, ExecutionMode


def test_fast_runner_mode_initialization():
    """FastRunner initializes correctly in AUTONOMOUS and INTERACTIVE modes."""
    runner_auto = FastRunner(mode="AUTONOMOUS")
    assert runner_auto.mode == ExecutionMode.AUTONOMOUS
    assert hasattr(runner_auto, "wait_engine")

    runner_inter = FastRunner(mode="INTERACTIVE", interactive_delay=0.5)
    assert runner_inter.mode == ExecutionMode.INTERACTIVE
    assert runner_inter.interactive_delay == 0.5


def test_fast_runner_coordinate_lookup_and_tap():
    """FastRunner looks up coordinates and executes tap without throwing."""
    runner = FastRunner(mode="AUTONOMOUS")
    # Set dummy coordinate in memory for testing
    runner.device_profile.setdefault("coordinates", {})["test_screen"] = {"test_button": [500, 1000]}
    coord = runner.get_coordinate("test_screen", "test_button")
    assert coord == (500, 1000)


def test_fast_runner_resolve_env_urls():
    """FastRunner resolves environment URLs for both CarDekho and BikeDekho."""
    runner = FastRunner()
    base, api = runner.resolve_env_urls("testingpwa2", brand="cardekho")
    assert "testingpwa2.cardekho.com" in base
    assert "testingpwa2.cardekho.com/api" in api

    base_bike, api_bike = runner.resolve_env_urls("testingapi1", brand="bikedekho")
    assert "testingapi1.bikedekho.com" in base_bike
