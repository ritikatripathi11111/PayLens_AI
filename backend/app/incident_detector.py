from collections import Counter
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from .models import PaymentEventDB


# ---------------------------------------------------------
# Detection thresholds
# ---------------------------------------------------------

# Relative degradation threshold
FAILURE_RATE_MULTIPLIER = 2.0

# Absolute failure-rate threshold
# If current failures are already this high,
# treat the payment system as degraded even when
# the baseline was also unhealthy.
ABSOLUTE_FAILURE_RATE_THRESHOLD = 50.0

# Latency degradation threshold
LATENCY_MULTIPLIER = 2.0

# Minimum number of events required for comparison
MIN_EVENTS = 20


# ---------------------------------------------------------
# Time helpers
# ---------------------------------------------------------

def utc_now_naive():
    """
    Return current UTC time without timezone information.

    SQLite DateTime stores timestamps as timezone-naive
    values, so comparisons use the same representation.
    """

    return datetime.now(timezone.utc).replace(
        tzinfo=None
    )


def normalize_timestamp(timestamp):
    """
    Convert any datetime into naive UTC.
    """

    if timestamp is None:
        return None

    if timestamp.tzinfo is not None:
        return (
            timestamp
            .astimezone(timezone.utc)
            .replace(tzinfo=None)
        )

    return timestamp


def get_analysis_end_time(
    db: Session,
    end_time: datetime = None
):
    """
    Determine the end time for incident analysis.

    If end_time is provided, use it.

    Otherwise, use the timestamp of the latest
    payment event in the database.
    """

    # -----------------------------------------------------
    # Explicit end time
    # -----------------------------------------------------

    if end_time is not None:
        return normalize_timestamp(end_time)

    # -----------------------------------------------------
    # Latest payment event
    # -----------------------------------------------------

    latest_event = (
        db.query(PaymentEventDB)
        .order_by(
            PaymentEventDB.timestamp.desc()
        )
        .first()
    )

    if latest_event is not None:
        return normalize_timestamp(
            latest_event.timestamp
        )

    # -----------------------------------------------------
    # No events
    # -----------------------------------------------------

    return utc_now_naive()


# ---------------------------------------------------------
# Metric helpers
# ---------------------------------------------------------

def calculate_failure_rate(events):
    """
    Calculate percentage of failed payments.
    """

    if not events:
        return 0.0

    failed = sum(
        1
        for event in events
        if event.status == "failed"
    )

    return (
        failed / len(events)
    ) * 100


def calculate_average_latency(events):
    """
    Calculate average payment latency.
    """

    latency_values = [
        event.latency_ms
        for event in events
        if event.latency_ms is not None
    ]

    if not latency_values:
        return 0.0

    return (
        sum(latency_values)
        / len(latency_values)
    )


def calculate_multiplier(current, baseline):
    """
    Calculate current value relative to baseline.
    """

    if baseline <= 0:
        return 0.0

    return current / baseline


# ---------------------------------------------------------
# Breakdown helpers
# ---------------------------------------------------------

def get_dominant_value(events, attribute):
    """
    Return the most common value of an attribute.
    """

    values = [
        getattr(event, attribute)
        for event in events
        if getattr(event, attribute) is not None
    ]

    if not values:
        return None

    return Counter(values).most_common(1)[0][0]


def get_failure_breakdown(events, attribute):
    """
    Calculate failure rate for every value
    of an attribute.
    """

    groups = {}

    for event in events:

        value = getattr(
            event,
            attribute
        )

        if value is None:
            continue

        if value not in groups:
            groups[value] = []

        groups[value].append(event)

    breakdown = {}

    for value, group in groups.items():

        breakdown[value] = round(
            calculate_failure_rate(group),
            2
        )

    return breakdown


# ---------------------------------------------------------
# Main incident analysis
# ---------------------------------------------------------

