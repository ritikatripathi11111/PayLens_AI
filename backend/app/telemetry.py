from datetime import datetime, timedelta, timezone
from sqlalchemy.orm import Session

from .models import PaymentEventDB


def _utc_now_naive():
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _metrics(events):
    total = len(events)
    failed = sum(1 for e in events if str(e.status).lower() == "failed")
    latency_values = [e.latency_ms for e in events if e.latency_ms is not None]

    failure_rate = (failed / total * 100) if total else 0.0
    avg_latency = (sum(latency_values) / len(latency_values)) if latency_values else 0.0

    return {
        "events": total,
        "failed_events": failed,
        "failure_rate": round(failure_rate, 2),
        "average_latency_ms": round(avg_latency, 2),
    }


def _gateway_health(events):
    gateway_stats = {}

    for event in events:
        gateway = event.gateway or "UNKNOWN"
        stats = gateway_stats.setdefault(gateway, {"events": 0, "failed": 0, "latency": []})
        stats["events"] += 1
        if str(event.status).lower() == "failed":
            stats["failed"] += 1
        if event.latency_ms is not None:
            stats["latency"].append(event.latency_ms)

    result = []
    for gateway, stats in gateway_stats.items():
        rate = stats["failed"] / stats["events"] * 100 if stats["events"] else 0
        latency = sum(stats["latency"]) / len(stats["latency"]) if stats["latency"] else 0
        result.append({
            "gateway": gateway,
            "failure_rate": round(rate, 2),
            "average_latency_ms": round(latency, 2),
            "events": stats["events"],
        })

    result.sort(key=lambda x: x["failure_rate"], reverse=True)

    if not result:
        return {
            "status": "NO_DATA",
            "gateway": "—",
            "failure_rate": 0,
            "gateways": [],
        }

    dominant = result[0]
    if dominant["failure_rate"] >= 25:
        status = "DEGRADED"
    elif dominant["failure_rate"] >= 10:
        status = "AT RISK"
    else:
        status = "HEALTHY"

    return {
        "status": status,
        "gateway": dominant["gateway"],
        "failure_rate": dominant["failure_rate"],
        "gateways": result,
    }


def _trend(db: Session, end_time: datetime, minutes: int = 12):
    """Return one failure-rate sample per minute for the live chart."""
    samples = []
    end_time = end_time.replace(second=59, microsecond=999999)
    start_time = end_time - timedelta(minutes=minutes)

    events = (
        db.query(PaymentEventDB)
        .filter(
            PaymentEventDB.timestamp >= start_time,
            PaymentEventDB.timestamp <= end_time,
        )
        .order_by(PaymentEventDB.timestamp.asc())
        .all()
    )

    for offset in range(minutes):
        bucket_start = start_time + timedelta(minutes=offset)
        bucket_end = bucket_start + timedelta(minutes=1)
        bucket = [e for e in events if bucket_start <= e.timestamp < bucket_end]
        metric = _metrics(bucket)
        samples.append({
            "timestamp": bucket_start.isoformat(),
            "failure_rate": metric["failure_rate"],
            "events": metric["events"],
        })

    return samples


def get_live_telemetry(db: Session, window_minutes: int = 5):
    """Build the dashboard's live telemetry snapshot from stored payment events."""
    if window_minutes <= 0:
        window_minutes = 5

    latest = (
        db.query(PaymentEventDB)
        .order_by(PaymentEventDB.timestamp.desc())
        .first()
    )

    # Use the latest stored event when available. This keeps telemetry usable
    # for seeded/demo data whose timestamps are not equal to the machine clock.
    end_time = latest.timestamp if latest else _utc_now_naive()
    start_time = end_time - timedelta(minutes=window_minutes)

    events = (
        db.query(PaymentEventDB)
        .filter(
            PaymentEventDB.timestamp >= start_time,
            PaymentEventDB.timestamp <= end_time,
        )
        .order_by(PaymentEventDB.timestamp.asc())
        .all()
    )

    metric = _metrics(events)
    gateway = _gateway_health(events)

    return {
        "status": "live",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "data_timestamp": end_time.isoformat(),
        "window_minutes": window_minutes,
        "metrics": metric,
        "gateway": gateway,
        "trend": _trend(db, end_time, minutes=12),
    }
