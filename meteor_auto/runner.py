from __future__ import annotations

import logging
import subprocess
import shutil
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Optional

from .config import Config
from .predict import PassEvent
from .utils import ensure_dir

logger = logging.getLogger(__name__)


class SatDumpRunner:
	def __init__(self, config: Config):
		self.config = config
		self._fallback_state = {}  # Track failures per satellite

	def _check_satdump_available(self) -> bool:
		"""Check if SatDump is available in PATH."""
		return shutil.which(self.config.satdump.path) is not None

	def _create_output_dir(self, pass_event: PassEvent) -> Path:
		"""Create timestamped output directory for this pass."""
		timestamp = pass_event.aos.strftime("%Y%m%d_%H%M%S")
		sat_name = pass_event.satellite_name.replace(" ", "_").replace("/", "_")
		output_dir = Path(self.config.paths.outputs_dir) / f"{timestamp}_{sat_name}"
		ensure_dir(output_dir)
		return output_dir

	def _should_use_fallback(self, satellite_name: str) -> bool:
		"""Check if we should use fallback frequency/pipeline due to recent failures."""
		failures = self._fallback_state.get(satellite_name, 0)
		return failures >= 2

	def _record_failure(self, satellite_name: str) -> None:
		"""Record a failure for fallback logic."""
		self._fallback_state[satellite_name] = self._fallback_state.get(satellite_name, 0) + 1
		logger.info("Recorded failure for %s (count: %d)", satellite_name, self._fallback_state[satellite_name])

	def _record_success(self, satellite_name: str) -> None:
		"""Record a success and reset failure counter."""
		if satellite_name in self._fallback_state:
			del self._fallback_state[satellite_name]

	def _build_satdump_cmd(self, pass_event: PassEvent, output_dir: Path) -> List[str]:
		"""Build SatDump command line."""
		use_fallback = self._should_use_fallback(pass_event.satellite_name)
		
		frequency = self.config.frequencies.backup_hz if use_fallback else self.config.frequencies.primary_hz
		pipeline = self.config.pipelines.fallback if use_fallback else self.config.pipelines.primary
		
		# Calculate timeout with margins
		duration_sec = pass_event.duration_sec + 120 + 60  # pre + post margins
		
		cmd = [
			self.config.satdump.path,
			"live",
			pipeline,
			str(output_dir),
			"--source", "rtlsdr",
			"--samplerate", str(int(self.config.satdump.sample_rate_sps)),
			"--frequency", str(int(frequency)),
			"--gain", str(self.config.satdump.gain_db),
			"--timeout", str(duration_sec),
		]
		
		if self.config.satdump.bias_tee:
			cmd.append("--bias")
		
		if not self.config.satdump.enable_agc:
			cmd.append("--no-agc")
			
		if self.config.satdump.http_bind:
			cmd.extend(["--http_server", self.config.satdump.http_bind])
		
		logger.info("SatDump command: %s", " ".join(cmd))
		return cmd

	def _check_capture_success(self, output_dir: Path) -> bool:
		"""Check if capture was successful by looking for output files."""
		# Look for common SatDump output patterns
		patterns = ["*.png", "*.jpg", "*.jpeg", "*.lrpt", "*.cadu"]
		for pattern in patterns:
			if list(output_dir.glob(pattern)):
				return True
		return False

	def capture_pass(self, pass_event: PassEvent) -> bool:
		"""Execute SatDump capture for a single pass."""
		if not self._check_satdump_available():
			logger.error("SatDump not found in PATH: %s", self.config.satdump.path)
			return False

		output_dir = self._create_output_dir(pass_event)
		cmd = self._build_satdump_cmd(pass_event, output_dir)
		
		try:
			logger.info("Starting SatDump capture for %s", pass_event.satellite_name)
			
			# Run SatDump
			result = subprocess.run(
				cmd,
				cwd=output_dir,
				capture_output=True,
				text=True,
				timeout=pass_event.duration_sec + 300  # Extra safety margin
			)
			
			# Log output
			if result.stdout:
				logger.debug("SatDump stdout: %s", result.stdout)
			if result.stderr:
				logger.debug("SatDump stderr: %s", result.stderr)
			
			# Check success
			if result.returncode == 0 and self._check_capture_success(output_dir):
				logger.info("Capture successful for %s", pass_event.satellite_name)
				self._record_success(pass_event.satellite_name)
				return True
			else:
				logger.warning("Capture failed for %s (returncode: %d)", 
							  pass_event.satellite_name, result.returncode)
				self._record_failure(pass_event.satellite_name)
				return False
				
		except subprocess.TimeoutExpired:
			logger.error("SatDump timeout for %s", pass_event.satellite_name)
			self._record_failure(pass_event.satellite_name)
			return False
		except Exception as e:
			logger.error("SatDump execution error for %s: %s", pass_event.satellite_name, e)
			self._record_failure(pass_event.satellite_name)
			return False
