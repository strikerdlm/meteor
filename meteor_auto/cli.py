import argparse
import sys
from pathlib import Path
from typing import Optional

from . import __version__
from .config import Config, load_config
from .utils import ensure_dir, setup_logging
from .tle import fetch_tles, parse_tles, select_meteor_targets
from .predict import find_passes, ObserverQTH


def build_parser() -> argparse.ArgumentParser:
	parser = argparse.ArgumentParser(
		prog="meteor-auto",
		description=(
			"Predict METEOR-M passes and schedule SatDump captures."
		),
	)
	parser.add_argument(
		"--config",
		type=str,
		help="Path to config YAML/JSON file",
	)
	parser.add_argument("--lookahead", type=int, help="Lookahead window in hours")
	parser.add_argument("--min-elev", type=float, help="Minimum elevation in degrees")
	parser.add_argument(
		"--version",
		action="store_true",
		help="Show version and exit",
	)

	subparsers = parser.add_subparsers(dest="command", required=False)

	list_parser = subparsers.add_parser(
		"list-passes", help="List predicted passes"
	)
	list_parser.add_argument("--hours", type=int, help="Override lookahead in hours")

	run_parser = subparsers.add_parser(
		"run", help="Run scheduler to capture passes (scheduling WIP)"
	)
	run_parser.add_argument(
		"--dry-run",
		action="store_true",
		help="Plan without invoking SatDump",
	)

	return parser


def _apply_cli_overrides(cfg: Config, args: argparse.Namespace) -> Config:
	if getattr(args, "lookahead", None) is not None:
		cfg.lookahead_hours = int(args.lookahead)
	if getattr(args, "min_elev", None) is not None:
		cfg.min_elevation_deg = float(args.min_elev)
	return cfg


def _list_passes(cfg: Config, hours_override: Optional[int]) -> int:
	lookahead = int(hours_override) if hours_override else cfg.lookahead_hours
	cache_dir = Path(cfg.paths.cache_dir)
	ensure_dir(cache_dir)
	text = fetch_tles(cache_dir)
	triples = parse_tles(text)
	targets = select_meteor_targets(triples)
	if not targets:
		print("No METEOR targets found in TLE set.")
		return 1
	qth = ObserverQTH(
		latitude_deg=cfg.qth.latitude_deg,
		longitude_deg=cfg.qth.longitude_deg,
		altitude_m=cfg.qth.altitude_m,
	)
	passes = find_passes(targets, qth, lookahead, cfg.min_elevation_deg)
	if not passes:
		print("No passes within lookahead window.")
		return 0
	for p in passes:
		print(
			f"{p.satellite_name}: AOS {p.aos.isoformat()}  TCA {p.tca.isoformat()}  "
			f"LOS {p.los.isoformat()}  max_el {p.max_elevation_deg:.1f}°  dur {p.duration_sec}s"
		)
	return 0


def main(argv: Optional[list[str]] = None) -> int:
	argv = argv if argv is not None else sys.argv[1:]
	parser = build_parser()
	args = parser.parse_args(argv)

	if args.version:
		print(__version__)
		return 0

	cfg = load_config(args.config)
	cfg = _apply_cli_overrides(cfg, args)

	# Ensure directories and logging are ready
	ensure_dir(Path(cfg.paths.logs_dir))
	setup_logging(Path(cfg.paths.logs_dir))

	if args.command == "list-passes":
		return _list_passes(cfg, getattr(args, "hours", None))
	elif args.command == "run":
		print("[WIP] Scheduler not implemented yet. Use list-passes for now.")
		return 0
	else:
		parser.print_help()
		return 0


if __name__ == "__main__":
	sys.exit(main())
