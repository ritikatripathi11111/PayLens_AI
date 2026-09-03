import argparse
from datetime import datetime, timedelta, timezone

import requests

from generator import generate_payment
from scenarios import SCENARIOS


# =========================================================
# Configuration
# =========================================================

BACKEND_URL = "http://127.0.0.1:8000"


# =========================================================
# Time helpers
# =========================================================

def parse_start_time(start_time, count):
    """
    Convert the user-provided ISO timestamp into a naive UTC
    datetime.

    If no start time is provided, automatically start the
    simulation `count` minutes before the current UTC time.

    This is useful for real-time incident detection because
    the generated events end approximately at the current time.

    Example:

        count = 120

        Current UTC:
            14:00

        Simulation:
            12:00 -> 14:00

        With incident-start=0.5:

            12:00 -> 13:00  baseline
            13:00 -> 14:00  incident
    """

    # -----------------------------------------------------
    # Automatic real-time simulation
    # -----------------------------------------------------

    if start_time is None:
        now_utc = datetime.now(timezone.utc).replace(
            tzinfo=None,
            microsecond=0
        )

        return now_utc - timedelta(minutes=count)

    # -----------------------------------------------------
    # User-provided simulation time
    # -----------------------------------------------------

    try:
        parsed = datetime.fromisoformat(start_time)

        # If timezone information exists,
        # convert to UTC and remove timezone.
        if parsed.tzinfo is not None:
            parsed = (
                parsed
                .astimezone(timezone.utc)
                .replace(tzinfo=None)
            )

        return parsed.replace(microsecond=0)

    except ValueError:
        raise ValueError(
            "Invalid start-time format. "
            "Use YYYY-MM-DDTHH:MM:SS"
        )


# =========================================================
# Metrics
# =========================================================

def calculate_failure_rate(events):
    """Calculate percentage of failed payments."""

    if not events:
        return 0.0

    failed = sum(
        1
        for event in events
        if event["status"] == "failed"
    )

    return (failed / len(events)) * 100


def calculate_average_latency(events):
    """Calculate average payment latency."""

    latency_values = [
        event["latency_ms"]
        for event in events
        if event.get("latency_ms") is not None
    ]

    if not latency_values:
        return 0.0

    return sum(latency_values) / len(latency_values)


def print_issuer_breakdown(events):
    """Print issuer-level failure rates."""

    print("\nIssuer Breakdown")
    print("-------------------------")

    issuers = sorted(
        set(
            event.get("issuer")
            for event in events
            if event.get("issuer") is not None
        )
    )

    for issuer in issuers:
        issuer_events = [
            event
            for event in events
            if event.get("issuer") == issuer
        ]

        failure_rate = calculate_failure_rate(
            issuer_events
        )

        print(
            f"{issuer:<12}"
            f"{failure_rate:>7.2f}%"
        )


def print_payment_method_breakdown(events):
    """Print payment-method-level failure rates."""

    print("\nPayment Method Breakdown")
    print("-------------------------")

    methods = sorted(
        set(
            event["payment_method"]
            for event in events
        )
    )

    for method in methods:
        method_events = [
            event
            for event in events
            if event["payment_method"] == method
        ]

        failure_rate = calculate_failure_rate(
            method_events
        )

        print(
            f"{method:<12}"
            f"{failure_rate:>7.2f}%"
        )


def print_error_breakdown(events):
    """Print failure error-code distribution."""

    print("\nError Code Breakdown")
    print("-------------------------")

    failed_events = [
        event
        for event in events
        if event["status"] == "failed"
    ]

    if not failed_events:
        print("No failed payments.")
        return

    error_codes = sorted(
        set(
            event.get("error_code")
            for event in failed_events
            if event.get("error_code")
        )
    )

    for error_code in error_codes:
        error_events = [
            event
            for event in failed_events
            if event.get("error_code") == error_code
        ]

        percentage = (
            len(error_events)
            / len(failed_events)
        ) * 100

        print(
            f"{error_code:<25}"
            f"{percentage:>7.2f}%"
        )


# =========================================================
# Backend integration
# =========================================================

def send_event_to_backend(event):
    """Send one payment event to FastAPI."""

    try:
        response = requests.post(
            f"{BACKEND_URL}/events",
            json=event,
            timeout=5
        )

        response.raise_for_status()

        return True

    except requests.RequestException as error:
        print(
            f"Failed to send "
            f"{event['payment_id']}: {error}"
        )

        return False


def send_events(events):
    """Send all generated events to the backend."""

    print(
        "\nSending events to PayLens backend..."
    )

    successful = 0
    failed = 0

    for event in events:

        if send_event_to_backend(event):
            successful += 1
        else:
            failed += 1

    print(
        "\n========== Ingestion Result =========="
    )

    print(
        f"Events generated: {len(events)}"
    )

    print(
        f"Successfully ingested: {successful}"
    )

    print(
        f"Failed to ingest: {failed}"
    )

    print(
        "======================================"
    )


# =========================================================
# Simulation engine
# =========================================================

