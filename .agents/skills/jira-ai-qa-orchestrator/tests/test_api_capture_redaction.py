import pytest
import os
import sys

base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if base_dir not in sys.path:
    sys.path.insert(0, base_dir)

from modules.api.network_capture import NetworkCapture


def test_api_classification():
    nc = NetworkCapture()
    assert nc.classify_request("https://testingpwa2.cardekho.com/api/v1/search") == "BUSINESS_API"
    assert nc.classify_request("https://www.google-analytics.com/collect") == "ANALYTICS"
    assert nc.classify_request("https://securepubads.g.doubleclick.net/gampad/ads") == "ADVERTISEMENT"
    assert nc.classify_request("https://static.cardekho.com/images/hero.webp") == "STATIC_ASSET"


def test_secret_and_token_redaction():
    nc = NetworkCapture()
    payload = {
        "user": "qa_tester",
        "password": "SuperSecretPassword123",
        "nested": {
            "auth_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9",
            "normal_data": "CarDekho Brezza"
        }
    }
    redacted = nc.redact_data(payload)
    assert redacted["password"] == "[REDACTED_SECRET]"
    assert redacted["nested"]["auth_token"] == "[REDACTED_SECRET]"
    assert redacted["nested"]["normal_data"] == "CarDekho Brezza"
