"""
Streamlit UI for meteor-auto

This app provides a local dashboard to:
- View and edit config (YAML)
- Predict passes for the next N hours
- Perform a dry-run schedule to verify jobs that would be scheduled
- View recent logs

It does NOT replace the headless scheduler. Keep running
`meteor-auto run` (e.g., via systemd/NSSM) for reliability.
"""

from __future__ import annotations

import io
import logging
from dataclasses import asdict
from datetime import timezone
from pathlib import Path
from typing import Any, Dict, List

import streamlit as st

from meteor_auto.config import Config, load_config
from meteor_auto.predict import ObserverQTH, find_passes
from meteor_auto.tle import fetch_tles, parse_tles, select_meteor_targets
from meteor_auto.scheduler import PassScheduler
from meteor_auto.utils import ensure_dir, load_yaml_lazy, setup_logging, load_dotenv_if_present


# ---------- Helpers ----------

def get_default_config_path() -> Path:
    candidates = [
        Path("configs/config.yaml"),
        Path("configs/config.example.yaml"),
    ]
    for p in candidates:
        if p.exists():
            return p
    return candidates[0]


def config_to_mapping(cfg: Config) -> Dict[str, Any]:
    return {
        "qth": {
            "lat": cfg.qth.latitude_deg,
            "lon": cfg.qth.longitude_deg,
            "alt": cfg.qth.altitude_m,
        },
        "lookahead": cfg.lookahead_hours,
        "min_elev": cfg.min_elevation_deg,
        "frequencies": {
            "primary": cfg.frequencies.primary_hz,
            "backup": cfg.frequencies.backup_hz,
        },
        "pipelines": {
            "primary": cfg.pipelines.primary,
            "fallback": cfg.pipelines.fallback,
        },
        "satdump": {
            "path": cfg.satdump.path,
            "gain": cfg.satdump.gain_db,
            "bias": cfg.satdump.bias_tee,
            "samplerate": int(cfg.satdump.sample_rate_sps),
            "agc": cfg.satdump.enable_agc,
            "http_bind": cfg.satdump.http_bind,
        },
        "paths": {
            "outputs": cfg.paths.outputs_dir,
            "logs": cfg.paths.logs_dir,
            "cache": cfg.paths.cache_dir,
        },
    }


def write_config_yaml(path: Path, data: Dict[str, Any]) -> None:
    try:
        import yaml  # type: ignore
    except Exception as e:
        raise RuntimeError("PyYAML is required to write config") from e
    ensure_dir(path.parent)
    with path.open("w", encoding="utf-8") as f:
        yaml.safe_dump(data, f, sort_keys=False)


def tail_text_file(path: Path, max_bytes: int = 20000) -> str:
    if not path.exists():
        return "(log file not found)"
    size = path.stat().st_size
    with path.open("rb") as f:
        if size > max_bytes:
            f.seek(-max_bytes, 2)
        data = f.read()
    try:
        return data.decode("utf-8", errors="replace")
    except Exception:
        return data.decode("latin-1", errors="replace")


# ---------- UI ----------

st.set_page_config(page_title="meteor-auto", layout="wide")

with st.sidebar:
    st.title("meteor-auto")
    st.caption("Local dashboard (control/monitor)")

    # Load .env if provided
    dotenv_file = st.text_input(".env path (optional)", value="")
    if st.button("Load .env", type="secondary"):
        load_dotenv_if_present(dotenv_file or None)
        st.success(".env loaded (if present)")

    # Config path
    cfg_path_str = st.text_input(
        "Config path",
        value=str(get_default_config_path()),
        help="Path to YAML config. Will be created if missing.",
    )
    cfg_path = Path(cfg_path_str)

    # Logging setup
    cfg_for_logs = load_config(str(cfg_path) if cfg_path.exists() else None)
    ensure_dir(Path(cfg_for_logs.paths.logs_dir))
    setup_logging(Path(cfg_for_logs.paths.logs_dir), console_level=logging.INFO)


st.header("Configuration")

cfg = load_config(str(cfg_path) if cfg_path.exists() else None)
cfg_map = config_to_mapping(cfg)