def run_simulation(
    scenario_name,
    count,
    incident_start=1.0,
    start_time=None
):
    """
    Generate a controlled payment time-series.

    For incident scenarios:

        Before incident:
            normal traffic

        After incident:
            selected incident scenario

    Example with 120 events:

        0.0 ---------------- 0.5 ---------------- 1.0
        |                    |                    |
        |    BASELINE        |     INCIDENT       |
        |                    |                    |
        60 events            60 events
    """

    # -----------------------------------------------------
    # Validate count
    # -----------------------------------------------------

    if count <= 0:
        raise ValueError(
            "Count must be greater than zero."
        )

    # -----------------------------------------------------
    # Validate incident start
    # -----------------------------------------------------

    if not 0 <= incident_start <= 1:
        raise ValueError(
            "incident-start must be between 0 and 1."
        )

    # -----------------------------------------------------
    # Validate scenario
    # -----------------------------------------------------

    if scenario_name not in SCENARIOS:
        raise ValueError(
            f"Unknown scenario: {scenario_name}"
        )

    # -----------------------------------------------------
    # Simulation clock
    # -----------------------------------------------------

    start_datetime = parse_start_time(
        start_time,
        count
    )

    # Each event represents one minute
    # of simulated payment traffic.
    interval = timedelta(minutes=1)

    events = []

    # -----------------------------------------------------
    # Generate events
    # -----------------------------------------------------

    incident_index = int(
        count * incident_start
    )

    for i in range(count):

        progress = i / count

        timestamp = (
            start_datetime
            + interval * i
        )

        # -------------------------------------------------
        # Select active scenario
        # -------------------------------------------------

        if (
            scenario_name != "normal"
            and progress >= incident_start
        ):
            active_scenario = scenario_name
        else:
            active_scenario = "normal"

        # -------------------------------------------------
        # Generate payment
        # -------------------------------------------------

        event = generate_payment(
            scenario_name=active_scenario,
            timestamp=timestamp
        )

        events.append(event)

    # =====================================================
    # Calculate overall metrics
    # =====================================================

    successful = sum(
        1
        for event in events
        if event["status"] == "captured"
    )

    failed = sum(
        1
        for event in events
        if event["status"] == "failed"
    )

    total_amount = sum(
        event["amount"]
        for event in events
    )

    failed_amount = sum(
        event["amount"]
        for event in events
        if event["status"] == "failed"
    )

    average_latency = calculate_average_latency(
        events
    )

    # =====================================================
    # Timeline
    # =====================================================

    end_datetime = (
        start_datetime
        + interval * (count - 1)
    )

    incident_time = (
        start_datetime
        + interval * incident_index
    )

    # =====================================================
    # Output
    # =====================================================

    print(
        "\n========== PayLens Simulation =========="
    )

    print(
        f"Scenario: {scenario_name}"
    )

    print(
        f"Description: "
        f"{SCENARIOS[scenario_name]['description']}"
    )

    print(
        f"Start time: "
        f"{start_datetime.isoformat()}"
    )

    print(
        f"End time: "
        f"{end_datetime.isoformat()}"
    )

    print(
        f"Total payments: {count}"
    )

    print(
        f"Successful: {successful}"
    )

    print(
        f"Failed: {failed}"
    )

    print(
        f"Failure rate: "
        f"{calculate_failure_rate(events):.2f}%"
    )

    print(
        f"Average latency: "
        f"{average_latency:.0f} ms"
    )

    print(
        f"Total transaction value: "
        f"₹{total_amount:,}"
    )

    print(
        f"Failed transaction value: "
        f"₹{failed_amount:,}"
    )

    if scenario_name != "normal":

        print(
            f"Incident begins around: "
            f"{incident_time.isoformat()}"
        )

    print(
        "========================================"
    )

    # =====================================================
    # Detailed breakdowns
    # =====================================================

    print_issuer_breakdown(events)

    print_payment_method_breakdown(events)

    print_error_breakdown(events)

    return events


# =========================================================
# CLI
# =========================================================

def main():

    parser = argparse.ArgumentParser(
        description=(
            "PayLens synthetic payment "
            "incident simulator"
        )
    )

    # -----------------------------------------------------
    # Scenario
    # -----------------------------------------------------

    parser.add_argument(
        "--scenario",
        choices=SCENARIOS.keys(),
        default="normal",
        help="Payment traffic scenario"
    )

    # -----------------------------------------------------
    # Event count
    # -----------------------------------------------------

    parser.add_argument(
        "--count",
        type=int,
        default=100,
        help="Number of payment events"
    )

    # -----------------------------------------------------
    # Incident start
    # -----------------------------------------------------

    parser.add_argument(
        "--incident-start",
        type=float,
        default=1.0,
        help=(
            "Fraction of timeline where "
            "incident begins (0.0 to 1.0)"
        )
    )

    # -----------------------------------------------------
    # Optional manual start time
    # -----------------------------------------------------

    parser.add_argument(
        "--start-time",
        type=str,
        default=None,
        help=(
            "Optional simulation start time in ISO format. "
            "If omitted, simulation automatically ends "
            "around current UTC time."
        )
    )

    # -----------------------------------------------------
    # Backend sending
    # -----------------------------------------------------

    parser.add_argument(
        "--send",
        action="store_true",
        help="Send events to FastAPI backend"
    )

    args = parser.parse_args()

    # =====================================================
    # Run simulation
    # =====================================================

    events = run_simulation(
        scenario_name=args.scenario,
        count=args.count,
        incident_start=args.incident_start,
        start_time=args.start_time
    )

    # =====================================================
    # Send events
    # =====================================================

    if args.send:
        send_events(events)


# =========================================================
# Entry point
# =========================================================

if __name__ == "__main__":
    main()