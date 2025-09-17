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
		log_dir / "meteor-auto.log",
		maxBytes=5_000_000,
		backupCount=3,
	)
	file_handler.setLevel(logging.DEBUG)
	file_fmt = logging.Formatter(
		"%(asctime)s [%(levelname)s] %(name)s: %(message)s",
		datefmt="%Y-%m-%dT%H:%M:%SZ",
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
	# Read and normalize leading tabs to spaces for YAML compliance
	text = p.read_text(encoding="utf-8")
	lines: list[str] = []
	for line in text.splitlines():
		j = 0
		while j < len(line) and line[j] == "\t":
			j += 1
		if j:
			line = ("  " * j) + line[j:]
		lines.append(line)
	normalized = "\n".join(lines)
	return yaml.safe_load(normalized)  # type: ignore[no-any-return]


def load_dotenv_if_present(env_path: Optional[str | Path] = None) -> None:
	"""Load environment variables from a .env file if python-dotenv is available.

	If `env_path` is provided, it will be used as the dotenv path; otherwise the
	default dotenv discovery is used.
	"""
	try:
		from dotenv import load_dotenv  # type: ignore
	except Exception:
		return
	try:
		if env_path is not None:
			load_dotenv(dotenv_path=str(env_path))
		else:
			load_dotenv()
	except Exception:
		# Ignore dotenv errors to keep CLI robust
		pass
