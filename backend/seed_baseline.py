import sqlite3
from datetime import datetime, timedelta


DB_PATH = "paylens.db"

# Your current latest event:
LATEST_EVENT = datetime(2026, 8, 30, 15, 19, 21)

# Put baseline safely inside the previous 60-minute window.
BASELINE_START = LATEST_EVENT - timedelta(minutes=115)


conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()


# ---------------------------------------------------------
# Create healthy baseline events
# ---------------------------------------------------------

events = []

for i in range(40):

    timestamp = BASELINE_START + timedelta(
        seconds=i * 70
    )

    # 2 failures out of 40 = 5% baseline failure rate
    failed = i < 2

    events.append(
        (
            f"baseline_demo_{i}",
            "merchant_demo",
            5000 + i * 10,
            "INR",
            ["CARD", "UPI", "NETBANKING"][i % 3],
            "failed" if failed else "captured",
            "BASELINE_ERROR" if failed else None,
            "Baseline test failure" if failed else None,
            200,
            ["gateway_a", "gateway_b"][i % 2],
            ["issuer_a", "issuer_b", "issuer_c"][i % 3],
            0,
            timestamp.strftime("%Y-%m-%d %H:%M:%S.%f"),
        )
    )


# ---------------------------------------------------------
# Insert baseline events
# ---------------------------------------------------------

cursor.executemany(
    """
    INSERT INTO payment_events (
        payment_id,
        merchant_id,
        amount,
        currency,
        payment_method,
        status,
        error_code,
        error_description,
        latency_ms,
        gateway,
        issuer,
        retry_count,
        timestamp
    )
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """,
    events,
)

conn.commit()


print("Baseline events inserted:", len(events))

print(
    "Baseline time:",
    events[0][-1],
    "→",
    events[-1][-1],
)


conn.close()