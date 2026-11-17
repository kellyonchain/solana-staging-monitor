import requests
import csv
import os
from datetime import datetime, timezone

RPC_URL = os.environ.get("RPC_URL")

SYSTEM_PROGRAM = "11111111111111111111111111111111"

def get_recent_signatures(address: str, limit: int = 15):
    """Fetch recent signatures for a given address."""
    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "getSignaturesForAddress",
        "params": [address, {"limit": limit}]
    }

    try:
        response = requests.post(RPC_URL, json=payload, timeout=30)
        response.raise_for_status()
        data = response.json()
        return data.get("result", [])
    except Exception as e:
        print(f"Error fetching signatures: {e}")
        return []


def save_events(filepath: str, rows: list):
    """Save events to CSV (append mode)."""
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    file_exists = os.path.isfile(filepath)

    with open(filepath, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        if not file_exists:
            writer.writerow([
                "timestamp",
                "signature",
                "address",
                "slot",
                "err",
                "note"
            ])
        writer.writerows(rows)


def main():
    print("========================================")
    print(" Solana Staging Monitor - Collector")
    print("========================================")

    if not RPC_URL:
        print("❌ ERROR: RPC_URL not found in environment variables.")
        exit(1)

    print("📡 Fetching recent System Program activity...")
    signatures = get_recent_signatures(SYSTEM_PROGRAM, limit=12)

    if not signatures:
        print("No signatures found.")
        return

    rows = []
    for sig in signatures:
        rows.append([
            datetime.now(timezone.utc).isoformat(),
            sig.get("signature"),
            SYSTEM_PROGRAM,
            sig.get("slot"),
            sig.get("err"),
            "system_program_potential_nonce_activity"
        ])

    save_events("data/events.csv", rows)

    print(f"✅ Saved {len(rows)} events to data/events.csv")
    print("Collector finished successfully.")
    print("========================================")


if __name__ == "__main__":
    main()