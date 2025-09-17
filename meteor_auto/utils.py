from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any, Optional
from datetime import datetime, timezone


def ensure_dir(path: Path) -> None:
	path.mkdir(parents=True, exist_ok=True)


def setup_logging(log_dir: Path, console_level: int = logging.INFO) -> None:
	ensure_dir(log_dir)
	logger = logging.getLogger()
	if logger.handlers:
		return  # already configured
	logger.setLevel(logging.DEBUG)

	# File handler (rotating)
	file_handler = RotatingFileHandler(
		log_dir / "meteor-auto.log", maxBytes=5_000_000, backupCount=3
	)
	file_handler.setLevel(logging.DEBUG)
	file_fmt = logging.Formatter(
		"%(asctime)s [%(levelname)s] %(name)s: %(message)s", datefmt="%Y-%m-%dT%H:%M:%SZ"
	)
	file_handler.setFormatter(file_fmt)
	logger.addHandler(file_handler)

	# Console handler
	console_handler = logging.StreamHandler()
	console_handler.setLevel(console_level)
	console_fmt = logging.Formatter("%(levelname)s: %(message)s")
	console_handler.setFormatter(console_fmt)
	logger.addHandler(console_handler)


def utc_now() -> datetime:
	return datetime.now(timezone.utc)


def load_yaml_lazy(path: str | Path) -> Optional[dict[str, Any]]:
	# Lazy import to avoid hard dependency for --help
	try:
		import yaml  # type: ignore
	except Exception:
		return None
	p = Path(path)
	if not p.exists():
		return None
	with p.open("r", encoding="utf-8") as f:
		return yaml.safe_load(f)  # type: ignore[no-any-return]
