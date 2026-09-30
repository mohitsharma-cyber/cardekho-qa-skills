"""
API Client for Jira AI QA Orchestrator.
Executes HTTP/REST requests against CarDekho & BikeDekho services.
Measures millisecond response times, traps network timeouts and connection errors,
and strictly sanitizes sensitive tokens and credentials from logs.
"""

import time
import json
import re
from typing import Dict, Any, Optional
import requests

SENSITIVE_HEADERS = ["authorization", "token", "cookie", "x-api-key", "secret", "session"]
SENSITIVE_KEYS = ["password", "token", "otp", "secret", "cvv", "auth", "access_token"]

class ApiClient:
    """Robust, timeout-safe HTTP client with precision timing and PII/token redaction."""

    def __init__(self, default_timeout: float = 10.0):
        self.default_timeout = default_timeout

    def sanitize_headers(self, headers: Optional[Dict[str, str]]) -> Dict[str, str]:
        """Redacts bearer tokens and secret headers from logging output."""
        if not headers:
            return {}
        clean = {}
        for k, v in headers.items():
            if any(sh in k.lower() for sh in SENSITIVE_HEADERS):
                clean[k] = "[REDACTED_SECRET_HEADER]"
            else:
                clean[k] = v
        return clean

    def sanitize_payload(self, data: Any) -> Any:
        """Deeply traverses and masks sensitive keys in payloads."""
        if isinstance(data, dict):
            clean = {}
            for k, v in data.items():
                if any(sk in str(k).lower() for sk in SENSITIVE_KEYS):
                    clean[k] = "[REDACTED]"
                else:
                    clean[k] = self.sanitize_payload(v)
            return clean
        elif isinstance(data, list):
            return [self.sanitize_payload(item) for item in data]
        return data

    def request(
        self,
        method: str,
        url: str,
        headers: Optional[Dict[str, str]] = None,
        params: Optional[Dict[str, Any]] = None,
        json_body: Optional[Any] = None,
        data: Optional[Any] = None,
        timeout: Optional[float] = None
    ) -> Dict[str, Any]:
        """
        Executes HTTP request, records round-trip duration in ms, and wraps exceptions cleanly.
        """
        req_timeout = timeout if timeout is not None else self.default_timeout
        start_time = time.perf_counter()

        sanitized_headers = self.sanitize_headers(headers)
        sanitized_body = self.sanitize_payload(json_body if json_body is not None else data)

        try:
            res = requests.request(
                method=method.upper(),
                url=url,
                headers=headers,
                params=params,
                json=json_body,
                data=data,
                timeout=req_timeout,
                verify=False
            )
            elapsed_ms = round((time.perf_counter() - start_time) * 1000, 2)

            is_json = False
            parsed_data = None
            try:
                parsed_data = res.json()
                is_json = True
            except Exception:
                parsed_data = res.text

            return {
                "status_code": res.status_code,
                "response_time_ms": elapsed_ms,
                "is_json": is_json,
                "data": parsed_data,
                "headers": dict(res.headers),
                "url": url,
                "method": method.upper(),
                "error": None,
                "sanitized_request": {
                    "headers": sanitized_headers,
                    "body": sanitized_body
                }
            }

        except requests.exceptions.Timeout as e:
            elapsed_ms = round((time.perf_counter() - start_time) * 1000, 2)
            return {
                "status_code": 408,
                "response_time_ms": elapsed_ms,
                "is_json": False,
                "data": None,
                "headers": {},
                "url": url,
                "method": method.upper(),
                "error": f"Request timed out after {req_timeout}s: {e}",
                "sanitized_request": {"headers": sanitized_headers, "body": sanitized_body}
            }

        except requests.exceptions.ConnectionError as e:
            elapsed_ms = round((time.perf_counter() - start_time) * 1000, 2)
            return {
                "status_code": 503,
                "response_time_ms": elapsed_ms,
                "is_json": False,
                "data": None,
                "headers": {},
                "url": url,
                "method": method.upper(),
                "error": f"Connection error occurred: {e}",
                "sanitized_request": {"headers": sanitized_headers, "body": sanitized_body}
            }

        except Exception as e:
            elapsed_ms = round((time.perf_counter() - start_time) * 1000, 2)
            return {
                "status_code": 500,
                "response_time_ms": elapsed_ms,
                "is_json": False,
                "data": None,
                "headers": {},
                "url": url,
                "method": method.upper(),
                "error": f"Unexpected request failure: {e}",
                "sanitized_request": {"headers": sanitized_headers, "body": sanitized_body}
            }

    def get(self, url: str, **kwargs) -> Dict[str, Any]:
        return self.request("GET", url, **kwargs)

    def post(self, url: str, **kwargs) -> Dict[str, Any]:
        return self.request("POST", url, **kwargs)

    def put(self, url: str, **kwargs) -> Dict[str, Any]:
        return self.request("PUT", url, **kwargs)

    def delete(self, url: str, **kwargs) -> Dict[str, Any]:
        return self.request("DELETE", url, **kwargs)
