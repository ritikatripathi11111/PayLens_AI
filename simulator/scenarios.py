SCENARIOS = {
    "normal": {
        "failure_rate": 0.03,
        "avg_latency_ms": 900,
        "latency_std_ms": 150,
        "description": "Normal payment traffic"
    },

    "gateway_timeout": {
        "failure_rate": 0.25,
        "avg_latency_ms": 4500,
        "latency_std_ms": 500,
        "description": "Gateway timeout spike"
    },

    "issuer_decline": {
        "failure_rate": 0.22,
        "avg_latency_ms": 1100,
        "latency_std_ms": 150,
        "description": "Issuer-specific decline spike"
    },

    "upi_failure": {
        "failure_rate": 0.28,
        "avg_latency_ms": 1800,
        "latency_std_ms": 250,
        "description": "UPI-specific failure spike"
    },

    "random_failures": {
        "failure_rate": 0.03,
        "avg_latency_ms": 1000,
        "latency_std_ms": 150,
        "description": "Random isolated failures"
    }
}