"""
PayLens AI - Root Cause Engine

Converts incident-detection signals into ranked,
evidence-backed root-cause hypotheses.

The engine evaluates multiple telemetry dimensions
and selects the root cause using both absolute
severity and cross-dimension isolation.
"""

import logging

logger = logging.getLogger(__name__)

from typing import Any, Dict, List


# ---------------------------------------------------------
# Root-cause definitions
# ---------------------------------------------------------

ROOT_CAUSES = {
    "GATEWAY_DEGRADATION": {
        "title": "Gateway / Network Degradation",
        "description": (
            "Failures are concentrated around a payment "
            "gateway or network path."
        ),
    },

    "UPI_DEGRADATION": {
        "title": "UPI Service Degradation",
        "description": (
            "Failures are disproportionately concentrated "
            "in UPI transactions while other payment "
            "methods remain comparatively healthy."
        ),
    },

    "ISSUER_DEGRADATION": {
        "title": "Issuer-Specific Degradation",
        "description": (
            "Failures are disproportionately concentrated "
            "around a particular issuing bank."
        ),
    },

    "PAYMENT_METHOD_DEGRADATION": {
        "title": "Payment Method Degradation",
        "description": (
            "Failures are disproportionately concentrated "
            "in a particular payment method."
        ),
    },

    "GENERAL_PAYMENT_DEGRADATION": {
        "title": "General Payment Degradation",
        "description": (
            "Payment failures increased broadly without "
            "a sufficiently strong single-dimension signal."
        ),
    },

    "INSUFFICIENT_EVIDENCE": {
        "title": "Insufficient Evidence",
        "description": (
            "Available telemetry is not strong enough "
            "to identify a reliable root cause."
        ),
    },
}


# ---------------------------------------------------------
# Utility helpers
# ---------------------------------------------------------

def safe_float(value, default=0.0):
    """
    Safely convert a value to float.
    """

    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def normalize_value(value):
    """
    Normalize categorical telemetry values.

    This makes the RCA engine robust to values such as:

        UPI
        upi
        Upi

    """

    if value is None:
        return None

    return str(value).strip().lower()


