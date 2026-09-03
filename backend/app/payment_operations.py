from dataclasses import dataclass
from datetime import datetime, timedelta
import random


@dataclass
class ScenarioProfile:
    name: str
    traffic_volume: int
    failure_rate: float
    latency_ms: float
    gateway: str | None = None
    payment_method: str | None = None
    issuer: str | None = None
    dominant_error: str | None = None


SCENARIOS = {
    "healthy": ScenarioProfile(
        name="HEALTHY",
        traffic_volume=100,
        failure_rate=0.03,
        latency_ms=210,
    ),

    "gateway_degradation": ScenarioProfile(
        name="GATEWAY_DEGRADATION",
        traffic_volume=100,
        failure_rate=0.38,
        latency_ms=1500,
        gateway="gateway_b",
        dominant_error="GATEWAY_TIMEOUT",
    ),

    "upi_degradation": ScenarioProfile(
        name="UPI_DEGRADATION",
        traffic_volume=100,
        failure_rate=0.35,
        latency_ms=900,
        payment_method="UPI",
        dominant_error="UPI_ERROR",
    ),

    "issuer_degradation": ScenarioProfile(
        name="ISSUER_DEGRADATION",
        traffic_volume=100,
        failure_rate=0.35,
        latency_ms=850,
        issuer="issuer_c",
        dominant_error="ISSUER_DECLINE",
    ),

    "payment_method_degradation": ScenarioProfile(
        name="PAYMENT_METHOD_DEGRADATION",
        traffic_volume=100,
        failure_rate=0.35,
        payment_method="CARD",
        latency_ms=800,
        dominant_error="METHOD_ERROR",
    ),
}


GATEWAYS = ["gateway_a", "gateway_b"]
PAYMENT_METHODS = ["UPI", "CARD", "NETBANKING"]
ISSUERS = ["issuer_a", "issuer_b", "issuer_c"]

NORMAL_ERRORS = [
    "TIMEOUT",
    "VALIDATION_ERROR",
    "INSUFFICIENT_FUNDS",
]


def get_scenario(name: str) -> ScenarioProfile:
    key = name.lower().strip()

    if key not in SCENARIOS:
        raise ValueError(
            f"Unknown scenario '{name}'. "
            f"Available: {', '.join(SCENARIOS.keys())}"
        )

    return SCENARIOS[key]


def generate_payment_events(
    scenario_name: str,
    count: int | None = None,
    seed: int = 42,
    start_time: datetime | None = None,
):
    """
    Generate deterministic synthetic payment telemetry.

    This is intentionally controlled rather than random production traffic.
    The generated events are suitable for PayLens incident detection and RCA.
    """

    scenario = get_scenario(scenario_name)

    rng = random.Random(seed)

    total_events = count or scenario.traffic_volume
    start_time = start_time or datetime.utcnow()

    events = []

    for index in range(total_events):
        timestamp = start_time + timedelta(seconds=index * 10)

        gateway = (
            scenario.gateway
            if scenario.gateway
            else rng.choice(GATEWAYS)
        )

        payment_method = (
            scenario.payment_method
            if scenario.payment_method
            else rng.choice(PAYMENT_METHODS)
        )

        issuer = (
            scenario.issuer
            if scenario.issuer
            else rng.choice(ISSUERS)
        )

        amount = rng.randint(10000, 500000)

        is_failed = rng.random() < scenario.failure_rate

        if is_failed:
            status = "failed"

            if scenario.dominant_error:
                error_code = scenario.dominant_error
            else:
                error_code = rng.choice(NORMAL_ERRORS)
        else:
            status = "captured"
            error_code = None

        latency_variation = rng.uniform(0.85, 1.15)

        latency = round(
            scenario.latency_ms * latency_variation,
            2,
        )

        events.append(
            {
                "payment_id": f"sim_{scenario_name}_{index + 1}",
                "timestamp": timestamp.isoformat(),
                "status": status,
                "amount": amount,
                "gateway": gateway,
                "payment_method": payment_method,
                "issuer": issuer,
                "latency_ms": latency,
                "error_code": error_code,
                "scenario": scenario.name,
            }
        )

    return events


def list_scenarios():
    return [
        {
            "key": key,
            "name": profile.name,
            "traffic_volume": profile.traffic_volume,
            "failure_rate": profile.failure_rate,
            "latency_ms": profile.latency_ms,
            "gateway": profile.gateway,
            "payment_method": profile.payment_method,
            "issuer": profile.issuer,
            "dominant_error": profile.dominant_error,
        }
        for key, profile in SCENARIOS.items()
    ]
    
def insert_scenario_events(db, scenario_name: str, count: int | None = None, seed: int = 42):
    """
    Generate a controlled payment scenario and insert
    the events into the existing payment_events table.
    """

    from app.models import PaymentEventDB

    events = generate_payment_events(
        scenario_name=scenario_name,
        count=count,
        seed=seed,
    )

    inserted = 0

    for event in events:
        db_event = PaymentEventDB(
            payment_id=event["payment_id"],
            merchant_id="merchant_demo",
            amount=event["amount"],
            currency="INR",
            payment_method=event["payment_method"],
            status=event["status"],
            error_code=event["error_code"],
            error_description=(
                f"Simulated {event['error_code']}"
                if event["error_code"]
                else None
            ),
            latency_ms=event["latency_ms"],
            gateway=event["gateway"],
            issuer=event["issuer"],
            retry_count=0,
            timestamp=datetime.fromisoformat(event["timestamp"]),
        )

        db.add(db_event)
        inserted += 1

    db.commit()

    return {
        "scenario": scenario_name,
        "events_generated": len(events),
        "events_inserted": inserted,
    }
    
