import requests
import csv
import os
from datetime import datetime, timezone

RPC_URL = os.environ.get("RPC_URL")

def get_signatures_for_address(address, limit=15):
    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "getSignaturesForAddress",
        "params": [address, {"limit": limit}]
    }
    response = requests.post(RPC_URL, json=payload, timeout=30)
    data = response.json()
    return data.get("result", [])

def save_to_csv(filename, rows):
    os.makedirs(os.path.dirname(filename), exist_ok=True)
    file_exists = os.path.isfile(filename)

    with open(filename, "a", newline="") as f:
        writer = csv.writer(f)
        if not file_exists:
            writer.writerow(["timestamp", "signature", "address", "slot", "note"])
        writer.writerows(rows)

if __name__ == "__main__":
    print("Starting Solana Staging Monitor...")

    if not RPC_URL:
        print("Error: RPC_URL not found in environment")
        exit(1)

    # System Program - durable nonce instructions go through here
    SYSTEM_PROGRAM = "11111111111111111111111111111111"

    print("Fetching recent signatures...")
    signatures = get_signatures_for_address(SYSTEM_PROGRAM, limit=10)

    rows = []
    for sig in signatures:
        rows.append([
            datetime.now(timezone.utc).isoformat(),
            sig.get("signature"),
            SYSTEM_PROGRAM,
            sig.get("slot"),
            "system_program_activity"
        ])

    save_to_csv("data/events.csv", rows)

    print(f"Saved {len(rows)} events to data/events.csv")
    print("Collector finished successfully.")