def get_nested(
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


def add_evidence(
    evidence_list: List[Dict[str, Any]],
    signal: str,
    strength: str,
    score: float,
    explanation: str
):
    """
    Add one evidence item.
    """

    evidence_list.append({
        "signal": signal,
        "strength": strength,
        "score": round(score, 2),
        "explanation": explanation
    })


# ---------------------------------------------------------
# Gateway analysis
# ---------------------------------------------------------

def evaluate_gateway_degradation(
    analysis: Dict[str, Any]
):
    """
    Evaluate gateway-specific degradation.

    Gateway degradation receives strong evidence when:

    1. Gateway-related errors dominate.
    2. Overall failure rate is elevated.
    3. A specific gateway has a very high failure rate.
    4. One gateway is significantly worse than another.
    """

    score = 0.0
    evidence = []

    dominant_error = normalize_value(
        get_nested(
            analysis,
            "dominant_signals",
            "error_code"
        )
    )

    failure_multiplier = safe_float(
        get_nested(
            analysis,
            "changes",
            "failure_rate_multiplier"
        )
    )

    latency_multiplier = safe_float(
        get_nested(
            analysis,
            "changes",
            "latency_multiplier"
        )
    )

    gateway_rates = get_nested(
        analysis,
        "breakdowns",
        "gateway_failure_rates",
        default={}
    )

    # -----------------------------------------------------
    # Normalize gateway names
    # -----------------------------------------------------

    normalized_gateway_rates = {
        normalize_value(gateway): safe_float(rate)
        for gateway, rate in gateway_rates.items()
    }

    # -----------------------------------------------------
    # Gateway-specific error
    # -----------------------------------------------------

    gateway_errors = {
        "gateway_error",
        "gateway_timeout",
        "network_error",
        "network_timeout",
        "gateway_failure",
        "connection_error",
    }

    if dominant_error in gateway_errors:

        score += 40

        add_evidence(
            evidence,
            "gateway_error",
            "VERY_STRONG",
            40,
            (
                f"{dominant_error.upper()} is the dominant "
                "failure signal and is directly associated "
                "with gateway/network processing."
            )
        )

    # -----------------------------------------------------
    # Overall failure spike
    # -----------------------------------------------------

    if failure_multiplier >= 5:

        score += 20

        add_evidence(
            evidence,
            "failure_rate",
            "STRONG",
            20,
            (
                "Overall failure rate increased by "
                "more than 5x compared with baseline."
            )
        )

    elif failure_multiplier >= 2:

        score += 10

        add_evidence(
            evidence,
            "failure_rate",
            "MODERATE",
            10,
            (
                "Overall failure rate increased to at "
                "least 2x the baseline."
            )
        )

    # -----------------------------------------------------
    # Latency degradation
    # -----------------------------------------------------

    if latency_multiplier >= 4:

        score += 15

        add_evidence(
            evidence,
            "latency",
            "STRONG",
            15,
            (
                "Average payment latency increased "
                "by more than 4x."
            )
        )

    elif latency_multiplier >= 2:

        score += 8

        add_evidence(
            evidence,
            "latency",
            "MODERATE",
            8,
            (
                "Average payment latency increased "
                "to at least 2x the baseline."
            )
        )

    # -----------------------------------------------------
    # Specific gateway degradation
    # -----------------------------------------------------

    if normalized_gateway_rates:

        dominant_gateway = max(
            normalized_gateway_rates,
            key=normalized_gateway_rates.get
        )

        dominant_gateway_rate = (
            normalized_gateway_rates[
                dominant_gateway
            ]
        )

        if dominant_gateway_rate >= 80:

            score += 35

            add_evidence(
                evidence,
                "gateway_failure_rate",
                "VERY_STRONG",
                35,
                (
                    f"{dominant_gateway} has a "
                    f"{dominant_gateway_rate:.2f}% failure rate, "
                    "indicating severe gateway-specific degradation."
                )
            )

        elif dominant_gateway_rate >= 50:

            score += 25

            add_evidence(
                evidence,
                "gateway_failure_rate",
                "STRONG",
                25,
                (
                    f"{dominant_gateway} has a "
                    f"{dominant_gateway_rate:.2f}% failure rate."
                )
            )

        elif dominant_gateway_rate >= 20:

            score += 15

            add_evidence(
                evidence,
                "gateway_failure_rate",
                "MODERATE",
                15,
                (
                    f"{dominant_gateway} has a "
                    f"{dominant_gateway_rate:.2f}% failure rate."
                )
            )

        # -------------------------------------------------
        # Gateway isolation
        # -------------------------------------------------

        other_gateway_rates = [
            rate
            for gateway, rate
            in normalized_gateway_rates.items()
            if gateway != dominant_gateway
        ]

        if other_gateway_rates:

            best_other_rate = max(
                other_gateway_rates
            )

            gateway_gap = (
                dominant_gateway_rate
                - best_other_rate
            )

            if (
                dominant_gateway_rate >= 50
                and gateway_gap >= 30
            ):

                score += 35

                add_evidence(
                    evidence,
                    "gateway_isolation",
                    "VERY_STRONG",
                    35,
                    (
                        f"{dominant_gateway} is failing at "
                        f"{dominant_gateway_rate:.2f}% while the "
                        f"healthiest alternative gateway is at "
                        f"{best_other_rate:.2f}%, showing strong "
                        "gateway-specific isolation."
                    )
                )

            elif (
                dominant_gateway_rate >= 30
                and gateway_gap >= 20
            ):

                score += 20

                add_evidence(
                    evidence,
                    "gateway_isolation",
                    "STRONG",
                    20,
                    (
                        f"{dominant_gateway} has a substantially "
                        "higher failure rate than other gateways."
                    )
                )

    return score, evidence


# ---------------------------------------------------------
# UPI analysis
# ---------------------------------------------------------

def evaluate_upi_degradation(
    analysis: Dict[str, Any]
):
    """
    Evaluate whether UPI is disproportionately affected.
    """

    score = 0.0
    evidence = []

    method_rates = get_nested(
        analysis,
        "breakdowns",
        "payment_method_failure_rates",
        default={}
    )

    # Normalize keys so UPI / upi / Upi are treated identically
    normalized_rates = {
        str(method).strip().upper(): safe_float(rate)
        for method, rate in method_rates.items()
    }

    upi_rate = normalized_rates.get("UPI", 0.0)

    other_rates = [
        rate
        for method, rate in normalized_rates.items()
        if method != "UPI"
    ]

    average_other_rate = (
        sum(other_rates) / len(other_rates)
        if other_rates
        else 0
    )

    if upi_rate >= 15:
        score += 25

        add_evidence(
            evidence,
            "upi_failure_rate",
            "STRONG",
            25,
            (
                f"UPI failure rate is "
                f"{upi_rate:.2f}%."
            )
        )

    if (
        average_other_rate > 0
        and upi_rate >= average_other_rate * 1.5
    ):
        score += 35

        add_evidence(
            evidence,
            "upi_isolation",
            "VERY_STRONG",
            35,
            (
                "UPI failure rate is substantially "
                "higher than other payment methods."
            )
        )

    return score, evidence


# ---------------------------------------------------------
# Issuer analysis
# ---------------------------------------------------------

def evaluate_issuer_degradation(
    analysis: Dict[str, Any]
):
    """
    Evaluate issuer-specific degradation.

    IMPORTANT:

    A single issuer is NOT enough to identify
    issuer-specific degradation.

    At least two issuers must exist so that the
    engine can establish comparative isolation.
    """

    score = 0.0
    evidence = []

    issuer_rates = get_nested(
        analysis,
        "breakdowns",
        "issuer_failure_rates",
        default={}
    )

    if not issuer_rates:

        return score, evidence

    issuer_values = {
    str(issuer).strip().lower(): safe_float(rate)
    for issuer, rate in issuer_rates.items()
}

    # -----------------------------------------------------
    # Cannot establish issuer-specific degradation
    # with only one issuer.
    # -----------------------------------------------------

    if len(issuer_values) < 2:

        return score, evidence
 
    dominant_issuer = max(
        issuer_values,
        key=issuer_values.get
    )

    dominant_rate = (
        issuer_values[
            dominant_issuer
        ]
    )

    other_rates = [
        rate
        for issuer, rate
        in issuer_values.items()
        if issuer != dominant_issuer
    ]

    if not other_rates:

        return score, evidence

    healthiest_other_rate = min(
        other_rates
    )

    difference = (
        dominant_rate
        - healthiest_other_rate
    )

    if dominant_rate >= 50:

        score += 20

        add_evidence(
            evidence,
            "issuer_failure_rate",
            "STRONG",
            20,
            (
                f"{dominant_issuer} has a "
                f"{dominant_rate:.2f}% failure rate."
            )
        )

    elif dominant_rate >= 20:

        score += 10

        add_evidence(
            evidence,
            "issuer_failure_rate",
            "MODERATE",
            10,
            (
                f"{dominant_issuer} has a "
                f"{dominant_rate:.2f}% failure rate."
            )
        )

    # -----------------------------------------------------
    # Comparative isolation
    # -----------------------------------------------------

    if (
        dominant_rate >= 50
        and difference >= 30
    ):

        score += 45

        add_evidence(
            evidence,
            "issuer_isolation",
            "VERY_STRONG",
            45,
            (
                f"{dominant_issuer} is failing at "
                f"{dominant_rate:.2f}% while another issuer "
                f"is at {healthiest_other_rate:.2f}%, indicating "
                "issuer-specific isolation."
            )
        )

    elif (
        dominant_rate >= 30
        and difference >= 20
    ):

        score += 40

        add_evidence(
            evidence,
            "issuer_isolation",
            "VERY_STRONG",
            40,
            (
                f"{dominant_issuer} is failing substantially "
                "more than other issuers."
            )
        )

    return score, evidence


# ---------------------------------------------------------
# Payment-method analysis
# ---------------------------------------------------------

def evaluate_payment_method_degradation(
    analysis: Dict[str, Any]
):
    """
    Evaluate whether one payment method is
    disproportionately affected.
    """

    score = 0.0
    evidence = []

    method_rates = get_nested(
        analysis,
        "breakdowns",
        "payment_method_failure_rates",
        default={}
    )

    normalized_method_rates = {
        normalize_value(method): safe_float(rate)
        for method, rate in method_rates.items()
    }

    if len(normalized_method_rates) < 2:

        return score, evidence

    dominant_method = max(
        normalized_method_rates,
        key=normalized_method_rates.get
    )

    dominant_rate = (
        normalized_method_rates[
            dominant_method
        ]
    )

    other_rates = [
        rate
        for method, rate
        in normalized_method_rates.items()
        if method != dominant_method
    ]

    if not other_rates:

        return score, evidence

    healthiest_other_rate = min(
        other_rates
    )

    difference = (
        dominant_rate
        - healthiest_other_rate
    )

    if dominant_rate >= 50:

        score += 15

        add_evidence(
            evidence,
            "payment_method_failure_rate",
            "STRONG",
            15,
            (
                f"{dominant_method.upper()} has a "
                f"{dominant_rate:.2f}% failure rate."
            )
        )

    elif dominant_rate >= 20:

        score += 10

        add_evidence(
            evidence,
            "payment_method_failure_rate",
            "MODERATE",
            10,
            (
                f"{dominant_method.upper()} has a "
                f"{dominant_rate:.2f}% failure rate."
            )
        )

    if (
        dominant_rate >= 50
        and difference >= 30
    ):

        score += 35

        add_evidence(
            evidence,
            "payment_method_isolation",
            "VERY_STRONG",
            35,
            (
                f"{dominant_method.upper()} is failing at "
                f"{dominant_rate:.2f}% while the healthiest "
                f"alternative method is at "
                f"{healthiest_other_rate:.2f}%."
            )
        )

    elif (
        dominant_rate >= 30
        and difference >= 20
    ):

        score += 35

        add_evidence(
            evidence,
            "payment_method_isolation",
            "STRONG",
            35,
            (
                f"{dominant_method.upper()} is disproportionately "
                "affected compared with other payment methods."
            )
        )

    return score, evidence


# ---------------------------------------------------------
# General degradation
# ---------------------------------------------------------

def evaluate_general_degradation(
    analysis: Dict[str, Any]
):
    """
    General degradation is used as a fallback when
    the system is broadly unhealthy but no specific
    dimension has enough evidence.
    """

    score = 0.0
    evidence = []

    failure_multiplier = safe_float(
        get_nested(
            analysis,
            "changes",
            "failure_rate_multiplier"
        )
    )

    latency_multiplier = safe_float(
        get_nested(
            analysis,
            "changes",
            "latency_multiplier"
        )
    )

    if failure_multiplier >= 2:

        score += 15

        add_evidence(
            evidence,
            "failure_rate",
            "MODERATE",
            15,
            (
                "Overall payment failure rate "
                "increased significantly."
            )
        )

    if latency_multiplier >= 2:

        score += 15

        add_evidence(
            evidence,
            "latency",
            "MODERATE",
            15,
            (
                "Overall payment latency "
                "increased significantly."
            )
        )

    return score, evidence


# ---------------------------------------------------------
# Main root-cause engine
# ---------------------------------------------------------

def investigate_root_cause(
    analysis: Dict[str, Any]
    
):
    issuer_score, issuer_evidence = evaluate_issuer_degradation(analysis)
    method_score, method_evidence = evaluate_payment_method_degradation(analysis)
    upi_score, upi_evidence = evaluate_upi_degradation(analysis)

    logger.debug(
        "RCA component scores: issuer=%s method=%s upi=%s",
        issuer_score,
        method_score,
        upi_score,
    )

    """
    Rank possible root causes using evidence from
    the incident detector.
    """

    if not analysis.get("incident_detected"):

        return {
            "root_cause_available": False,
            "message": (
                "No active incident was detected, "
                "so root-cause investigation is not required."
            ),
            "hypotheses": []
        }

    hypotheses = []
    
    # -----------------------------------------------------
    # Gateway
    # -----------------------------------------------------
    
    

    gateway_score, gateway_evidence = (
        
        
        evaluate_gateway_degradation(
            analysis
        )
    )

    hypotheses.append({
        "cause": "GATEWAY_DEGRADATION",
        "title": ROOT_CAUSES[
            "GATEWAY_DEGRADATION"
        ]["title"],
        "description": ROOT_CAUSES[
            "GATEWAY_DEGRADATION"
        ]["description"],
        "score": gateway_score,
        "evidence": gateway_evidence
    })

    # -----------------------------------------------------
    # UPI
    # -----------------------------------------------------

    upi_score, upi_evidence = (
        evaluate_upi_degradation(
            analysis
        )
    )

    hypotheses.append({
        "cause": "UPI_DEGRADATION",
        "title": ROOT_CAUSES[
            "UPI_DEGRADATION"
        ]["title"],
        "description": ROOT_CAUSES[
            "UPI_DEGRADATION"
        ]["description"],
        "score": upi_score,
        "evidence": upi_evidence
    })

    # -----------------------------------------------------
    # Issuer
    # -----------------------------------------------------

    issuer_score, issuer_evidence = (
        evaluate_issuer_degradation(
            analysis
        )
    )

    hypotheses.append({
        "cause": "ISSUER_DEGRADATION",
        "title": ROOT_CAUSES[
            "ISSUER_DEGRADATION"
        ]["title"],
        "description": ROOT_CAUSES[
            "ISSUER_DEGRADATION"
        ]["description"],
        "score": issuer_score,
        "evidence": issuer_evidence
    })

    # -----------------------------------------------------
    # Payment method
    # -----------------------------------------------------

    method_score, method_evidence = (
        evaluate_payment_method_degradation(
            analysis
        )
    )

    hypotheses.append({
        "cause": "PAYMENT_METHOD_DEGRADATION",
        "title": ROOT_CAUSES[
            "PAYMENT_METHOD_DEGRADATION"
        ]["title"],
        "description": ROOT_CAUSES[
            "PAYMENT_METHOD_DEGRADATION"
        ]["description"],
        "score": method_score,
        "evidence": method_evidence
    })

    # -----------------------------------------------------
    # General
    # -----------------------------------------------------

    general_score, general_evidence = (
        evaluate_general_degradation(
            analysis
        )
    )

    hypotheses.append({
        "cause": "GENERAL_PAYMENT_DEGRADATION",
        "title": ROOT_CAUSES[
            "GENERAL_PAYMENT_DEGRADATION"
        ]["title"],
        "description": ROOT_CAUSES[
            "GENERAL_PAYMENT_DEGRADATION"
        ]["description"],
        "score": general_score,
        "evidence": general_evidence
    })

    # -----------------------------------------------------
    # Sort by evidence score
    # -----------------------------------------------------

    hypotheses.sort(
        key=lambda item: item["score"],
        reverse=True
    )

    top = hypotheses[0]

    # -----------------------------------------------------
    # No useful evidence
    # -----------------------------------------------------

    if top["score"] <= 0:

        return {
            "root_cause_available": False,
            "message": (
                "An incident exists, but available "
                "evidence is insufficient to determine "
                "a reliable root cause."
            ),
            "hypotheses": hypotheses
        }

    # -----------------------------------------------------
    # Determine separation
    # -----------------------------------------------------

    second_score = (
        hypotheses[1]["score"]
        if len(hypotheses) > 1
        else 0
    )

    dominance = (
        (top["score"] - second_score)
        / top["score"]
        if top["score"] > 0
        else 0
    )

    # -----------------------------------------------------
    # Base confidence
    # -----------------------------------------------------

    if top["score"] >= 100:

        base_confidence = 0.90

    elif top["score"] >= 80:

        base_confidence = 0.82

    elif top["score"] >= 60:

        base_confidence = 0.72

    elif top["score"] >= 40:

        base_confidence = 0.60

    else:

        base_confidence = 0.45

    # -----------------------------------------------------
    # Reward separation from competing hypotheses
    # -----------------------------------------------------

    confidence = (
        base_confidence
        + (dominance * 0.10)
    )

    confidence = min(
        max(confidence, 0.0),
        0.99
    )

    confidence_percentage = round(
        confidence * 100,
        2
    )

    # -----------------------------------------------------
    # Explanation
    # -----------------------------------------------------

    explanation_parts = [
        item["explanation"]
        for item in top["evidence"]
    ]

    explanation = " ".join(
        explanation_parts
    )

    # -----------------------------------------------------
    # Final result
    # -----------------------------------------------------

    return {
        "root_cause_available": True,

        "primary_root_cause": {
        "cause": top["cause"],
        "title": top["title"],
        "description": top["description"],
        "confidence": confidence_percentage,
        "score": round(
        top["score"],
        2
        ),
        "evidence": top["evidence"],
        "rank": 1,
        "score_margin": round(
        top["score"] - second_score,
        2
        ),
        "alternative_hypotheses": [
        {
            "cause": hypothesis["cause"],
            "title": hypothesis["title"],
            "score": round(
                hypothesis["score"],
                2
            )
        }
        for hypothesis in hypotheses[1:]
    ]
},
        "explanation": explanation,

        "hypotheses": [
            {
                "cause": hypothesis["cause"],
                "title": hypothesis["title"],
                "score": round(
                    hypothesis["score"],
                    2
                ),
                "evidence": hypothesis["evidence"]
            }
            for hypothesis in hypotheses
        ],

        "reasoning_policy": (
            "Root cause is selected using multiple "
            "telemetry dimensions. Absolute failure rates "
            "alone are insufficient for issuer or payment "
            "method attribution. Comparative isolation and "
            "gateway-specific error signals are weighted "
            "more strongly."
        )
    }