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
			logger.warning("TLE fetch failed (attempt %d/%d): %s", attempt, backoff_attempts, e)
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


def select_meteor_targets(tles: Dict[str, Tuple[str, str]]) -> Dict[str, Tuple[str, str]]:
	selected: Dict[str, Tuple[str, str]] = {}
	for name, pair in tles.items():
		upper = name.upper()
		if any(p in upper for p in _METEOR_PATTERNS):
			selected[name] = pair
	return selected
