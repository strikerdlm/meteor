from meteor_auto.config import load_config


def test_env_overrides(monkeypatch):
	monkeypatch.setenv("METEOR_AUTO_LOOKAHEAD_H", "12")
	monkeypatch.setenv("METEOR_AUTO_MIN_ELEV_DEG", "30")
	cfg = load_config(None)
	assert cfg.lookahead_hours == 12
	assert cfg.min_elevation_deg == 30


def test_file_merge(tmp_path):
	cfg_file = tmp_path / "cfg.yaml"
	cfg_file.write_text(
		"""
		qth:
		  lat: 10
		  lon: -70
		  alt: 100
		lookahead: 6
		min_elev: 15
		""",
		encoding="utf-8",
	)
	cfg = load_config(str(cfg_file))
	assert cfg.qth.latitude_deg == 10
	assert cfg.qth.longitude_deg == -70
	assert cfg.qth.altitude_m == 100
	assert cfg.lookahead_hours == 6
	assert cfg.min_elevation_deg == 15
