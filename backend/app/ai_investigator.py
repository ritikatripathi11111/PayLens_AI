"""
PayLens AI - AI Investigator

The deterministic incident detector and root-cause engine
remain the source of truth.

This module converts structured evidence into a concise
incident investigation report.

LLM integration is optional. If no LLM/API key is
configured, PayLens uses a deterministic fallback report.
"""

import os
from typing import Any, Dict, List


# ---------------------------------------------------------
# Configuration
# ---------------------------------------------------------

AI_PROVIDER = os.getenv(
    "PAYLENS_AI_PROVIDER",
    "fallback"
)


# ---------------------------------------------------------
# Helpers
# ---------------------------------------------------------

def get_value(
    data: Dict[str, Any],
    *keys,
    default=None
):
    """
    Safely retrieve nested dictionary values.
    """

    current = data

    for key in keys:

        if not isinstance(current, dict):
            return default

        current = current.get(key)

        if current is None:
            return default

    return current


def format_percentage(value):
    if value is None:
        return "N/A"

    return f"{float(value):.2f}%"


def format_multiplier(value):
    if value is None:
        return "N/A"

    return f"{float(value):.2f}x"


# ---------------------------------------------------------
# Evidence extraction
# ---------------------------------------------------------

def extract_evidence(
    incident_analysis: Dict[str, Any],
    root_cause_analysis: Dict[str, Any]
):
    """
    Convert detector + RCA output into concise,
    evidence-grounded facts.
    """

    facts: List[str] = []

    baseline_failure = get_value(
        incident_analysis,
        "baseline",
        "failure_rate"
    )

    current_failure = get_value(
        incident_analysis,
        "current",
        "failure_rate"
    )

    failure_multiplier = get_value(
        incident_analysis,
        "changes",
        "failure_rate_multiplier"
    )

    baseline_latency = get_value(
        incident_analysis,
        "baseline",
        "average_latency_ms"
    )

    current_latency = get_value(
        incident_analysis,
        "current",
        "average_latency_ms"
    )

    latency_multiplier = get_value(
        incident_analysis,
        "changes",
        "latency_multiplier"
    )

    dominant_error = get_value(
        incident_analysis,
        "dominant_signals",
        "error_code"
    )

    gateway_rates = get_value(
        incident_analysis,
        "breakdowns",
        "gateway_failure_rates",
        default={}
    )

    # -----------------------------------------------------
    # Failure-rate evidence
    # -----------------------------------------------------

    if (
        baseline_failure is not None
        and current_failure is not None
    ):

        facts.append(
            (
                f"Payment failure rate increased from "
                f"{format_percentage(baseline_failure)} "
                f"to "
                f"{format_percentage(current_failure)} "
                f"({format_multiplier(failure_multiplier)} "
                f"of baseline)."
            )
        )

    # -----------------------------------------------------
    # Latency evidence
    # -----------------------------------------------------

    if (
        baseline_latency is not None
        and current_latency is not None
    ):

        facts.append(
            (
                f"Average payment latency increased from "
                f"{baseline_latency:.0f} ms to "
                f"{current_latency:.0f} ms "
                f"({format_multiplier(latency_multiplier)} "
                f"of baseline)."
            )
        )

    # -----------------------------------------------------
    # Error evidence
    # -----------------------------------------------------

    if dominant_error:

        error_rates = get_value(
            incident_analysis,
            "breakdowns",
            "error_code_failure_rates",
            default={}
        )

        error_rate = error_rates.get(
            dominant_error
        )

        if error_rate is not None:

            facts.append(
                (
                    f"{dominant_error} accounts for "
                    f"{format_percentage(error_rate)} "
                    f"of failures associated with the "
                    f"observed error-code breakdown."
                )
            )

        else:

            facts.append(
                (
                    f"{dominant_error} is the dominant "
                    f"observed failure error."
                )
            )

    # -----------------------------------------------------
    # Gateway breadth
    # -----------------------------------------------------

    elevated_gateways = [
        gateway
        for gateway, rate in gateway_rates.items()
        if float(rate) >= 10
    ]

    if len(elevated_gateways) >= 2:

        facts.append(
            (
                "Multiple payment gateways show "
                "elevated failure rates, which supports "
                "a broader system or network issue rather "
                "than an isolated gateway correlation."
            )
        )

    return facts


