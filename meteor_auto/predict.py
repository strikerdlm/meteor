from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import List, Tuple, Dict

from skyfield.api import EarthSatellite, load, wgs84


@dataclass
class ObserverQTH:
	latitude_deg: float
	longitude_deg: float
	altitude_m: float


@dataclass
class PassEvent:
	satellite_name: str
	aos: datetime
	tca: datetime
	los: datetime
	max_elevation_deg: float
	duration_sec: int


def _to_ts(ts, dt: datetime):
	if dt.tzinfo is None:
		dt = dt.replace(tzinfo=timezone.utc)
	return ts.utc(dt)


def _elevation_deg(sat: EarthSatellite, qth: ObserverQTH, ts, t):
	observer = wgs84.latlon(qth.latitude_deg, qth.longitude_deg, elevation_m=qth.altitude_m)
	topocentric = (sat - observer).at(t)
	_, el, _ = topocentric.altaz()
	return float(el.degrees)


def find_passes(
	sat_name_to_tle: Dict[str, Tuple[str, str]],
	qth: ObserverQTH,
	lookahead_hours: int,
	min_elev_deg: float,
	step_seconds: int = 10,
) -> List[PassEvent]:
	"""
	Simple brute-force pass prediction by sampling elevations every step_seconds.
	Sufficient for scheduling within seconds accuracy when using generous margins.
	"""
	ts = load.timescale()
	start = datetime.now(timezone.utc)
	end = start + timedelta(hours=lookahead_hours)
	
	passes: List[PassEvent] = []

	for sat_name, (l1, l2) in sat_name_to_tle.items():
		sat = EarthSatellite(l1, l2, sat_name, ts)
		t = start
		in_pass = False
		aos_dt = None
		peak_el = -90.0
		peak_time = None
		while t <= end:
			elev = _elevation_deg(sat, qth, ts, _to_ts(ts, t))
			if elev >= 0.0 and not in_pass:
				# horizon crossing
				in_pass = True
				aos_dt = t
				peak_el = elev
				peak_time = t
			elif in_pass:
				if elev > peak_el:
					peak_el = elev
					peak_time = t
				if elev < 0.0:
					# End of pass
					los_dt = t
					if peak_el >= min_elev_deg and aos_dt is not None and peak_time is not None:
						passes.append(
							PassEvent(
								satellite_name=sat_name,
								aos=aos_dt,
								tca=peak_time,
								los=los_dt,
								max_elevation_deg=peak_el,
								duration_sec=int((los_dt - aos_dt).total_seconds()),
							)
						)
					# Reset
					in_pass = False
					aos_dt = None
					peak_el = -90.0
					peak_time = None
			t += timedelta(seconds=step_seconds)

	# Sort by AOS
	passes.sort(key=lambda p: p.aos)
	return passes
