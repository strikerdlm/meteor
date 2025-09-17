# meteor-auto

Headless, reliable automation to predict METEOR-M N2-3/N2-4 passes (Bogotá: 4.7110, -74.0721), schedule SatDump live captures, and decode LRPT (OQPSK, 72 ksym/s). Designed for headless operation with retries, fallbacks, and systemd.

## What this does

- **Predict passes** for METEOR-M, NOAA APT/HRPT, and METOP AHRPT using Skyfield with Celestrak weather TLEs
- **Schedule SatDump** live runs per pass at a fixed center frequency (no LO Doppler correction)
- **Create outputs per pass** in timestamped directories
- **Handle fallbacks**: if recent runs fail to lock/produce frames, next pass tries alternate frequency/pipeline
- **One device at a time**: prevents overlapping runs via a lock file
- **Logs**: rotating file logs plus concise console output

Defaults reflect 2025 facts:

- LRPT/APT band ~137 MHz; HRPT/AHRPT around ~1700 MHz
- METEOR-M: LRPT 137.1/137.9 MHz; HRPT ~1700 MHz
- METOP-B/C: AHRPT 1701.3 MHz
- NOAA-15/19: APT/HRPT in 137 MHz / 1.7 GHz bands
- RTL-SDR v4 + bias-tee LNA (137 MHz SAW) recommended; 1.024 Msps stable; avoid 250 ksps

## Zero-to-first-pass (Windows & Linux)

1. Hardware
   - Plug the RTL-SDR (v4 recommended). For 137 MHz (LRPT/APT), use a V-dipole or QFH. For HRPT/AHRPT (~1.7 GHz), use an L-band dish/helix + LNA.
   - Optional: enable bias-tee if your LNA requires it.
2. Software
   - Install Python 3.10+ and SatDump CLI (verify with `satdump --version`).
   - Clone and install this repo in editable mode (see Quick start below).
3. Create a config
   - Copy `configs/config.example.yaml` to `configs/config.yaml` and adjust paths/QTH if needed.
4. Start the dashboard
   - `streamlit run scripts/streamlit_app.py`
   - In the sidebar, optionally load a `.env` for overrides. Confirm `Config path` points to your YAML.
5. Choose antenna and targets
   - In Pass prediction: pick an Antenna profile (e.g., “Dipole 137 MHz” for LRPT/APT or “L-band HRPT (dish)” for HRPT).
   - The target set (LRPT/HRPT/All) and a recommended minimum elevation will be prefilled.
6. Find passes
   - Click “Find passes” to fetch TLEs and compute upcoming passes for your QTH. Use “Dry-run schedule” to validate without capturing.
7. Headless scheduling (optional)
   - Keep the backend running via `meteor-auto run` (systemd/NSSM) for reliable unattended scheduling while the UI is used for planning.

### Dipole length helper (137 MHz)

- The app includes an Antenna helper popover to size a 137 MHz V-dipole:
  - Quarter-wave leg length per side: `0.25 * c / f * VF`. A common practical value at 137.9 MHz with VF≈0.95 is ~34.5 cm per leg (≈13.6 in). At 137.1 MHz it is ~35.0 cm (≈13.8 in).
  - Form a V at ~120°–135°, mount outdoors with clear sky view, and route coax away from the elements.
- HRPT/AHRPT requires an L-band dish/helix and is not suitable for a 137 MHz dipole.

## Quick start (Linux)

1. Install prerequisites
   - SatDump CLI in PATH (test with `satdump --version`)
   - Python 3.10+
   - Optional: `tl_biast` if you use bias-tee

2. Clone and install

```bash
git clone https://github.com/strikerdlm/meteor.git
cd meteor
python -m venv .venv
source .venv/bin/activate
pip install -e .
```

1. Configure

Copy the example and edit if needed:

```bash
mkdir -p configs
cp configs/config.example.yaml configs/config.yaml
```

Key defaults (see full reference below):