# ---------------------------------------------------------
# Secondary correlations
# ---------------------------------------------------------

def extract_secondary_correlations(
    incident_analysis: Dict[str, Any],
    root_cause_analysis: Dict[str, Any]
):
    """
    Identify signals that are interesting but should
    NOT automatically be treated as root causes.
    """

    correlations = []

    hypotheses = root_cause_analysis.get(
        "hypotheses",
        []
    )

    primary = root_cause_analysis.get(
        "primary_root_cause",
        {}
    ).get(
        "cause"
    )

    for hypothesis in hypotheses:

        cause = hypothesis.get(
            "cause"
        )

        if cause == primary:
            continue

        score = hypothesis.get(
            "score",
            0
        )

        if score <= 0:
            continue

        correlations.append(
            {
                "cause": cause,
                "title": hypothesis.get(
                    "title"
                ),
                "score": score,
                "note": (
                    "Observed correlation only; "
                    "not established as the primary "
                    "root cause."
                )
            }
        )

    return correlations


# ---------------------------------------------------------
# Recommended actions
# ---------------------------------------------------------

def generate_recommendations(
    root_cause_analysis: Dict[str, Any],
    incident_analysis: Dict[str, Any]
):
    """
    Generate safe, operational recommendations.

    These are recommendations only.
    PayLens does not automatically execute production
    financial actions.
    """

    primary = get_value(
        root_cause_analysis,
        "primary_root_cause",
        "cause"
    )

    recommendations = []

    if primary == "GATEWAY_DEGRADATION":

        recommendations = [
            (
                "Inspect gateway and upstream network "
                "health metrics for elevated latency "
                "and timeout rates."
            ),
            (
                "Check gateway-specific timeout and "
                "error-rate telemetry."
            ),
            (
                "Evaluate traffic redistribution or "
                "failover according to the merchant's "
                "configured routing policy."
            ),
            (
                "Continue monitoring failure rate and "
                "latency to confirm recovery."
            )
        ]

    elif primary == "UPI_DEGRADATION":

        recommendations = [
            (
                "Inspect UPI provider and upstream "
                "service health."
            ),
            (
                "Compare UPI failure rates across "
                "providers and time windows."
            ),
            (
                "Consider alternative payment methods "
                "where merchant routing policy allows."
            ),
            (
                "Monitor UPI recovery before closing "
                "the incident."
            )
        ]

    elif primary == "ISSUER_DEGRADATION":

        recommendations = [
            (
                "Investigate the affected issuer's "
                "authorization and response metrics."
            ),
            (
                "Compare the issuer against other "
                "issuers during the same time window."
            ),
            (
                "Avoid treating isolated issuer "
                "correlation as confirmed causation "
                "without additional telemetry."
            )
        ]

    elif primary == "PAYMENT_METHOD_DEGRADATION":

        recommendations = [
            (
                "Inspect the affected payment method's "
                "provider and authorization metrics."
            ),
            (
                "Compare the affected method with "
                "other payment methods."
            ),
            (
                "Evaluate alternative payment methods "
                "where business policy permits."
            )
        ]

    else:

        recommendations = [
            (
                "Continue collecting telemetry to "
                "increase root-cause confidence."
            ),
            (
                "Compare failures across gateway, "
                "issuer, and payment-method dimensions."
            ),
            (
                "Escalate to payment operations if "
                "degradation persists."
            )
        ]

    return recommendations


# ---------------------------------------------------------
# Deterministic AI-style report
# ---------------------------------------------------------