def analyze_incident(
    db: Session,
    window_minutes: int = 60,
    end_time: datetime = None
):
    """
    Compare the current time window against the
    immediately preceding baseline window.

    Detection considers:

        1. Relative failure-rate degradation
        2. Absolute failure-rate degradation
        3. Latency degradation
        4. Supporting error/gateway signals

    Architecture:

        Database
             ↓
        Latest Event Timestamp
             ↓
        Baseline Window
             ↓
        Current Window
             ↓
        Metric Comparison
             ↓
        Anomaly Detection
             ↓
        Evidence
             ↓
        Severity
    """

    # -----------------------------------------------------
    # Determine analysis end time
    # -----------------------------------------------------

    now = get_analysis_end_time(
        db=db,
        end_time=end_time
    )

    # -----------------------------------------------------
    # Calculate windows
    # -----------------------------------------------------

    current_start = (
        now
        - timedelta(
            minutes=window_minutes
        )
    )

    baseline_start = (
        now
        - timedelta(
            minutes=window_minutes * 2
        )
    )

    baseline_end = current_start

    # -----------------------------------------------------
    # Fetch events
    # -----------------------------------------------------

    all_events = (
        db.query(PaymentEventDB)
        .filter(
            PaymentEventDB.timestamp >= baseline_start,
            PaymentEventDB.timestamp <= now
        )
        .order_by(
            PaymentEventDB.timestamp.asc()
        )
        .all()
    )

    # -----------------------------------------------------
    # Split baseline and current windows
    # -----------------------------------------------------

    baseline_events = []
    current_events = []

    for event in all_events:

        event_time = normalize_timestamp(
            event.timestamp
        )

        if event_time < current_start:

            baseline_events.append(event)

        elif event_time <= now:

            current_events.append(event)

    # -----------------------------------------------------
    # Validate data volume
    # -----------------------------------------------------

    if len(baseline_events) < MIN_EVENTS:

        return {
            "incident_detected": False,
            "status": "insufficient_baseline_data",
            "message": (
                f"Need at least {MIN_EVENTS} "
                "baseline events."
            ),
            "baseline_events": len(
                baseline_events
            ),
            "current_events": len(
                current_events
            )
        }

    if len(current_events) < MIN_EVENTS:

        return {
            "incident_detected": False,
            "status": "insufficient_current_data",
            "message": (
                f"Need at least {MIN_EVENTS} "
                "current events."
            ),
            "baseline_events": len(
                baseline_events
            ),
            "current_events": len(
                current_events
            )
        }

    # -----------------------------------------------------
    # Core metrics
    # -----------------------------------------------------

    baseline_failure_rate = (
        calculate_failure_rate(
            baseline_events
        )
    )

    current_failure_rate = (
        calculate_failure_rate(
            current_events
        )
    )

    baseline_latency = (
        calculate_average_latency(
            baseline_events
        )
    )

    current_latency = (
        calculate_average_latency(
            current_events
        )
    )

    failure_multiplier = calculate_multiplier(
        current_failure_rate,
        baseline_failure_rate
    )

    latency_multiplier = calculate_multiplier(
        current_latency,
        baseline_latency
    )

    # -----------------------------------------------------
    # Detect anomalies
    # -----------------------------------------------------

    # Relative degradation
    failure_rate_anomaly = (
        current_failure_rate
        >= (
            baseline_failure_rate
            * FAILURE_RATE_MULTIPLIER
        )
    )

    # Absolute degradation
    absolute_failure_anomaly = (
        current_failure_rate
        >= ABSOLUTE_FAILURE_RATE_THRESHOLD
    )

    # Latency degradation
    latency_anomaly = (
        current_latency
        >= (
            baseline_latency
            * LATENCY_MULTIPLIER
        )
    )

    # -----------------------------------------------------
    # Dimension analysis
    # -----------------------------------------------------

    issuer_breakdown = (
        get_failure_breakdown(
            current_events,
            "issuer"
        )
    )

    gateway_breakdown = (
        get_failure_breakdown(
            current_events,
            "gateway"
        )
    )

    payment_method_breakdown = (
        get_failure_breakdown(
            current_events,
            "payment_method"
        )
    )

    error_code_breakdown = (
        get_failure_breakdown(
            current_events,
            "error_code"
        )
    )

    # -----------------------------------------------------
    # Failed current events
    # -----------------------------------------------------

    failed_current_events = [
        event
        for event in current_events
        if event.status == "failed"
    ]

    failed_transaction_value = sum(
        event.amount
        for event in failed_current_events
    )

    successful_current_events = [
        event
        for event in current_events
        if event.status == "captured"
    ]

    successful_transaction_value = sum(
        event.amount
        for event in successful_current_events
    )

    # -----------------------------------------------------
    # Dominant signals
    # -----------------------------------------------------

    dominant_error = get_dominant_value(
        failed_current_events,
        "error_code"
    )

    dominant_gateway = get_dominant_value(
        failed_current_events,
        "gateway"
    )

    dominant_issuer = get_dominant_value(
        failed_current_events,
        "issuer"
    )

    dominant_payment_method = get_dominant_value(
        failed_current_events,
        "payment_method"
    )

    # -----------------------------------------------------
    # Evidence
    # -----------------------------------------------------

    evidence = []

    # Relative failure degradation
    if failure_rate_anomaly:

        evidence.append({
            "type": "failure_rate",
            "message": (
                "Failure rate increased "
                "significantly relative to baseline."
            ),
            "baseline": round(
                baseline_failure_rate,
                2
            ),
            "current": round(
                current_failure_rate,
                2
            ),
            "multiplier": round(
                failure_multiplier,
                2
            )
        })

    # Absolute failure degradation
    if absolute_failure_anomaly:

        evidence.append({
            "type": "absolute_failure_rate",
            "message": (
                "Current payment failure rate "
                "exceeded the critical threshold."
            ),
            "threshold": (
                ABSOLUTE_FAILURE_RATE_THRESHOLD
            ),
            "current": round(
                current_failure_rate,
                2
            )
        })

    # Latency degradation
    if latency_anomaly:

        evidence.append({
            "type": "latency",
            "message": (
                "Average payment latency "
                "increased significantly."
            ),
            "baseline_ms": round(
                baseline_latency,
                2
            ),
            "current_ms": round(
                current_latency,
                2
            ),
            "multiplier": round(
                latency_multiplier,
                2
            )
        })

    # Dominant error
    if dominant_error:

        evidence.append({
            "type": "error_code",
            "message": (
                "A dominant error code was "
                "identified among failed payments."
            ),
            "dominant_error": dominant_error
        })

    # Dominant gateway
    if dominant_gateway:

        gateway_failure_rate = (
            gateway_breakdown.get(
                dominant_gateway,
                0
            )
        )

        if gateway_failure_rate >= 50:

            evidence.append({
                "type": "gateway",
                "message": (
                    "A payment gateway is showing "
                    "a high concentration of failures."
                ),
                "gateway": dominant_gateway,
                "failure_rate": gateway_failure_rate
            })

    # -----------------------------------------------------
    # Incident decision
    # -----------------------------------------------------

    incident_detected = (
        failure_rate_anomaly
        or absolute_failure_anomaly
        or latency_anomaly
    )

    # -----------------------------------------------------
    # Severity
    # -----------------------------------------------------

    anomaly_score = 0

    if failure_rate_anomaly:
        anomaly_score += 1

    if absolute_failure_anomaly:
        anomaly_score += 1

    if latency_anomaly:
        anomaly_score += 1

    if dominant_error:
        anomaly_score += 1

    if (
        dominant_gateway
        and gateway_breakdown.get(
            dominant_gateway,
            0
        ) >= 50
    ):
        anomaly_score += 1

    # -----------------------------------------------------
    # Determine severity
    # -----------------------------------------------------

    if not incident_detected:

        severity = "NONE"

    elif (
        current_failure_rate >= 80
        or anomaly_score >= 4
    ):

        severity = "HIGH"

    elif (
        current_failure_rate >= 60
        or anomaly_score >= 3
    ):

        severity = "MEDIUM"

    else:

        severity = "LOW"

    # -----------------------------------------------------
    # Final response
    # -----------------------------------------------------

    return {
        "incident_detected": incident_detected,

        "severity": severity,

        "analysis_window_minutes": window_minutes,

        "baseline": {
            "start": baseline_start.isoformat(),
            "end": baseline_end.isoformat(),
            "events": len(
                baseline_events
            ),
            "failure_rate": round(
                baseline_failure_rate,
                2
            ),
            "average_latency_ms": round(
                baseline_latency,
                2
            )
        },

        "current": {
            "start": current_start.isoformat(),
            "end": now.isoformat(),
            "events": len(
                current_events
            ),
            "failed_events": len(
                failed_current_events
            ),
            "successful_events": len(
                successful_current_events
            ),
            "failure_rate": round(
                current_failure_rate,
                2
            ),
            "average_latency_ms": round(
                current_latency,
                2
            ),
            "failed_transaction_value": (
                failed_transaction_value
            ),
            "successful_transaction_value": (
                successful_transaction_value
            )
        },

        "changes": {
            "failure_rate_multiplier": round(
                failure_multiplier,
                2
            ),
            "latency_multiplier": round(
                latency_multiplier,
                2
            )
        },

        "dominant_signals": {
            "error_code": dominant_error,
            "gateway": dominant_gateway,
            "issuer": dominant_issuer,
            "payment_method": (
                dominant_payment_method
            )
        },

        "breakdowns": {
            "issuer_failure_rates": (
                issuer_breakdown
            ),
            "gateway_failure_rates": (
                gateway_breakdown
            ),
            "payment_method_failure_rates": (
                payment_method_breakdown
            ),
            "error_code_failure_rates": (
                error_code_breakdown
            )
        },

        "evidence": evidence,

        "status": (
            "incident_detected"
            if incident_detected
            else "normal"
        )
    }