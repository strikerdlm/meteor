from __future__ import annotations

import time
import logging
from pathlib import Path
from typing import Dict, List, Tuple, Optional

import requests

DEFAULT_TLE_URL = "https://celestrak.org/NORAD/elements/weather.txt"

logger = logging.getLogger(__name__)


def _is_fresh(path: Path, max_age_hours: int) -> bool:
    if not path.exists():
        return False
    age_seconds = time.time() - path.stat().st_mtime
    return age_seconds <= max_age_hours * 3600


def fetch_tles(
    cache_dir: Path,
    url: str = DEFAULT_TLE_URL,
    max_age_hours: int = 6,
    timeout_sec: int = 10,
    backoff_attempts: int = 3,
) -> str:
    """
    Fetch TLE catalog text with on-disk caching and simple backoff.

    If network fetch fails, returns the cached copy if available.
    """
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache_file = cache_dir / "weather.tle"

    if _is_fresh(cache_file, max_age_hours):
        try:
            return cache_file.read_text(encoding="utf-8")
        except Exception:
            pass

    last_err: Optional[Exception] = None
    for attempt in range(1, backoff_attempts + 1):
        try:
            logger.info("Fetching TLEs from %s (attempt %d)", url, attempt)
            resp = requests.get(url, timeout=timeout_sec)
            resp.raise_for_status()
            text = resp.text
            cache_file.write_text(text, encoding="utf-8")
            return text
        except Exception as e:
            last_err = e
            logger.warning(
                "TLE fetch failed (attempt %d/%d): %s",
                attempt,
                backoff_attempts,
                e,
            )
            time.sleep(min(2 ** attempt, 8))

    logger.error("TLE fetch failed. Using cached copy if available.")
    if cache_file.exists():
        return cache_file.read_text(encoding="utf-8")
    raise RuntimeError(f"Unable to fetch TLEs from {url}: {last_err}")


def parse_tles(text: str) -> Dict[str, Tuple[str, str]]:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    triples: Dict[str, Tuple[str, str]] = {}
    i = 0
    while i + 2 < len(lines):
        name = lines[i]
        l1 = lines[i + 1]
        l2 = lines[i + 2]
        if l1.startswith("1 ") and l2.startswith("2 "):
            triples[name] = (l1, l2)
            i += 3
        else:
            i += 1
    return triples


_METEOR_PATTERNS: List[str] = [
    "METEOR-M N2-3",
    "METEOR-M N2-4",
    "METEOR-M2 3",
    "METEOR-M2 4",
    "METEOR-M2-3",
    "METEOR-M2-4",
]

# NOAA APT/HRPT naming patterns (per SatDump satellite list and SatNOGS)
_NOAA_PATTERNS: List[str] = [
    "NOAA 15",
    "NOAA-15",
    "NOAA 19",
    "NOAA-19",
]

# METOP AHRPT naming patterns
_METOP_PATTERNS: List[str] = [
    "METOP-B",
    "METOP C",
    "METOP-C",
]


def select_meteor_targets(
    tles: Dict[str, Tuple[str, str]]
) -> Dict[str, Tuple[str, str]]:
    selected: Dict[str, Tuple[str, str]] = {}
    for name, pair in tles.items():
        upper = name.upper()
        if any(p in upper for p in _METEOR_PATTERNS):
            selected[name] = pair
    return selected


def select_targets(
    tles: Dict[str, Tuple[str, str]],
    bands: str = "lrpt",
) -> Dict[str, Tuple[str, str]]:
    """
    Select LRPT/APT/HRPT-capable targets known to work with SatDump.

    bands: "lrpt" | "hrpt" | "all"
      - lrpt: METEOR-M N2-3/N2-4, NOAA APT (15/19)
      - hrpt: METOP-B/C (AHRPT), NOAA HRPT (15/19)
      - all: union of both
    """
    bands = bands.lower()
    selected: Dict[str, Tuple[str, str]] = {}
    for name, pair in tles.items():
        u = name.upper()
        is_meteor = any(p in u for p in _METEOR_PATTERNS)
        is_noaa = any(p in u for p in _NOAA_PATTERNS)
        is_metop = any(p in u for p in _METOP_PATTERNS)

        if bands == "lrpt":
            if is_meteor or is_noaa:
                selected[name] = pair
        elif bands == "hrpt":
            if is_metop or is_noaa:
                selected[name] = pair
        else:  # all
            if is_meteor or is_noaa or is_metop:
                selected[name] = pair
    return selected
