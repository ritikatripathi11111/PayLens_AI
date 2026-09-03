import random
import uuid
from datetime import datetime, timedelta, timezone

from scenarios import SCENARIOS


PAYMENT_METHODS = [
    "UPI",
    "CARD",
    "NETBANKING",
    "WALLET"
]

GATEWAYS = [
    "gateway_a",
    "gateway_b"
]

ISSUERS = [
    "issuer_a",
    "issuer_b",
    "issuer_c"
]


def generate_payment(
    scenario_name="normal",
    timestamp=None
):
    """
    Generate one synthetic payment event.

    scenario_name:
        Determines the type of traffic/failure.

    timestamp:
        Allows the simulator to generate
        time-series payment events.
    """

    if scenario_name not in SCENARIOS:
        raise ValueError(
            f"Unknown scenario: {scenario_name}"
        )

    scenario = SCENARIOS[scenario_name]

    # ---------------------------------------------
    # BASIC PAYMENT INFORMATION
    # ---------------------------------------------

    payment_id = (
        f"pay_{uuid.uuid4().hex[:12]}"
    )

    gateway = random.choice(GATEWAYS)

    payment_method = random.choice(
        PAYMENT_METHODS
    )

    # ---------------------------------------------
    # ISSUER SELECTION
    # ---------------------------------------------

    # In the issuer_decline scenario,
    # issuer_c becomes the problematic issuer.
    if scenario_name == "issuer_decline":

        issuer = random.choices(
            ISSUERS,
            weights=[0.45, 0.45, 0.10]
        )[0]

    else:

        issuer = random.choice(ISSUERS)

    # ---------------------------------------------
    # FAILURE LOGIC
    # ---------------------------------------------

    if (
        scenario_name == "issuer_decline"
        and issuer == "issuer_c"
    ):

        # issuer_c has a high failure rate
        is_failed = random.random() < 0.70

    elif scenario_name == "issuer_decline":

        # Other issuers behave normally
        is_failed = random.random() < 0.03

    else:

        is_failed = (
            random.random()
            < scenario["failure_rate"]
        )

    # ---------------------------------------------
    # LATENCY
    # ---------------------------------------------

    latency = max(
        100,
        int(
            random.gauss(
                scenario["avg_latency_ms"],
                scenario["latency_std_ms"]
            )
        )
    )

    # ---------------------------------------------
    # PAYMENT RESULT
    # ---------------------------------------------

    if is_failed:

        status = "failed"

        if scenario_name == "gateway_timeout":

            error_code = "GATEWAY_TIMEOUT"

            error_description = (
                "Gateway response timeout"
            )

        elif scenario_name == "issuer_decline":

            error_code = "ISSUER_DECLINED"

            error_description = (
                "Payment declined by issuer"
            )

        elif scenario_name == "upi_failure":

            payment_method = "UPI"

            error_code = "UPI_FAILURE"

            error_description = (
                "UPI transaction failed"
            )

        else:

            error_code = "RANDOM_FAILURE"

            error_description = (
                "Random payment failure"
            )

    else:

        status = "captured"

        error_code = None

        error_description = None

    # ---------------------------------------------
    # TIMESTAMP
    # ---------------------------------------------

    if timestamp is None:

        timestamp = datetime.now(
            timezone.utc
        )

    # ---------------------------------------------
    # FINAL EVENT
    # ---------------------------------------------

    return {
        "payment_id": payment_id,

        "merchant_id": "merchant_demo",

        "amount": random.randint(
            100,
            10000
        ),

        "currency": "INR",

        "payment_method": payment_method,

        "status": status,

        "error_code": error_code,

        "error_description": error_description,

        "latency_ms": latency,

        "gateway": gateway,

        "issuer": issuer,

        "retry_count": random.randint(
            0,
            2
        ),

        "timestamp": timestamp.isoformat()
    }


# ---------------------------------------------
# BASIC TEST
# ---------------------------------------------

if __name__ == "__main__":

    start_time = datetime.now(
        timezone.utc
    )

    for i in range(5):

        timestamp = (
            start_time
            + timedelta(minutes=i)
        )

        payment = generate_payment(
            scenario_name="gateway_timeout",
            timestamp=timestamp
        )

        print(payment)