- QTH Bogotá: lat 4.7110, lon -74.0721, alt 2640 m
- Lookahead 24 h, min elevation 20°
- SatDump: samplerate 1.024 Msps; no AGC; gain 40 dB; optional `--bias`

1. Explore passes

```bash
meteor-auto --config configs/config.yaml list-passes --hours 6
```

If you see "No passes within lookahead window", try a larger window.

1. Run scheduler (dry-run first)

```bash
meteor-auto --config configs/config.yaml --lookahead 24 --min-elev 20 run --dry-run
```

Then actually schedule and run:

```bash
meteor-auto --config configs/config.yaml --lookahead 24 --min-elev 20 run
```

Outputs appear under `outputs/DATE_TIME_SAT/`. Logs go to `logs/meteor-auto.log`.

## Quick start (Windows PowerShell)

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e .
Copy-Item configs\config.example.yaml configs\config.yaml
meteor-auto --config configs\config.yaml list-passes --hours 6
```

## Configuration reference

Config can be YAML/JSON; env vars override fields.

Example (`configs/config.example.yaml`):

```yaml
qth:
  lat: 4.7110
  lon: -74.0721
  alt: 2640

lookahead: 24
min_elev: 20

frequencies:
  primary: 137900000
  backup: 137100000

pipelines:
  primary: meteor_m2-x_lrpt
  fallback: meteor_m2-x_lrpt_80k

satdump:
  path: satdump
  gain: 40
  bias: false
  samplerate: 1024000
  agc: false
  # http_bind: 0.0.0.0:8080

paths:
  outputs: outputs
  logs: logs
  cache: .cache
```

Environment variable overrides:

- METEOR_AUTO_LAT, METEOR_AUTO_LON, METEOR_AUTO_ALT_M
- METEOR_AUTO_LOOKAHEAD_H, METEOR_AUTO_MIN_ELEV_DEG
- METEOR_AUTO_FREQ_PRIMARY_HZ, METEOR_AUTO_FREQ_BACKUP_HZ
- METEOR_AUTO_GAIN_DB, METEOR_AUTO_BIAS_TEE, METEOR_AUTO_SAMPLERATE_SPS, METEOR_AUTO_SATDUMP_PATH
- METEOR_AUTO_OUTPUTS_DIR, METEOR_AUTO_LOGS_DIR, METEOR_AUTO_CACHE_DIR

### Optional: .env

You can place overrides in a `.env` file and load it via:

```bash
meteor-auto --env .env run --dry-run
```

Any variables in `.env` will be applied before the config file is loaded.

## How scheduling works

- Passes computed with Skyfield sampling every 10 s; sufficient with margins
- Capture starts ~120 s before AOS; timeout covers duration + pre/post margins
- Single SDR: a `capture.lock` prevents overlap; stale locks (>4 h) are removed
- Fallbacks after failures (no lock/frames): try backup frequency and 80k pipeline next time

## Hardware tips

- Antennas: V-dipole/QFH for 137 MHz LRPT/APT; L-band dish/helix + LNA for HRPT/AHRPT
- RF front-end: filtered LNA near antenna; avoid FM broadcast overload
- SDR: RTL-SDR v4 recommended; keep samplerate 1.024 Msps; avoid 250 ksps
- Do not Doppler-correct LO; keep center frequency fixed; Costas loop will handle small offset

## Streamlit UI (optional)

Local dashboard for configuration, pass prediction, dry-run scheduling, and log viewing.

Install (already included in `requirements.txt`):

```bash
pip install -r requirements.txt
```

Run the UI:

```bash
streamlit run scripts/streamlit_app.py
```

Notes:

- Keep the headless scheduler running separately for reliability (e.g., `meteor-auto run`).
- The UI reads/writes `configs/config.yaml` and respects env overrides (you can load a `.env`).
- Use the UI for planning/monitoring; captures are still executed by the backend.

## License

MIT
