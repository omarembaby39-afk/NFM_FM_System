# utils.py – shared helper functions

from datetime import datetime, timedelta


def compute_overdue(requested_at, sla_hours, status):
    """
    Return True if a work order is overdue based on requested_at + sla_hours
    and status is not 'Completed' / 'Closed'.
    """
    if not requested_at or not sla_hours:
        return False

    if status in ("Completed", "Closed"):
        return False

    # requested_at is already a datetime from psycopg2
    deadline = requested_at + timedelta(hours=int(sla_hours))
    now = datetime.utcnow()
    return now > deadline
