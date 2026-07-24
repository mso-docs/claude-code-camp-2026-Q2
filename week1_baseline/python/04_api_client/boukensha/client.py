from __future__ import annotations

import json
import socket
import ssl
import time
import urllib.error
import urllib.request
from http.client import RemoteDisconnected

from .errors import ApiError

RETRYABLE_STATUS_CODES = {408, 409, 429, 500, 502, 503, 504}
# Ruby's TRANSIENT_ERRORS list, translated: connection-level failures worth
# retrying rather than failing immediately on. urllib usually wraps these in
# URLError, but we catch the underlying types too in case they surface raw.
TRANSIENT_ERRORS = (
    EOFError,
    ConnectionResetError,
    ConnectionRefusedError,
    RemoteDisconnected,
    socket.timeout,
    ssl.SSLError,
    urllib.error.URLError,
)
MAX_RETRIES = 3
BASE_RETRY_DELAY = 0.5


class Client:
    """POSTs a PromptBuilder's payload and returns the parsed JSON response."""

    def __init__(self, builder) -> None:
        self.builder = builder

    def call(self, *, max_output_tokens: int = 1024) -> dict:
        url = self.builder.url()
        headers = self.builder.headers()
        body = json.dumps(
            self.builder.to_api_payload(max_output_tokens=max_output_tokens)
        ).encode("utf-8")

        attempts = 0
        while True:
            attempts += 1
            request = urllib.request.Request(url, data=body, headers=headers, method="POST")
            try:
                # urlopen creates a default SSL context (system CA store) for
                # https:// URLs automatically — no ca_file workaround needed.
                with urllib.request.urlopen(request) as response:
                    return json.loads(response.read())
            except urllib.error.HTTPError as e:
                response_body = e.read().decode("utf-8", errors="replace")
                if e.code in RETRYABLE_STATUS_CODES and attempts <= MAX_RETRIES:
                    time.sleep(self._retry_delay(attempts))
                    continue
                suffix = "" if attempts == 1 else "s"
                raise ApiError(
                    f"API request failed after {attempts} attempt{suffix} ({e.code}): {response_body}"
                ) from e
            except TRANSIENT_ERRORS as e:
                if attempts > MAX_RETRIES:
                    raise ApiError(
                        f"API request failed after {attempts} attempts: {type(e).__name__}: {e}"
                    ) from e
                time.sleep(self._retry_delay(attempts))
                continue

    @staticmethod
    def _retry_delay(attempt: int) -> float:
        return BASE_RETRY_DELAY * (2 ** (attempt - 1))
