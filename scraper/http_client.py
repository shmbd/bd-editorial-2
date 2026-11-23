"""Polite thread-safe HTTP client with robots.txt compliance, domain rate-limiting, and exponential backoff."""

from __future__ import annotations

import logging
import os
import random
import threading
import time
import urllib.robotparser
from urllib.parse import urlparse

import requests

logger = logging.getLogger(__name__)

DEFAULT_USER_AGENT = os.getenv(
    "BD_EDITORIALS_USER_AGENT",
    "BDEditorialsAggregator/1.0 (+https://github.com/bd-editorials/bd-editorials; ethical opinion index, max 120w summary)",
)


class EthicalFetchBlockedError(RuntimeError):
    """Raised when robots.txt, anti-bot challenge, or paywall forbids automated access."""


class PoliteHttpClient:
    """Thread-safe HTTP client enforcing robots.txt, 2-3s per-domain delay, and exponential backoff."""

    def __init__(
        self,
        user_agent: str = DEFAULT_USER_AGENT,
        min_delay_sec: float = 2.0,
        max_delay_sec: float = 3.0,
        max_retries: int = 3,
        timeout_sec: int = 20,
    ) -> None:
        self.user_agent = user_agent
        self.min_delay_sec = min_delay_sec
        self.max_delay_sec = max_delay_sec
        self.max_retries = max_retries
        self.timeout_sec = timeout_sec

        self._tls = threading.local()
        self._meta_lock = threading.Lock()
        self._domain_locks: dict[str, threading.Lock] = {}
        self._last_request_at: dict[str, float] = {}
        self._robots_cache: dict[str, urllib.robotparser.RobotFileParser | None] = {}

    def _get_session(self) -> requests.Session:
        sess = getattr(self._tls, "session", None)
        if sess is None:
            sess = requests.Session()
            sess.headers.update(
                {
                    "User-Agent": self.user_agent,
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                    "Accept-Language": "bn-BD,bn;q=0.9,en-US;q=0.8,en;q=0.7",
                }
            )
            self._tls.session = sess
        return sess

    def _get_domain_lock(self, netloc: str) -> threading.Lock:
        with self._meta_lock:
            lock = self._domain_locks.get(netloc)
            if lock is None:
                lock = threading.Lock()
                self._domain_locks[netloc] = lock
            return lock

    def _wait_for_domain(self, netloc: str) -> None:
        with self._get_domain_lock(netloc):
            last_ts = self._last_request_at.get(netloc)
            if last_ts is not None:
                target_gap = random.uniform(self.min_delay_sec, self.max_delay_sec)
                elapsed = time.monotonic() - last_ts
                if elapsed < target_gap:
                    time.sleep(target_gap - elapsed)
            self._last_request_at[netloc] = time.monotonic()

    def is_allowed_by_robots(self, url: str) -> bool:
        """Verify URL against the domain's robots.txt."""
        parsed = urlparse(url)
        origin = f"{parsed.scheme}://{parsed.netloc}"

        with self._get_domain_lock(f"robots:{origin}"):
            if origin not in self._robots_cache:
                rp = urllib.robotparser.RobotFileParser()
                robots_url = f"{origin}/robots.txt"
                try:
                    self._wait_for_domain(parsed.netloc)
                    resp = self._get_session().get(robots_url, timeout=self.timeout_sec)
                    if resp.status_code == 200:
                        rp.parse(resp.text.splitlines())
                        self._robots_cache[origin] = rp
                    elif resp.status_code in (401, 403):
                        if resp.headers.get("cf-mitigated") == "challenge":
                            raise EthicalFetchBlockedError(
                                f"Cloudflare anti-bot challenge active on {origin} (HTTP {resp.status_code})"
                            )
                        rp.disallow_all = True
                        self._robots_cache[origin] = rp
                    else:
                        self._robots_cache[origin] = None
                except EthicalFetchBlockedError:
                    raise
                except Exception as exc:
                    logger.warning("Could not fetch robots.txt for %s: %s", origin, exc)
                    self._robots_cache[origin] = None

        rp_cached = self._robots_cache.get(origin)
        if rp_cached is None:
            return True
        return rp_cached.can_fetch(self.user_agent, url) and rp_cached.can_fetch("*", url)

    def get(self, url: str, check_robots: bool = True) -> requests.Response:
        """Perform a polite GET request with robots check and exponential backoff."""
        if check_robots and not self.is_allowed_by_robots(url):
            raise EthicalFetchBlockedError(f"Disallowed by robots.txt: {url}")

        parsed = urlparse(url)
        last_exc: Exception | None = None
        session = self._get_session()

        for attempt in range(self.max_retries):
            self._wait_for_domain(parsed.netloc)
            try:
                resp = session.get(url, timeout=self.timeout_sec, allow_redirects=True)
                if resp.status_code in (401, 402, 403):
                    cf_mit = resp.headers.get("cf-mitigated", "")
                    reason = (
                        "Cloudflare anti-bot challenge"
                        if cf_mit == "challenge" or "Just a moment" in resp.text[:1000]
                        else f"HTTP {resp.status_code} access/paywall restriction"
                    )
                    raise EthicalFetchBlockedError(f"{reason} at {url}")

                if resp.status_code in (429, 500, 502, 503, 504):
                    backoff = (2 ** attempt) * 2.0 + random.uniform(0.2, 0.8)
                    logger.warning("Transient HTTP %s on %s; retrying in %.1fs", resp.status_code, url, backoff)
                    time.sleep(backoff)
                    continue

                resp.raise_for_status()
                ctype = resp.headers.get("Content-Type", "").lower()
                if "charset=" not in ctype:
                    resp.encoding = "utf-8"
                return resp
            except EthicalFetchBlockedError:
                raise
            except requests.RequestException as exc:
                last_exc = exc
                if attempt < self.max_retries - 1:
                    backoff = (2 ** attempt) * 2.0 + random.uniform(0.2, 0.8)
                    logger.warning("Request error on %s (%s); retrying in %.1fs", url, exc, backoff)
                    time.sleep(backoff)

        raise RuntimeError(f"Failed to fetch {url} after {self.max_retries} attempts: {last_exc}")
