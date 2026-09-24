import pytest
import os
import sys

base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if base_dir not in sys.path:
    sys.path.insert(0, base_dir)

from modules.assertions.assertion_engine import AssertionEngine


def test_status_code_assertion():
    spec = {"kind": "STATUS_CODE", "expected": 200}
    passed, msg = AssertionEngine.evaluate_assertion(spec, {"status_code": 200})
    assert passed is True

    failed, msg = AssertionEngine.evaluate_assertion(spec, {"status_code": 500})
    assert failed is False
    assert "mismatch" in msg


def test_element_not_contains_stack_trace():
    spec = {"kind": "ELEMENT_NOT_CONTAINS", "unexpected": "NullPointerException"}
    passed, _ = AssertionEngine.evaluate_assertion(spec, {"page_text": "Welcome to CarDekho Search"})
    assert passed is True

    failed, msg = AssertionEngine.evaluate_assertion(spec, {"page_text": "FATAL: NullPointerException in SearchController.java"})
    assert failed is False
    assert "forbidden" in msg.lower()


def test_no_crash_assertion():
    spec = {"kind": "NO_CRASH", "expected": True}
    passed, _ = AssertionEngine.evaluate_assertion(spec, {"app_crashed": False})
    assert passed is True

    failed, _ = AssertionEngine.evaluate_assertion(spec, {"app_crashed": True})
    assert failed is False
