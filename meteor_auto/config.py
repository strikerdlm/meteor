from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Optional

from .utils import load_yaml_lazy


@dataclass
class QTH:
	latitude_deg: float = 4.7110
	longitude_deg: float = -74.0721
	altitude_m: float = 2640.0


@dataclass
class Frequencies:
	primary_hz: float = 137_900_000.0
	backup_hz: float = 137_100_000.0


@dataclass
class Pipelines:
	primary: str = "meteor_m2-x_lrpt"
	fallback: str = "meteor_m2-x_lrpt_80k"


@dataclass
class Satdump:
	path: str = "satdump"
	gain_db: float = 40.0
	bias_tee: bool = False
	sample_rate_sps: float = 1.024e6
	enable_agc: bool = False
	http_bind: Optional[str] = None  # e.g. "0.0.0.0:8080"


@dataclass
class Paths:
	outputs_dir: str = "outputs"
	logs_dir: str = "logs"
	cache_dir: str = ".cache"


@dataclass
class Config:
	qth: QTH = field(default_factory=QTH)
	frequencies: Frequencies = field(default_factory=Frequencies)
	pipelines: Pipelines = field(default_factory=Pipelines)
	satdump: Satdump = field(default_factory=Satdump)
	paths: Paths = field(default_factory=Paths)
	lookahead_hours: int = 24
	min_elevation_deg: float = 20.0
	timezone: str = "UTC"


_ENV_MAP = {
	"METEOR_AUTO_LAT": ("qth", "latitude_deg", float),
	"METEOR_AUTO_LON": ("qth", "longitude_deg", float),
	"METEOR_AUTO_ALT_M": ("qth", "altitude_m", float),
	"METEOR_AUTO_LOOKAHEAD_H": ("lookahead_hours", None, int),
	"METEOR_AUTO_MIN_ELEV_DEG": ("min_elevation_deg", None, float),
	"METEOR_AUTO_GAIN_DB": ("satdump", "gain_db", float),
	"METEOR_AUTO_BIAS_TEE": ("satdump", "bias_tee", lambda v: str(v).lower() in {"1", "true", "yes", "on"}),
	"METEOR_AUTO_FREQ_PRIMARY_HZ": ("frequencies", "primary_hz", float),
	"METEOR_AUTO_FREQ_BACKUP_HZ": ("frequencies", "backup_hz", float),
	"METEOR_AUTO_SAMPLERATE_SPS": ("satdump", "sample_rate_sps", float),
	"METEOR_AUTO_OUTPUTS_DIR": ("paths", "outputs_dir", str),
	"METEOR_AUTO_LOGS_DIR": ("paths", "logs_dir", str),
	"METEOR_AUTO_CACHE_DIR": ("paths", "cache_dir", str),
	"METEOR_AUTO_SATDUMP_PATH": ("satdump", "path", str),
}


def _apply_env_overrides(cfg: Config, env: Optional[dict] = None) -> Config:
	env = env or os.environ
	for key, (section, field_name, caster) in _ENV_MAP.items():
		if key not in env:
			continue
		value = caster(env[key])
		if field_name is None:
			setattr(cfg, section, value)
		else:
			section_obj = getattr(cfg, section)
			setattr(section_obj, field_name, value)
	return cfg


def _merge_from_mapping(cfg: Config, data: dict) -> Config:
	# Shallow merge for known sections
	if "qth" in data:
		q = data["qth"]
		cfg.qth.latitude_deg = float(q.get("lat", q.get("latitude", cfg.qth.latitude_deg)))
		cfg.qth.longitude_deg = float(q.get("lon", q.get("longitude", cfg.qth.longitude_deg)))
		cfg.qth.altitude_m = float(q.get("alt", q.get("altitude", cfg.qth.altitude_m)))
	if "lookahead" in data:
		cfg.lookahead_hours = int(data["lookahead"])
	if "min_elev" in data:
		cfg.min_elevation_deg = float(data["min_elev"])
	if "frequencies" in data:
		f = data["frequencies"]
		cfg.frequencies.primary_hz = float(f.get("primary", cfg.frequencies.primary_hz))
		cfg.frequencies.backup_hz = float(f.get("backup", cfg.frequencies.backup_hz))
	if "pipelines" in data:
		p = data["pipelines"]
		cfg.pipelines.primary = str(p.get("primary", cfg.pipelines.primary))
		cfg.pipelines.fallback = str(p.get("fallback", cfg.pipelines.fallback))
	if "satdump" in data:
		s = data["satdump"]
		cfg.satdump.path = str(s.get("path", cfg.satdump.path))
		cfg.satdump.gain_db = float(s.get("gain", s.get("gain_db", cfg.satdump.gain_db)))
		cfg.satdump.bias_tee = bool(s.get("bias", s.get("bias_tee", cfg.satdump.bias_tee)))
		cfg.satdump.sample_rate_sps = float(
			s.get("samplerate", s.get("sample_rate_sps", cfg.satdump.sample_rate_sps))
		)
		cfg.satdump.enable_agc = bool(s.get("agc", s.get("enable_agc", cfg.satdump.enable_agc)))
		cfg.satdump.http_bind = s.get("http_bind", cfg.satdump.http_bind)
	if "paths" in data:
		p = data["paths"]
		cfg.paths.outputs_dir = str(p.get("outputs", p.get("outputs_dir", cfg.paths.outputs_dir)))
		cfg.paths.logs_dir = str(p.get("logs", p.get("logs_dir", cfg.paths.logs_dir)))
		cfg.paths.cache_dir = str(p.get("cache", p.get("cache_dir", cfg.paths.cache_dir)))
	return cfg


def load_config(path: Optional[str] = None, env: Optional[dict] = None) -> Config:
	cfg = Config()
	if path:
		data = load_yaml_lazy(path)
		if isinstance(data, dict):
			cfg = _merge_from_mapping(cfg, data)
	cfg = _apply_env_overrides(cfg, env)
	return cfg
