"""Google Jules REST API Client.

Handles HTTP requests, authentication via X-Goog-Api-Key, robust retries
with exponential backoff and jitter, status code inspection, and automatic
pagination iteration.
"""

from __future__ import annotations
import json
import logging
import random
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Dict, Generator, Iterator, List, Optional

from .models import Activity, Session, Source

logger = logging.getLogger(__name__)

DEFAULT_BASE_URL = "https://jules.googleapis.com"
DEFAULT_PAGE_SIZE = 100
MAX_RETRIES = 5
INITIAL_BACKOFF = 1.0
BACKOFF_FACTOR = 2.0
MAX_BACKOFF = 32.0


class JulesAPIError(Exception):
    """Exception raised when Jules API returns an error."""

    def __init__(self, message: str, status_code: Optional[int] = None, response_body: Optional[str] = None):
        super().__init__(message)
        self.status_code = status_code
        self.response_body = response_body


class JulesClient:
    """Client for Google Jules API v1alpha."""

    def __init__(
        self,
        api_key: str,
        base_url: str = DEFAULT_BASE_URL,
        timeout: float = 30.0,
        max_retries: int = MAX_RETRIES,
        initial_backoff: float = INITIAL_BACKOFF,
        rate_limit_delay: float = 0.05,
    ):
        if not api_key or not api_key.strip():
            raise ValueError("API key must be provided and non-empty")
        self.api_key = api_key.strip()
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.max_retries = max_retries
        self.initial_backoff = initial_backoff
        self.rate_limit_delay = rate_limit_delay

    def _get_headers(self) -> Dict[str, str]:
        return {
            "X-Goog-Api-Key": self.api_key,
            "Accept": "application/json",
            "User-Agent": "Google-Jules-Exporter/1.0",
        }

    def _request(
        self,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None,
        method: str = "GET",
    ) -> Dict[str, Any]:
        """Performs HTTP request with exponential backoff and jitter for transient errors."""
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        if params:
            clean_params = {k: v for k, v in params.items() if v is not None}
            if clean_params:
                url = f"{url}?{urllib.parse.urlencode(clean_params)}"

        headers = self._get_headers()
        req = urllib.request.Request(url, headers=headers, method=method)

        backoff = self.initial_backoff
        for attempt in range(1, self.max_retries + 1):
            try:
                if self.rate_limit_delay > 0:
                    time.sleep(self.rate_limit_delay)

                with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                    raw_body = resp.read().decode("utf-8")
                    if not raw_body.strip():
                        return {}
                    return json.loads(raw_body)

            except urllib.error.HTTPError as e:
                status_code = e.code
                error_body = ""
                try:
                    error_body = e.read().decode("utf-8", errors="replace")
                except Exception:
                    pass

                # Transient errors: 429 (Too Many Requests), 500, 502, 503, 504
                is_transient = status_code in (429, 500, 502, 503, 504)
                if is_transient and attempt < self.max_retries:
                    # Parse Retry-After if available
                    retry_after = e.headers.get("Retry-After") if e.headers else None
                    sleep_time = float(retry_after) if retry_after and retry_after.isdigit() else backoff
                    sleep_time += random.uniform(0.05, 0.25)  # add jitter
                    logger.warning(
                        "Received HTTP %d for %s (attempt %d/%d). Retrying in %.2fs...",
                        status_code,
                        url,
                        attempt,
                        self.max_retries,
                        sleep_time,
                    )
                    time.sleep(sleep_time)
                    backoff = min(backoff * BACKOFF_FACTOR, MAX_BACKOFF)
                    continue

                logger.error(
                    "HTTP %d error requesting %s: %s",
                    status_code,
                    url,
                    error_body,
                )
                raise JulesAPIError(
                    f"HTTP {status_code}: {error_body}",
                    status_code=status_code,
                    response_body=error_body,
                ) from e

            except (urllib.error.URLError, TimeoutError, OSError) as e:
                if attempt < self.max_retries:
                    sleep_time = backoff + random.uniform(0.05, 0.25)
                    logger.warning(
                        "Network error %s requesting %s (attempt %d/%d). Retrying in %.2fs...",
                        str(e),
                        url,
                        attempt,
                        self.max_retries,
                        sleep_time,
                    )
                    time.sleep(sleep_time)
                    backoff = min(backoff * BACKOFF_FACTOR, MAX_BACKOFF)
                    continue

                logger.error("Network error requesting %s: %s", url, str(e))
                raise JulesAPIError(f"Network error: {str(e)}") from e

        raise JulesAPIError(f"Failed request to {url} after {self.max_retries} attempts")

    def paginate(
        self,
        endpoint: str,
        items_key: str,
        page_size: int = DEFAULT_PAGE_SIZE,
        extra_params: Optional[Dict[str, Any]] = None,
    ) -> Generator[Dict[str, Any], None, None]:
        """Automatically follows nextPageToken until all items have been yielded."""
        params: Dict[str, Any] = {"pageSize": page_size}
        if extra_params:
            params.update(extra_params)

        page_token: Optional[str] = None
        while True:
            if page_token:
                params["pageToken"] = page_token
            elif "pageToken" in params:
                del params["pageToken"]

            response = self._request(endpoint, params=params)
            items = response.get(items_key, [])
            for item in items:
                yield item

            page_token = response.get("nextPageToken")
            if not page_token:
                break

    def list_sessions(self, page_size: int = DEFAULT_PAGE_SIZE) -> Iterator[Session]:
        """Yields all Session objects automatically paginating through all available pages."""
        for item in self.paginate("v1alpha/sessions", items_key="sessions", page_size=page_size):
            yield Session.from_dict(item)

    def get_session(self, session_id: str) -> Session:
        """Fetches a single session by id or name."""
        clean_id = session_id.replace("sessions/", "").strip()
        data = self._request(f"v1alpha/sessions/{clean_id}")
        return Session.from_dict(data)

    def list_activities(self, session_id: str, page_size: int = DEFAULT_PAGE_SIZE) -> Iterator[Activity]:
        """Yields all Activity objects for a session, automatically handling pagination."""
        clean_id = session_id.replace("sessions/", "").strip()
        endpoint = f"v1alpha/sessions/{clean_id}/activities"
        for item in self.paginate(endpoint, items_key="activities", page_size=page_size):
            yield Activity.from_dict(item)

    def get_activity(self, session_id: str, activity_id: str) -> Activity:
        """Fetches a single activity."""
        clean_s_id = session_id.replace("sessions/", "").strip()
        clean_a_id = activity_id.replace(f"sessions/{clean_s_id}/activities/", "").strip()
        data = self._request(f"v1alpha/sessions/{clean_s_id}/activities/{clean_a_id}")
        return Activity.from_dict(data)

    def list_sources(self, page_size: int = DEFAULT_PAGE_SIZE) -> Iterator[Source]:
        """Yields all Source objects connected to Jules."""
        for item in self.paginate("v1alpha/sources", items_key="sources", page_size=page_size):
            yield Source.from_dict(item)
