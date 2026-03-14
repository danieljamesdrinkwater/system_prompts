"""APScheduler-based cron scheduler for timed automation actions."""

import json
import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

import aiosqlite

from app.database import get_db

logger = logging.getLogger(__name__)


class SchedulerManager:
    """Manages cron-based scheduled automation jobs."""

    def __init__(self) -> None:
        self.scheduler: AsyncIOScheduler | None = None

    async def start(self) -> None:
        """Initialise the scheduler, load persisted schedules, and start."""
        self.scheduler = AsyncIOScheduler()
        self.scheduler.start()

        async with get_db() as db:
            cursor = await db.execute(
                "SELECT id, name, cron_expr, action_type, action_config "
                "FROM schedules WHERE enabled = 1"
            )
            rows = await cursor.fetchall()
            for row in rows:
                self._add_job_from_row(row)

        logger.info("Scheduler started with %d jobs", len(self.scheduler.get_jobs()))

    async def stop(self) -> None:
        """Gracefully shut down the scheduler."""
        if self.scheduler and self.scheduler.running:
            self.scheduler.shutdown(wait=False)
            logger.info("Scheduler stopped")

    async def add_schedule(self, db: aiosqlite.Connection, schedule: dict) -> None:
        """Persist a new schedule and register the cron job."""
        await db.execute(
            "INSERT INTO schedules (id, name, cron_expr, action_type, action_config, enabled) "
            "VALUES (?, ?, ?, ?, ?, 1)",
            (
                schedule["id"],
                schedule["name"],
                schedule["cron_expr"],
                schedule["action_type"],
                json.dumps(schedule.get("action_config", {})),
            ),
        )
        await db.commit()

        if self.scheduler and self.scheduler.running:
            self._add_job(
                schedule_id=schedule["id"],
                cron_expr=schedule["cron_expr"],
                action_type=schedule["action_type"],
                action_config=schedule.get("action_config", {}),
            )

    async def remove_schedule(self, db: aiosqlite.Connection, schedule_id: str) -> None:
        """Remove a schedule from the database and the running scheduler."""
        await db.execute("DELETE FROM schedules WHERE id = ?", (schedule_id,))
        await db.commit()

        if self.scheduler:
            job = self.scheduler.get_job(schedule_id)
            if job:
                job.remove()
                logger.info("Removed scheduled job '%s'", schedule_id)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _add_job_from_row(self, row: aiosqlite.Row) -> None:
        """Create a scheduler job from a database row."""
        self._add_job(
            schedule_id=row["id"],
            cron_expr=row["cron_expr"],
            action_type=row["action_type"],
            action_config=json.loads(row["action_config"]),
        )

    def _add_job(
        self,
        schedule_id: str,
        cron_expr: str,
        action_type: str,
        action_config: dict,
    ) -> None:
        """Register a cron job with the APScheduler instance."""
        if not self.scheduler:
            return

        trigger = CronTrigger.from_crontab(cron_expr)
        self.scheduler.add_job(
            self._execute_scheduled_action,
            trigger=trigger,
            id=schedule_id,
            replace_existing=True,
            kwargs={"action_type": action_type, "action_config": action_config},
        )
        logger.info("Added scheduled job '%s' with cron '%s'", schedule_id, cron_expr)

    @staticmethod
    async def _execute_scheduled_action(action_type: str, action_config: dict) -> None:
        """Callback invoked by APScheduler — dispatches to the automation engine."""
        from app.automation.engine import automation_engine

        action = {"type": action_type, **action_config}
        logger.info("Executing scheduled action: %s", action_type)
        await automation_engine.execute_actions([action])


scheduler_manager = SchedulerManager()
