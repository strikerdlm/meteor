from datetime import timedelta

from meteor_auto.predict import find_passes, ObserverQTH


def test_find_passes_smoke():
	# Single known satellite TLE (fabricated parameters but valid format)
	name = "METEOR-M N2-3"
	l1 = "1 12345U 24001A   25060.00000000  .00000000  00000-0  00000-0 0  9991"
	l2 = "2 12345 098.0000 200.0000 0001000  10.0000 350.0000 14.20600000100001"
	tles = {name: (l1, l2)}
	qth = ObserverQTH(latitude_deg=4.7110, longitude_deg=-74.0721, altitude_m=2640)
	# Run a very short lookahead to keep runtime small; result may be empty
	passes = find_passes(tles, qth, lookahead_hours=1, min_elev_deg=0.0, step_seconds=60)
	assert isinstance(passes, list)
	# We don't require non-empty; just ensure function executes
