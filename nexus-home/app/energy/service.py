"""Energy monitoring data management."""

from app.database import get_db


async def record_reading(device_id: str, watts: float) -> None:
    """Record an energy reading."""
    async with get_db() as db:
        await db.execute(
            "INSERT INTO energy_readings (device_id, watts) VALUES (?, ?)",
            (device_id, watts),
        )
        await db.commit()


async def get_usage(device_id: str | None = None, hours: int = 24) -> list[dict]:
    """Get energy readings for a device or all devices."""
    async with get_db() as db:
        if device_id:
            cursor = await db.execute(
                "SELECT * FROM energy_readings WHERE device_id = ? "
                "AND recorded_at >= datetime('now', ? || ' hours') ORDER BY recorded_at",
                (device_id, f"-{hours}"),
            )
        else:
            cursor = await db.execute(
                "SELECT * FROM energy_readings "
                "WHERE recorded_at >= datetime('now', ? || ' hours') ORDER BY recorded_at",
                (f"-{hours}",),
            )
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]


async def get_summary(hours: int = 24) -> dict:
    """Get aggregated energy summary."""
    async with get_db() as db:
        time_filter = f"-{hours}"

        # Total and peak
        cursor = await db.execute(
            "SELECT COUNT(*) as cnt, MAX(watts) as peak, SUM(watts) as total "
            "FROM energy_readings WHERE recorded_at >= datetime('now', ? || ' hours')",
            (time_filter,),
        )
        row = await cursor.fetchone()
        total_readings = dict(row) if row else {"cnt": 0, "peak": 0, "total": 0}

        # Per-device breakdown
        cursor = await db.execute(
            "SELECT device_id, AVG(watts) as avg_watts, MAX(watts) as peak_watts, "
            "COUNT(*) as readings FROM energy_readings "
            "WHERE recorded_at >= datetime('now', ? || ' hours') GROUP BY device_id",
            (time_filter,),
        )
        breakdown = [dict(row) for row in await cursor.fetchall()]

        # Estimate kWh: average watts * hours / 1000
        count = total_readings["cnt"] or 1
        avg_watts = (total_readings["total"] or 0) / count
        total_kwh = avg_watts * hours / 1000

        return {
            "total_kwh": round(total_kwh, 3),
            "peak_watts": total_readings["peak"] or 0,
            "readings_count": total_readings["cnt"] or 0,
            "device_breakdown": breakdown,
        }