def generate_fallback_report(
    incident_analysis: Dict[str, Any],
    root_cause_analysis: Dict[str, Any]
):
    """
    Generate a high-quality report without an external
    LLM.

    This guarantees that the demo still works even when
    an AI provider is unavailable.
    """

    primary = root_cause_analysis.get(
        "primary_root_cause",
        {}
    )

    cause = primary.get(
        "cause",
        "UNKNOWN"
    )

    title = primary.get(
        "title",
        "Unknown Root Cause"
    )

    confidence = primary.get(
        "confidence",
        0
    )

    severity = incident_analysis.get(
        "severity",
        "UNKNOWN"
    )

    facts = extract_evidence(
        incident_analysis,
        root_cause_analysis
    )

    secondary = extract_secondary_correlations(
        incident_analysis,
        root_cause_analysis
    )

    recommendations = generate_recommendations(
        root_cause_analysis,
        incident_analysis
    )

    total_events = get_value(
    incident_analysis,
    "current",
    "events",
    default=0
)

    failed_events = get_value(
      incident_analysis,
      "current",
      "failed_events",
       default=0
    )

    failed_transaction_value = get_value(
     incident_analysis,
     "current",
     "failed_transaction_value",
     default=0
    )

    current_failure_rate = get_value(
        incident_analysis,
        "current",
        "failure_rate"
    )

    current_latency = get_value(
        incident_analysis,
        "current",
        "average_latency_ms"
    )

    # -----------------------------------------------------
    # What happened
    # -----------------------------------------------------

    what_happened = (
    f"A {severity}-severity payment incident was "
    f"detected during the analyzed window. "
    f"{total_events} payment events were observed, "
    f"of which {failed_events} failed. "
    f"The current failure rate was "
    f"{format_percentage(current_failure_rate)}."
)

    # -----------------------------------------------------
    # Why
    # -----------------------------------------------------

    why = (
        f"The strongest evidence supports "
        f"{title} with {confidence:.2f}% confidence. "
        f"The conclusion is based on multiple telemetry "
        f"signals rather than a single correlated field."
    )

    # -----------------------------------------------------
    # Impact
    # -----------------------------------------------------

    impact = {
    "total_events": total_events,
    "failed_events": failed_events,
    "current_failure_rate": current_failure_rate,
    "average_latency_ms": current_latency,
    "failed_transaction_value": (
        failed_transaction_value
       )
    }

    return {
        "mode": "deterministic_fallback",

        "incident_summary": {
            "severity": severity,
            "root_cause": cause,
            "root_cause_title": title,
            "confidence": confidence
        },

        "what_happened": what_happened,

        "why_it_happened": why,

        "evidence": facts,

        "secondary_correlations": secondary,

        "impact": impact,

        "recommended_actions": recommendations,

        "limitations": [
            (
                "Root cause confidence is based only on "
                "available payment telemetry."
            ),
            (
                "Correlations involving issuer, gateway, "
                "or payment method are not treated as "
                "causal without supporting evidence."
            ),
            (
                "Recommendations are advisory and do not "
                "automatically execute financial or routing "
                "actions."
            )
        ]
    }


# ---------------------------------------------------------
# Optional LLM integration point
# ---------------------------------------------------------

def investigate_with_ai(
    incident_analysis: Dict[str, Any],
    root_cause_analysis: Dict[str, Any]
):
    """
    Main AI investigation entry point.

    Currently the safe deterministic fallback is used.

    Later we can connect an LLM here while preserving
    the same evidence-grounded interface.
    """

    # -----------------------------------------------------
    # Safety-first behavior
    # -----------------------------------------------------

    if AI_PROVIDER == "fallback":

        return generate_fallback_report(
            incident_analysis,
            root_cause_analysis
        )

    # -----------------------------------------------------
    # Future provider integration
    # -----------------------------------------------------

    return generate_fallback_report(
        incident_analysis,
        root_cause_analysis
    )