import requests
import os

# Put your Helius RPC URL here (keep it private later)
RPC_URL = "PASTE_YOUR_HELIUS_RPC_URL_HERE"
def get_slot():
    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "getSlot"
    }
    response = requests.post(RPC_URL, json=payload)
    data = response.json()
    return data.get("result")

if __name__ == "__main__":
    slot = get_slot()
    print("Current Solana slot:", slot)
    print("Collector is working.")