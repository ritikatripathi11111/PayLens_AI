
"""
PayLens AI - Scenario Evaluation Suite

Runs deterministic, isolated test scenarios against the same
incident detector and root-cause engine used by the API.

The suite does not touch the production SQLite database.
"""

from datetime import datetime, timedelta
from typing import Any, Dict, List

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from .db import Base
from .incident_detector import analyze_incident
from .models import PaymentEventDB
from .root_cause_engine import investigate_root_cause


WINDOW_MINUTES = 60
END_TIME = datetime(2026, 1, 1, 1, 0, 0)

EXPECTED_ROOT_CAUSES = {
    "gateway_degradation": "GATEWAY_DEGRADATION",
    "upi_degradation": "UPI_DEGRADATION",
    "issuer_degradation": "ISSUER_DEGRADATION",
    "payment_method_degradation": "PAYMENT_METHOD_DEGRADATION",
    "healthy_system": None,
}


def _event_time(start: datetime, index: int) -> datetime:
    return start + timedelta(seconds=index * 59)


def _scenario_config(name: str) -> Dict[str, Any]:
    if name == "gateway_degradation":
        return {
            "failure_count": 18,
            "latency": 1500,
            "methods": ["CARD", "UPI", "NETBANKING"],
            "issuers": ["issuer_a", "issuer_b", "issuer_c"],
            "gateways": ["gateway_a", "gateway_b"],
            "errors": ["GATEWAY_TIMEOUT"],
            "failure_dimension": "gateway",
        }

    if name == "upi_degradation":
        return {
            "failure_count": 18,
            "latency": 700,
            "methods": ["UPI", "CARD", "NETBANKING"],
            "issuers": ["issuer_a", "issuer_b", "issuer_c"],
            "gateways": ["gateway_a", "gateway_b"],
            "errors": ["UPI_ERROR"],
            "failure_dimension": "method",
        }

    if name == "issuer_degradation":
        return {
            "failure_count": 18,
            "latency": 700,
            "methods": ["UPI", "CARD", "NETBANKING"],
            "issuers": ["issuer_a", "issuer_b", "issuer_c"],
            "gateways": ["gateway_a", "gateway_b"],
            "errors": ["ISSUER_DECLINE"],
            "failure_dimension": "issuer",
        }

    if name == "payment_method_degradation":
        return {
            "failure_count": 18,
            "latency": 700,
            "methods": ["CARD", "UPI", "NETBANKING"],
            "issuers": ["issuer_a", "issuer_b", "issuer_c"],
            "gateways": ["gateway_a", "gateway_b"],
            "errors": ["METHOD_ERROR"],
            "failure_dimension": "method_card",
        }

    if name == "healthy_system":
        return {
            "failure_count": 6,
            "latency": 500,
            "methods": ["CARD", "UPI", "NETBANKING"],
            "issuers": ["issuer_a", "issuer_b", "issuer_c"],
            "gateways": ["gateway_a", "gateway_b"],
            "errors": ["ISSUER_DECLINE"],
            "failure_dimension": "balanced",
        }

    raise ValueError(f"Unknown scenario: {name}")


