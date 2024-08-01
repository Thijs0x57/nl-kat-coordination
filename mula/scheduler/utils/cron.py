from datetime import datetime, timezone

from croniter import croniter  # type: ignore


def next_run(expression: str, start_time: datetime = datetime.now(timezone.utc)):
    cron = croniter(expression, start_time)
    return cron.get_next(datetime)