def insert_scenario_window(
    db,
    scenario_name: str,
    baseline_count: int = 40,
    incident_count: int = 100,
    seed: int = 42,
):
    """
    Insert a complete scenario window:
    - healthy baseline events
    - followed by incident events

    This keeps the timestamps close together so the
    incident detector can compare baseline vs current traffic.
    """

    from app.models import PaymentEventDB

    # Latest existing event becomes the reference point.
    latest_event = (
        db.query(PaymentEventDB)
        .order_by(PaymentEventDB.timestamp.desc())
        .first()
    )

    if latest_event:
        start_time = latest_event.timestamp + timedelta(minutes=2)
    else:
        start_time = datetime.utcnow() - timedelta(minutes=120)

    # -----------------------------
    # 1. Generate healthy baseline
    # -----------------------------
    baseline_events = generate_payment_events(
        scenario_name="healthy",
        count=baseline_count,
        seed=seed,
        start_time=start_time,
    )

    # -----------------------------
    # 2. Generate incident traffic
    # -----------------------------
    baseline_end = start_time + timedelta(
        seconds=(baseline_count - 1) * 10
    )

    incident_start = baseline_end + timedelta(seconds=10)

    incident_events = generate_payment_events(
        scenario_name=scenario_name,
        count=incident_count,
        seed=seed + 1,
        start_time=incident_start,
    )

    all_events = baseline_events + incident_events

    inserted = 0

    for event in all_events:
        db_event = PaymentEventDB(
            payment_id=event["payment_id"],
            merchant_id="merchant_demo",
            amount=event["amount"],
            currency="INR",
            payment_method=event["payment_method"],
            status=event["status"],
            error_code=event["error_code"],
            error_description=(
                f"Simulated {event['error_code']}"
                if event["error_code"]
                else None
            ),
            latency_ms=event["latency_ms"],
            gateway=event["gateway"],
            issuer=event["issuer"],
            retry_count=0,
            timestamp=datetime.fromisoformat(event["timestamp"]),
        )

        db.add(db_event)
        inserted += 1

    db.commit()

    return {
        "scenario": scenario_name,
        "baseline_events": len(baseline_events),
        "incident_events": len(incident_events),
        "events_inserted": inserted,
        "baseline_start": baseline_events[0]["timestamp"],
        "baseline_end": baseline_events[-1]["timestamp"],
        "incident_start": incident_events[0]["timestamp"],
        "incident_end": incident_events[-1]["timestamp"],
    }
    
def insert_clean_scenario_window(
    db,
    scenario_name: str,
    baseline_count: int = 40,
    incident_count: int = 100,
    seed: int = 42,
):
    """
    Insert a clean scenario aligned with the detector's
    60-minute baseline/current windows.

    The baseline occupies the hour before the incident.
    The incident occupies the latest analysis window.
    """

    from app.models import PaymentEventDB

    latest_event = (
        db.query(PaymentEventDB)
        .order_by(PaymentEventDB.timestamp.desc())
        .first()
    )

    if latest_event:
        incident_start = latest_event.timestamp + timedelta(minutes=70)
    else:
        incident_start = datetime.utcnow()

    # --------------------------------
    # Baseline: 60 minutes before incident
    # --------------------------------
    baseline_start = incident_start - timedelta(minutes=60)

    baseline_events = generate_payment_events(
        scenario_name="healthy",
        count=baseline_count,
        seed=seed,
        start_time=baseline_start,
    )

    # Spread baseline events across the full hour
    if baseline_count > 1:
        baseline_step = timedelta(
            seconds=3600 / (baseline_count - 1)
        )

        for index, event in enumerate(baseline_events):
            event["timestamp"] = (
                baseline_start + baseline_step * index
            ).isoformat()

    # --------------------------------
    # Incident: latest 60-minute window
    # --------------------------------
    incident_events = generate_payment_events(
        scenario_name=scenario_name,
        count=incident_count,
        seed=seed + 1,
        start_time=incident_start,
    )

    # Spread incident traffic across 60 minutes
    if incident_count > 1:
        incident_step = timedelta(
            seconds=3600 / (incident_count - 1)
        )

        for index, event in enumerate(incident_events):
            event["timestamp"] = (
                incident_start + incident_step * index
            ).isoformat()

    all_events = baseline_events + incident_events

    for event in all_events:
        db_event = PaymentEventDB(
            payment_id=event["payment_id"],
            merchant_id="merchant_demo",
            amount=event["amount"],
            currency="INR",
            payment_method=event["payment_method"],
            status=event["status"],
            error_code=event["error_code"],
            error_description=(
                f"Simulated {event['error_code']}"
                if event["error_code"]
                else None
            ),
            latency_ms=event["latency_ms"],
            gateway=event["gateway"],
            issuer=event["issuer"],
            retry_count=0,
            timestamp=datetime.fromisoformat(event["timestamp"]),
        )

        db.add(db_event)

    db.commit()

    return {
        "scenario": scenario_name,
        "baseline_events": len(baseline_events),
        "incident_events": len(incident_events),
        "events_inserted": len(all_events),
        "baseline_start": baseline_events[0]["timestamp"],
        "baseline_end": baseline_events[-1]["timestamp"],
        "incident_start": incident_events[0]["timestamp"],
        "incident_end": incident_events[-1]["timestamp"],
    }