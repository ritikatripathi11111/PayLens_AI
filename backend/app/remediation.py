from typing import Dict, Any, List


# =========================================================
# Remediation Engine
# =========================================================
#
# This module does NOT execute real payment-routing actions.
# It generates safe, advisory recommendations and performs
# a "what-if" recovery simulation.
#
# =========================================================


def calculate_recovery_score(
    current_failure_rate: float,
    current_latency: float,
    baseline_failure_rate: float,
    baseline_latency: float,
) -> float:
    """
    Estimate how much recovery could be achieved.

    This is a simulation score, NOT a production prediction.
    """

    if current_failure_rate <= baseline_failure_rate:
        failure_improvement = 0.0
    else:
        failure_improvement = (
            current_failure_rate - baseline_failure_rate
        ) / current_failure_rate

    if current_latency <= baseline_latency:
        latency_improvement = 0.0
    else:
        latency_improvement = (
            current_latency - baseline_latency
        ) / current_latency

    recovery_score = (
        failure_improvement * 0.65
        + latency_improvement * 0.35
    )

    return round(
        min(max(recovery_score, 0.0), 1.0) * 100,
        2
    )


# =========================================================
# Recommended Actions
# =========================================================

def generate_recommendations(
    root_cause: str,
    dominant_gateway: str | None = None,
    dominant_error: str | None = None,
    current_failure_rate: float = 0.0,
    current_latency: float = 0.0,
) -> List[Dict[str, Any]]:
    """
    Generate actionable but non-executing recommendations.
    """

    recommendations = []

    # -----------------------------------------------------
    # Gateway degradation
    # -----------------------------------------------------

    if root_cause == "GATEWAY_DEGRADATION":

        recommendations.append(
            {
                "priority": "P0",
                "action": "REDUCE_AFFECTED_GATEWAY_TRAFFIC",
                "title": "Reduce traffic to affected gateway",
                "description": (
                    f"Gateway {dominant_gateway or 'the affected gateway'} "
                    "shows elevated failure or latency. "
                    "Reduce traffic according to the merchant's "
                    "configured routing policy."
                ),
                "safe": True,
                "execution": "ADVISORY_ONLY",
                
                "decision_basis": [
                (
                    f"Primary root cause is gateway degradation "
                    f"with incident failure rate at "
                    f"{current_failure_rate:.2f}%."
                ),
                (
                    f"{dominant_error or 'Gateway-related failures'} "
                    "is the dominant failure signal."
                ),
                (
                    f"Average payment latency is "
                    f"{current_latency:.0f} ms, indicating degraded "
                    "payment-path performance."
                ),
                (
                    "Reducing affected-gateway traffic limits exposure "
                    "to the degraded payment path."
                ),
            ],
            }
        )

        recommendations.append(
            {
                "priority": "P0",
                "action": "TRAFFIC_FAILOVER",
                "title": "Prefer healthier payment route",
                "description": (
                    "Where routing policy permits, shift eligible "
                    "traffic toward healthier payment infrastructure."
                ),
                "safe": True,
                "execution": "ADVISORY_ONLY",
                "decision_basis": [
                (
                    f"Gateway degradation is the selected root cause "
                    f"with {current_failure_rate:.2f}% incident failure rate."
                ),
                (
                    f"The dominant failure signal is "
                    f"{dominant_error or 'gateway-related failure'}."
                ),
                (
                    "Failover is recommended to reduce dependency on "
                    "the affected payment route."
                ),
                (
                    "The action remains advisory because actual routing "
                    "depends on merchant configuration and available capacity."
                ),
            ],
            }
        )

        recommendations.append(
            {
                "priority": "P1",
                "action": "RETRY_TIMEOUTS",
                "title": "Retry transient timeout failures",
                "description": (
                    "Retry eligible timeout failures using "
                    "bounded exponential backoff. Avoid repeated "
                    "retries for the same payment."
                ),
                "safe": True,
                "execution": "ADVISORY_ONLY",
            }
        )

        recommendations.append(
            {
                "priority": "P1",
                "action": "MONITOR_RECOVERY",
                "title": "Monitor recovery",
                "description": (
                    "Continue monitoring failure rate, latency, "
                    "and timeout frequency after mitigation."
                ),
                "safe": True,
                "execution": "ADVISORY_ONLY",
            }
        )

    # -----------------------------------------------------
    # UPI degradation
    # -----------------------------------------------------

    elif root_cause == "UPI_DEGRADATION":

        recommendations.append(
            {
                "priority": "P0",
                "action": "MONITOR_UPI_HEALTH",
                "title": "Investigate UPI degradation",
                "description": (
                    "Inspect UPI-specific failure and latency "
                    "metrics to identify the affected path."
                ),
                "safe": True,
                "execution": "ADVISORY_ONLY",
            }
        )

        recommendations.append(
            {
                "priority": "P1",
                "action": "OFFER_ALTERNATIVE_METHOD",
                "title": "Offer alternative payment methods",
                "description": (
                    "Where appropriate, offer customers an "
                    "alternative payment method instead of "
                    "repeatedly retrying the same UPI attempt."
                ),
                "safe": True,
                "execution": "ADVISORY_ONLY",
            }
        )

    # -----------------------------------------------------
    # Issuer degradation
    # -----------------------------------------------------

    elif root_cause == "ISSUER_DEGRADATION":

        recommendations.append(
            {
                "priority": "P0",
                "action": "ISOLATE_ISSUER_SIGNAL",
                "title": "Investigate issuer-specific failures",
                "description": (
                    "Check issuer-level decline and timeout "
                    "patterns before applying broader mitigation."
                ),
                "safe": True,
                "execution": "ADVISORY_ONLY",
            }
        )

        recommendations.append(
            {
                "priority": "P1",
                "action": "OFFER_ALTERNATIVE_METHOD",
                "title": "Offer alternative payment method",
                "description": (
                    "If the issuer continues failing, allow the "
                    "customer to use another supported payment method."
                ),
                "safe": True,
                "execution": "ADVISORY_ONLY",
            }
        )

    # -----------------------------------------------------
    # Payment method degradation
    # -----------------------------------------------------

    elif root_cause == "PAYMENT_METHOD_DEGRADATION":

        recommendations.append(
            {
                "priority": "P0",
                "action": "INVESTIGATE_PAYMENT_METHOD",
                "title": "Investigate affected payment method",
                "description": (
                    "Inspect method-specific failure rates and "
                    "latency before applying mitigation."
                ),
                "safe": True,
                "execution": "ADVISORY_ONLY",
            }
        )

        recommendations.append(
            {
                "priority": "P1",
                "action": "OFFER_ALTERNATIVE_METHOD",
                "title": "Offer alternative payment method",
                "description": (
                    "Provide an alternative payment method to "
                    "reduce customer payment friction."
                ),
                "safe": True,
                "execution": "ADVISORY_ONLY",
            }
        )

    # -----------------------------------------------------
    # General degradation
    # -----------------------------------------------------

    else:

        recommendations.append(
            {
                "priority": "P1",
                "action": "INVESTIGATE_PAYMENT_HEALTH",
                "title": "Investigate payment health",
                "description": (
                    "Inspect payment infrastructure, gateway, "
                    "issuer, and method-level telemetry."
                ),
                "safe": True,
                "execution": "ADVISORY_ONLY",
            }
        )

        recommendations.append(
            {
                "priority": "P1",
                "action": "MONITOR_METRICS",
                "title": "Monitor failure rate and latency",
                "description": (
                    "Continue observing payment health to determine "
                    "whether the degradation is recovering."
                ),
                "safe": True,
                "execution": "ADVISORY_ONLY",
            }
        )

    return recommendations


