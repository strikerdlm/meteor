from __future__ import annotations

import logging
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Optional

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.date import DateTrigger

from .config import Config
from .predict import PassEvent
from .runner import SatDumpRunner
from .utils import ensure_dir

logger = logging.getLogger(__name__)


class PassScheduler:
	def __init__(self, config: Config):
		self.config = config
		self.scheduler = BlockingScheduler()
		self.runner = SatDumpRunner(config)
		self.lock_file = Path(config.paths.cache_dir) / "capture.lock"

	def _is_locked(self) -> bool:
		"""Check if another capture is already running."""
		if not self.lock_file.exists():
			return False
		try:
			# Check if lock is stale (older than 4 hours)
			age_hours = (time.time() - self.lock_file.stat().st_mtime) / 3600
			if age_hours > 4:
				logger.warning("Removing stale lock file (age: %.1f hours)", age_hours)
				self.lock_file.unlink()
				return False
			return True
		except Exception:
			return False

	def _acquire_lock(self) -> bool:
		"""Acquire capture lock."""
		if self._is_locked():
			return False
		try:
			ensure_dir(self.lock_file.parent)
			self.lock_file.write_text(str(datetime.now().isoformat()), encoding="utf-8")
			return True
		except Exception as e:
			logger.error("Failed to acquire lock: %s", e)
			return False

	def _release_lock(self) -> None:
		"""Release capture lock."""
		try:
			if self.lock_file.exists():
				self.lock_file.unlink()
		except Exception as e:
			logger.warning("Failed to release lock: %s", e)

	def _schedule_capture(self, pass_event: PassEvent) -> None:
		"""Schedule a single pass capture."""
		# Add pre-start margin
		start_time = pass_event.aos - timedelta(seconds=120)
		
		def capture_job():
			if not self._acquire_lock():
				logger.warning("Skipping %s - another capture is running", pass_event.satellite_name)
				return
			
			try:
				logger.info("Starting capture for %s", pass_event.satellite_name)
				success = self.runner.capture_pass(pass_event)
				if success:
					logger.info("Capture completed successfully for %s", pass_event.satellite_name)
				else:
					logger.warning("Capture failed for %s", pass_event.satellite_name)
			finally:
				self._release_lock()

		self.scheduler.add_job(
			capture_job,
			trigger=DateTrigger(run_date=start_time),
			id=f"capture_{pass_event.satellite_name}_{pass_event.aos.isoformat()}",
			name=f"Capture {pass_event.satellite_name}",
		)
		logger.info("Scheduled %s for %s (AOS: %s)", 
					pass_event.satellite_name, start_time.isoformat(), pass_event.aos.isoformat())

	def schedule_passes(self, passes: List[PassEvent], dry_run: bool = False) -> None:
		"""Schedule all passes for capture."""
		if not passes:
			logger.info("No passes to schedule")
			return

		for pass_event in passes:
			if dry_run:
				logger.info("[DRY-RUN] Would schedule %s for %s", 
						   pass_event.satellite_name, pass_event.aos.isoformat())
			else:
				self._schedule_capture(pass_event)

		if not dry_run:
			logger.info("Scheduled %d passes. Starting scheduler...", len(passes))
			try:
				self.scheduler.start()
			except KeyboardInterrupt:
				logger.info("Scheduler interrupted by user")
				self.scheduler.shutdown()
			except Exception as e:
				logger.error("Scheduler error: %s", e)
				self.scheduler.shutdown()
		else:
			logger.info("[DRY-RUN] Would start scheduler for %d passes", len(passes))

	def list_scheduled_jobs(self) -> None:
		"""List all scheduled jobs."""
		jobs = self.scheduler.get_jobs()
		if not jobs:
			print("No jobs scheduled")
			return
		
		print(f"Scheduled jobs ({len(jobs)}):")
		for job in jobs:
			print(f"  {job.name} - {job.next_run_time}")