with st.form("cfg_form"):
    col1, col2, col3 = st.columns(3)
    with col1:
        cfg_map["qth"]["lat"] = st.number_input("Lat (deg)", value=float(cfg_map["qth"]["lat"]))
        cfg_map["lookahead"] = st.number_input("Lookahead (h)", value=int(cfg_map["lookahead"]))
        cfg_map["frequencies"]["primary"] = st.number_input(
            "Primary freq (Hz)", value=float(cfg_map["frequencies"]["primary"])  # type: ignore[arg-type]
        )
        cfg_map["pipelines"]["primary"] = st.text_input("Primary pipeline", value=cfg_map["pipelines"]["primary"])  # type: ignore[index]
        cfg_map["paths"]["outputs"] = st.text_input("Outputs dir", value=cfg_map["paths"]["outputs"])  # type: ignore[index]
    with col2:
        cfg_map["qth"]["lon"] = st.number_input("Lon (deg)", value=float(cfg_map["qth"]["lon"]))
        cfg_map["min_elev"] = st.number_input("Min elevation (deg)", value=float(cfg_map["min_elev"]))
        cfg_map["frequencies"]["backup"] = st.number_input(
            "Backup freq (Hz)", value=float(cfg_map["frequencies"]["backup"])  # type: ignore[arg-type]
        )
        cfg_map["pipelines"]["fallback"] = st.text_input("Fallback pipeline", value=cfg_map["pipelines"]["fallback"])  # type: ignore[index]
        cfg_map["paths"]["logs"] = st.text_input("Logs dir", value=cfg_map["paths"]["logs"])  # type: ignore[index]
    with col3:
        cfg_map["qth"]["alt"] = st.number_input("Alt (m)", value=float(cfg_map["qth"]["alt"]))
        cfg_map["satdump"]["path"] = st.text_input("SatDump path", value=cfg_map["satdump"]["path"])  # type: ignore[index]
        cfg_map["satdump"]["gain"] = st.number_input("Gain (dB)", value=float(cfg_map["satdump"]["gain"]))
        cfg_map["satdump"]["bias"] = st.checkbox("Bias-tee", value=bool(cfg_map["satdump"]["bias"]))
        cfg_map["satdump"]["samplerate"] = st.number_input("Samplerate (sps)", value=int(cfg_map["satdump"]["samplerate"]))
        cfg_map["satdump"]["agc"] = st.checkbox("Enable AGC", value=bool(cfg_map["satdump"]["agc"]))
        cfg_map["satdump"]["http_bind"] = st.text_input("HTTP bind (optional)", value=str(cfg_map["satdump"]["http_bind"] or ""))
        cfg_map["paths"]["cache"] = st.text_input("Cache dir", value=cfg_map["paths"]["cache"])  # type: ignore[index]

    submitted = st.form_submit_button("Save config")
    if submitted:
        try:
            write_config_yaml(cfg_path, cfg_map)
            st.success(f"Saved: {cfg_path}")
        except Exception as e:
            st.error(f"Failed to save config: {e}")


st.divider()
st.header("Pass prediction")

hours_override = st.number_input("Hours (override)", value=cfg.lookahead_hours, min_value=1, max_value=168)
min_elev_override = st.number_input("Min elevation (deg)", value=cfg.min_elevation_deg, min_value=0.0, max_value=90.0)

if st.button("Find passes"):
    with st.spinner("Fetching TLEs and computing passes..."):
        cache_dir = Path(cfg.paths.cache_dir)
        ensure_dir(cache_dir)
        text = fetch_tles(cache_dir)
        triples = parse_tles(text)
        targets = select_meteor_targets(triples)
        if not targets:
            st.warning("No METEOR targets found in TLE set.")
        else:
            qth = ObserverQTH(
                latitude_deg=cfg.qth.latitude_deg,
                longitude_deg=cfg.qth.longitude_deg,
                altitude_m=cfg.qth.altitude_m,
            )
            passes = find_passes(targets, qth, int(hours_override), float(min_elev_override))
            if not passes:
                st.info("No passes within lookahead window.")
            else:
                rows: List[Dict[str, Any]] = []
                for p in passes:
                    rows.append(
                        {
                            "satellite": p.satellite_name,
                            "aos": p.aos.astimezone(timezone.utc).isoformat(),
                            "tca": p.tca.astimezone(timezone.utc).isoformat(),
                            "los": p.los.astimezone(timezone.utc).isoformat(),
                            "max_el_deg": round(p.max_elevation_deg, 1),
                            "duration_s": p.duration_sec,
                        }
                    )
                st.dataframe(rows, use_container_width=True)

                if st.button("Dry-run schedule these passes"):
                    with st.spinner("Planning schedule (dry-run)..."):
                        scheduler = PassScheduler(cfg)
                        try:
                            scheduler.schedule_passes(passes, dry_run=True)
                            st.success("Dry-run complete. See logs for details.")
                        except Exception as e:
                            st.error(f"Dry-run failed: {e}")


st.divider()
st.header("Logs")

log_path = Path(cfg.paths.logs_dir) / "meteor-auto.log"
col_a, col_b = st.columns([1, 6])
with col_a:
    if st.button("Refresh logs"):
        st.experimental_rerun()
with col_b:
    log_text = tail_text_file(log_path)
    st.code(log_text, language="log")