# =========================================================
# Recovery Simulation
# =========================================================

def simulate_recovery(
    root_cause: str,
    current_failure_rate: float,
    current_latency: float,
    baseline_failure_rate: float,
    baseline_latency: float,
    failed_events: int = 0,
    failed_transaction_value: float = 0.0,
    dominant_gateway: str | None = None,
) -> Dict[str, Any]:
    """
    Perform a deterministic what-if recovery simulation.

    IMPORTANT:
    This does NOT modify real payment traffic.

    It estimates what could happen if an appropriate
    remediation strategy were applied.
    """

    # -----------------------------------------------------
    # Validate values
    # -----------------------------------------------------

    current_failure_rate = max(
        float(current_failure_rate),
        0.0
    )

    current_latency = max(
        float(current_latency),
        0.0
    )

    baseline_failure_rate = max(
        float(baseline_failure_rate),
        0.0
    )

    baseline_latency = max(
        float(baseline_latency),
        0.0
    )

    # -----------------------------------------------------
    # Determine simulated improvement
    # -----------------------------------------------------

    if root_cause == "GATEWAY_DEGRADATION":

        # Gateway incidents should have strong recovery
        # potential because traffic redistribution can
        # reduce exposure to a degraded route.

        failure_reduction_factor = 0.55
        latency_reduction_factor = 0.60

        strategy = (
            "Simulate traffic redistribution away from "
            f"{dominant_gateway or 'the affected gateway'}"
        )

    elif root_cause == "UPI_DEGRADATION":

        failure_reduction_factor = 0.35
        latency_reduction_factor = 0.30

        strategy = (
            "Simulate reduced UPI exposure and "
            "alternative payment-method selection"
        )

    elif root_cause == "ISSUER_DEGRADATION":

        failure_reduction_factor = 0.30
        latency_reduction_factor = 0.25

        strategy = (
            "Simulate routing eligible customers toward "
            "alternative payment paths"
        )

    elif root_cause == "PAYMENT_METHOD_DEGRADATION":

        failure_reduction_factor = 0.30
        latency_reduction_factor = 0.25

        strategy = (
            "Simulate increased availability of "
            "alternative payment methods"
        )

    else:

        failure_reduction_factor = 0.20
        latency_reduction_factor = 0.20

        strategy = (
            "Simulate general payment-health mitigation"
        )

    # -----------------------------------------------------
    # Calculate simulated values
    # -----------------------------------------------------

    simulated_failure_rate = (
        current_failure_rate
        * (1 - failure_reduction_factor)
    )

    simulated_latency = (
        current_latency
        * (1 - latency_reduction_factor)
    )

    # Never claim simulation is better than baseline.
    simulated_failure_rate = max(
        simulated_failure_rate,
        baseline_failure_rate
    )

    simulated_latency = max(
        simulated_latency,
        baseline_latency
    )

    # -----------------------------------------------------
    # Estimate recovered transactions
    # -----------------------------------------------------

    if failed_events > 0:

        recovered_transactions = round(
            failed_events
            * failure_reduction_factor
        )

    else:

        recovered_transactions = 0

    # -----------------------------------------------------
    # Estimate recovered transaction value
    # -----------------------------------------------------

    if failed_events > 0 and failed_transaction_value > 0:

        recovered_value = (
            failed_transaction_value
            * failure_reduction_factor
        )

    else:

        recovered_value = 0.0

    # -----------------------------------------------------
    # Recovery score
    # -----------------------------------------------------

    recovery_score = calculate_recovery_score(
        current_failure_rate=current_failure_rate,
        current_latency=current_latency,
        baseline_failure_rate=baseline_failure_rate,
        baseline_latency=baseline_latency,
    )

    # -----------------------------------------------------
    # Recovery status
    # -----------------------------------------------------

    if (
        simulated_failure_rate <= baseline_failure_rate * 1.25
        and simulated_latency <= baseline_latency * 1.25
    ):

        recovery_status = "NEAR_BASELINE"

    elif (
        simulated_failure_rate < current_failure_rate
        and simulated_latency < current_latency
    ):

        recovery_status = "IMPROVING"

    else:

        recovery_status = "INSUFFICIENT_RECOVERY"

    # -----------------------------------------------------
    # Return simulation
    # -----------------------------------------------------

    return {
        "simulation_type": "WHAT_IF",
        "execution": "NOT_EXECUTED",
        "strategy": strategy,

        "before": {
            "failure_rate": round(
                current_failure_rate,
                2
            ),
            "average_latency_ms": round(
                current_latency,
                2
            ),
        },

        "after": {
            "failure_rate": round(
                simulated_failure_rate,
                2
            ),
            "average_latency_ms": round(
                simulated_latency,
                2
            ),
        },

        "improvement": {
            "failure_rate_reduction_percent": round(
                current_failure_rate
                - simulated_failure_rate,
                2
            ),
            "latency_reduction_ms": round(
                current_latency
                - simulated_latency,
                2
            ),
            "estimated_recovered_transactions": (
                recovered_transactions
            ),
            "estimated_recovered_transaction_value": round(
                recovered_value,
                2
            ),
        },

        "recovery_score": recovery_score,

        "recovery_status": recovery_status,

        "limitations": [
            "This is a what-if simulation, not a production prediction.",
            "No real payment-routing action is executed.",
            "Actual recovery depends on gateway, issuer, network, and merchant configuration.",
            "Estimated recovered transactions are scenario-based."
        ]
    }


# =========================================================
# Complete Remediation Analysis
# =========================================================

def build_remediation_analysis(
    root_cause: str,
    current_failure_rate: float,
    current_latency: float,
    baseline_failure_rate: float,
    baseline_latency: float,
    failed_events: int = 0,
    failed_transaction_value: float = 0.0,
    dominant_gateway: str | None = None,
    dominant_error: str | None = None,
) -> Dict[str, Any]:
    """
    Generate recommendations + recovery simulation.
    """

    recommendations = generate_recommendations(
        root_cause=root_cause,
        dominant_gateway=dominant_gateway,
        dominant_error=dominant_error,
        current_failure_rate=current_failure_rate,
        current_latency=current_latency,
    )

    recovery = simulate_recovery(
        root_cause=root_cause,
        current_failure_rate=current_failure_rate,
        current_latency=current_latency,
        baseline_failure_rate=baseline_failure_rate,
        baseline_latency=baseline_latency,
        failed_events=failed_events,
        failed_transaction_value=failed_transaction_value,
        dominant_gateway=dominant_gateway,
    )

    return {
        "remediation": {
            "root_cause": root_cause,
            "recommendations": recommendations,
        },
        "recovery_simulation": recovery,
    }
    