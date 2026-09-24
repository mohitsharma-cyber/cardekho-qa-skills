"""
API & Network Traffic Capture & Sanitizer for Jira AI QA Orchestrator.
Classifies network requests (Business, Analytics, Third Party, Ads, Static),
redacts sensitive credentials/PII, and logs structured business API telemetry.
"""

import json
import re
import time
from typing import Any, Dict, List, Optional


class NetworkCapture:
    # Classification rules based on URL patterns
    ANALYTICS_DOMAINS = ["google-analytics.com", "analytics", "branch.io", "segment.io", "mixpanel", "hotjar", "clevertap"]
    AD_DOMAINS = ["doubleclick.net", "googlesyndication", "adservice", "ads", "appnexus"]
    STATIC_EXTENSIONS = [".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg", ".css", ".woff", ".woff2", ".ttf", ".js"]
    BUSINESS_PATHS = ["/api/", "/v1/", "/v2/", "/f8/", "/feed/", "/catalog/", "/model/", "/search/", "/user/", "/auth/"]

    SENSITIVE_KEYS = [
        "password", "pass", "pwd", "token", "auth", "authorization", "secret", "bearer",
        "access_token", "refresh_token", "apikey", "cookie", "session_id", "otp",
        "pan", "aadhaar", "card_number", "cvv"
    ]

    def classify_request(self, url: str) -> str:
        url_lower = url.lower()
        if any(ad in url_lower for ad in self.AD_DOMAINS):
            return "ADVERTISEMENT"
        if any(an in url_lower for an in self.ANALYTICS_DOMAINS):
            return "ANALYTICS"
        if any(url_lower.split("?")[0].endswith(ext) for ext in self.STATIC_EXTENSIONS):
            return "STATIC_ASSET"
        if any(bp in url_lower for bp in self.BUSINESS_PATHS):
            return "BUSINESS_API"
        if "cardekho" in url_lower or "bikedekho" in url_lower:
            return "BUSINESS_API"
        return "THIRD_PARTY"

    def redact_data(self, data: Any) -> Any:
        """Deeply traverses dict/list/string to mask credentials and sensitive PII."""
        if isinstance(data, dict):
            redacted = {}
            for k, v in data.items():
                if any(sk in k.lower() for sk in self.SENSITIVE_KEYS):
                    redacted[k] = "[REDACTED_SECRET]"
                else:
                    redacted[k] = self.redact_data(v)
            return redacted
        elif isinstance(data, list):
            return [self.redact_data(item) for item in data]
        elif isinstance(data, str):
            # Mask Bearer tokens
            val = re.sub(r'(?i)bearer\s+[A-Za-z0-9\-\._~\+\/]+=*', 'Bearer [REDACTED_TOKEN]', data)
            # Mask Passwords in queries
            val = re.sub(r'(?i)(password|token|secret)=([^&]+)', r'\1=[REDACTED]', val)
            return val
        return data

    def format_api_record(self, execution_id: str, test_case_id: str, url: str, method: str,
                          status_code: int, response_time_ms: int,
                          req_body: Optional[Any] = None, resp_body: Optional[Any] = None) -> Dict[str, Any]:
        """Constructs a sanitized, classified API telemetry record."""
        classification = self.classify_request(url)
        clean_req = self.redact_data(req_body) if req_body else None
        clean_resp = self.redact_data(resp_body) if resp_body else None

        return {
            "execution_id": execution_id,
            "test_case_id": test_case_id,
            "url": url,
            "method": method.upper(),
            "status_code": status_code,
            "response_time_ms": response_time_ms,
            "classification": classification,
            "request_body": json.dumps(clean_req) if isinstance(clean_req, (dict, list)) else clean_req,
            "response_body": json.dumps(clean_resp) if isinstance(clean_resp, (dict, list)) else clean_resp,
            "is_redacted": True,
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
        }

    def capture_traffic(self, scenario_id: str, base_api_url: str = "") -> List[Dict[str, Any]]:
        """Simulates or collects captured network traffic calls for a scenario."""
        url = f"{base_api_url or 'https://testingpwa2.cardekho.com/api'}/v1/search"
        return [
            self.format_api_record(
                execution_id="EXEC-RUN",
                test_case_id=scenario_id,
                url=url,
                method="GET",
                status_code=200,
                response_time_ms=145,
                req_body={"query": "suv"},
                resp_body={"count": 15, "items": [{"id": 1, "model": "Brezza"}]}
            )
        ]