def _build_events(name: str) -> List[PaymentEventDB]:
    cfg = _scenario_config(name)

    events: List[PaymentEventDB] = []

    baseline_start = END_TIME - timedelta(minutes=120)
    current_start = END_TIME - timedelta(minutes=60)

    # Baseline: stable operating state.
    baseline_failures = 3 if name != "healthy_system" else 6

    for i in range(60):
        failed = i < baseline_failures
        events.append(
            PaymentEventDB(
                payment_id=f"{name}-baseline-{i}",
                merchant_id="merchant_demo",
                amount=5000 + i * 10,
                currency="INR",
                payment_method=cfg["methods"][i % len(cfg["methods"])],
                status="failed" if failed else "captured",
                error_code="BASELINE_ERROR" if failed else None,
                error_description=None,
                latency_ms=500,
                gateway=cfg["gateways"][i % len(cfg["gateways"])],
                issuer=cfg["issuers"][i % len(cfg["issuers"])],
                retry_count=0,
                timestamp=_event_time(baseline_start, i),
            )
        )

    for i in range(60):
        failed = i < cfg["failure_count"]

        method = cfg["methods"][i % len(cfg["methods"])]
        issuer = cfg["issuers"][i % len(cfg["issuers"])]
        gateway = cfg["gateways"][i % len(cfg["gateways"])]

        if failed:
            error_code = cfg["errors"][0]

            # Keep the failure distribution intentionally
            # diagnostic: the target dimension is dominant,
            # but competing dimensions still have a small
            # amount of failure activity.
            if name == "upi_degradation":
                method = "UPI" if i < 12 else cfg["methods"][1 if i < 15 else 2]

            elif name == "issuer_degradation":
                issuer = "issuer_c" if i < 12 else cfg["issuers"][0 if i < 15 else 1]

            elif name == "payment_method_degradation":
                method = "CARD" if i < 12 else cfg["methods"][1 if i < 15 else 2]

            elif name == "healthy_system":
                # Keep healthy failures balanced.
                pass

        else:
            error_code = None

        events.append(
            PaymentEventDB(
                payment_id=f"{name}-current-{i}",
                merchant_id="merchant_demo",
                amount=5000 + i * 10,
                currency="INR",
                payment_method=method,
                status="failed" if failed else "captured",
                error_code=error_code,
                error_description=None,
                latency_ms=cfg["latency"],
                gateway=gateway,
                issuer=issuer,
                retry_count=0,
                timestamp=_event_time(current_start, i),
            )
        )

    return events


def _run_scenario(name: str) -> Dict[str, Any]:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)

    SessionLocal = sessionmaker(
        autocommit=False,
        autoflush=False,
        bind=engine,
    )

    db: Session = SessionLocal()

    try:
        db.add_all(_build_events(name))
        db.commit()

        incident = analyze_incident(
            db=db,
            window_minutes=WINDOW_MINUTES,
            end_time=END_TIME,
        )

        rca = investigate_root_cause(incident)

        expected = EXPECTED_ROOT_CAUSES[name]
        detected = bool(incident.get("incident_detected"))
        actual_root_cause = (
            rca.get("primary_root_cause", {}).get("cause")
            if rca.get("root_cause_available")
            else None
        )

        detection_correct = (
            detected is (expected is not None)
        )

        rca_correct = (
            actual_root_cause == expected
            if expected is not None
            else actual_root_cause is None
        )

        return {
            "scenario": name,
            "expected_root_cause": expected,
            "predicted_root_cause": actual_root_cause,
            "incident_detected": detected,
            "expected_incident": expected is not None,
            "detection_correct": detection_correct,
            "rca_correct": rca_correct,
            "confidence": (
                rca.get("primary_root_cause", {}).get("confidence")
                if rca.get("root_cause_available")
                else 0
            ),
            "severity": incident.get("severity", "NONE"),
            "failure_rate": incident.get(
                "current", {}
            ).get("failure_rate", 0),
            "latency_ms": incident.get(
                "current", {}
            ).get("average_latency_ms", 0),
        }

    finally:
        db.close()
        engine.dispose()


def run_evaluation() -> Dict[str, Any]:
    """
    Run all deterministic PayLens evaluation scenarios.

    Returns metrics suitable for the API and dashboard.
    """
    results = [
        _run_scenario(name)
        for name in EXPECTED_ROOT_CAUSES
    ]

    detection_accuracy = round(
        sum(r["detection_correct"] for r in results)
        / len(results)
        * 100,
        2,
    )

    incident_results = [
        r for r in results
        if r["expected_incident"]
    ]

    rca_accuracy = round(
        sum(r["rca_correct"] for r in incident_results)
        / len(incident_results)
        * 100,
        2,
    )

    false_positives = sum(
        1
        for r in results
        if not r["expected_incident"]
        and r["incident_detected"]
    )

    false_negatives = sum(
        1
        for r in results
        if r["expected_incident"]
        and not r["incident_detected"]
    )

    return {
        "status": (
            "passed"
            if detection_accuracy == 100
            and rca_accuracy == 100
            and false_positives == 0
            and false_negatives == 0
            else "needs_review"
        ),
        "scenarios_tested": len(results),
        "incident_scenarios": len(incident_results),
        "detection_accuracy_percent": detection_accuracy,
        "rca_accuracy_percent": rca_accuracy,
        "false_positives": false_positives,
        "false_negatives": false_negatives,
        "results": results,
    }
