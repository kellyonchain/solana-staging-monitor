import requests
import csv
import os
from datetime import datetime, timezone

RPC_URL = os.environ.get("RPC_URL")

def get_signatures_for_address(address, limit=20):
    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "getSignaturesForAddress",
        "params": [address, {"limit": limit}]
    }
    response = requests.post(RPC_URL, json=payload, timeout=30)
    return response.json().get("result", [])

def save_to_csv(filename, rows):
    file_exists = os.path.isfile(filename)
    
    with open(filename, "a", newline="") as f:
        writer = csv.writer(f)
        if not file_exists:
            writer.writerow(["timestamp", "signature", "address", "note"])
        writer.writerows(rows)

if __name__ == "__main__":
    print("Starting collector...")

    if not RPC_URL:
        print("Error: RPC_URL not found")
        exit(1)

    # Temporary test address (System Program)
    test_address = "11111111111111111111111111111111"
    
    signatures = get_signatures_for_address(test_address, limit=5)
    
    rows = []
    for sig in signatures:
        rows.append([
            datetime.now(timezone.utc).isoformat(),
            sig.get("signature"),
            test_address,
            "test"
        ])

    os.makedirs("data", exist_ok=True)
    save_to_csv("data/events.csv", rows)

    print(f"Saved {len(rows)} events.")
    print("Collector finished.")