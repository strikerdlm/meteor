from meteor_auto.tle import parse_tles, select_meteor_targets


def test_parse_and_select():
	text = """
METEOR-M N2-3
1 12345U 24001A   25060.00000000  .00000000  00000-0  00000-0 0  9991
2 12345 098.0000 200.0000 0001000  10.0000 350.0000 14.20600000100001
NOAA 19
1 33591U 09005A   25060.00000000  .00000000  00000-0  00000-0 0  9990
2 33591 099.0000 210.0000 0010000  20.0000 340.0000 14.12300000100002
"""
	triples = parse_tles(text)
	assert "METEOR-M N2-3" in triples
	sel = select_meteor_targets(triples)
	assert any("METEOR" in name.upper() for name in sel.keys())
