"""
Solana Staging Monitor - collector

Scans recent finalized blocks and flags transactions that use System Program
nonce instructions (durable nonces), then scores them with simple, explainable
signals. Output goes to data/events.json and data/status.json.
"""
import json
import os
import time
from datetime import datetime, timezone

import requests

RPC_URL = os.environ.get("RPC_URL")
SCAN_SLOTS = int(os.environ.get("SCAN_SLOTS", "40"))  # how many recent slots to scan per run
MAX_EVENTS = 500
EVENTS_PATH = "data/events.json"
STATUS_PATH = "data/status.json"

SYSTEM_PROGRAM = "11111111111111111111111111111111"
NONCE_TYPES = {"advanceNonce", "initializeNonce", "authorizeNonce", "withdrawNonce"}
LARGE_TRANSFER_LAMPORTS = 100 * 1_000_000_000  # 100 SOL

# Programs that are normal to see next to a nonce transaction
FAMILIAR_PROGRAMS = {
    SYSTEM_PROGRAM,
    "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA",   # SPL Token
    "TokenzQdBNbLqP5VEhdkAS6EPFLC1PHnBqCXEpPxuEb",   # Token-2022
    "ATokenGPvbdGVxr1b2hvZbsiqW5xWH25efTNsLJA8knL",  # Associated Token
    "ComputeBudget111111111111111111111111111111",
    "MemoSq4gqABAXKb96qnH8TysNcWxMyWCqXgDLGmfcHr",
    "Memo1UhkJRfHyvLMcVucJwxXeuD728EqVDDwQDxFMNo",
}

SIGNAL_POINTS = {
    "durable_tx": 1,
    "nonce_created": 1,
    "nonce_withdrawn": 1,
    "nonce_authority_changed": 3,
    "third_party_authority": 2,
    "unfamiliar_program": 2,
    "large_sol_transfer": 2,
}


def rpc(method, params):
    """Call the RPC with retries. Returns (result, error)."""
    payload = {"jsonrpc": "2.0", "id": 1, "method": method, "params": params}
    for attempt in range(3):
        try:
            r = requests.post(RPC_URL, json=payload, timeout=60)
            r.raise_for_status()
            data = r.json()
            if "error" in data:
                return None, data["error"]
            return data.get("result"), None
        except Exception as e:  # network or HTTP problem, retry
            last = str(e)
            time.sleep(2 * (attempt + 1))
    return None, last


def analyze(entry, slot, block_time):
    """Return an event dict if the transaction has nonce signals, else None."""
    tx = entry.get("transaction") or {}
    meta = entry.get("meta") or {}
    msg = tx.get("message") or {}
    instructions = msg.get("instructions") or []
    if not instructions:
        return None

    keys = [k["pubkey"] if isinstance(k, dict) else k for k in msg.get("accountKeys", [])]
    if not keys:
        return None
    payer = keys[0]

    signals = set()
    transferred = 0
    nonce_seen = False

    for i, ix in enumerate(instructions):
        if ix.get("programId") != SYSTEM_PROGRAM:
            continue
        parsed = ix.get("parsed")
        if not isinstance(parsed, dict):
            continue
        ix_type = parsed.get("type")
        info = parsed.get("info", {})

        if ix_type in NONCE_TYPES:
            nonce_seen = True
        if ix_type == "advanceNonce" and i == 0:
            signals.add("durable_tx")
            if info.get("nonceAuthority") and info["nonceAuthority"] != payer:
                signals.add("third_party_authority")
        elif ix_type == "initializeNonce":
            signals.add("nonce_created")
        elif ix_type == "authorizeNonce":
            signals.add("nonce_authority_changed")
        elif ix_type == "withdrawNonce":
            signals.add("nonce_withdrawn")
        elif ix_type == "transfer":
            try:
                transferred += int(info.get("lamports", 0))
            except (TypeError, ValueError):
                pass

    if not nonce_seen or not signals:
        return None

    programs = sorted({ix.get("programId") for ix in instructions if ix.get("programId")})
    unfamiliar = [p for p in programs if p not in FAMILIAR_PROGRAMS]
    if unfamiliar:
        signals.add("unfamiliar_program")
    if transferred >= LARGE_TRANSFER_LAMPORTS:
        signals.add("large_sol_transfer")

    score = sum(SIGNAL_POINTS[s] for s in signals)
    severity = "high" if score >= 5 else "medium" if score >= 3 else "low"

    return {
        "time": datetime.fromtimestamp(block_time, tz=timezone.utc).isoformat() if block_time else None,
        "signature": (tx.get("signatures") or [None])[0],
        "slot": slot,
        "fee_payer": payer,
        "programs": unfamiliar,
        "signals": sorted(signals),
        "score": score,
        "severity": severity,
        "failed": meta.get("err") is not None,
    }


def load_events():
    try:
        with open(EVENTS_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return []


def main():
    print("Solana Staging Monitor - collector")

    if not RPC_URL:
        print("ERROR: RPC_URL not found in environment variables.")
        raise SystemExit(1)

    tip, err = rpc("getSlot", [{"commitment": "finalized"}])
    if tip is None:
        print(f"Could not get current slot: {err}")
        raise SystemExit(1)

    first_slot = tip - SCAN_SLOTS + 1
    found, blocks_read = [], 0

    for slot in range(first_slot, tip + 1):
        block, err = rpc("getBlock", [slot, {
            "encoding": "jsonParsed",
            "transactionDetails": "full",
            "maxSupportedTransactionVersion": 0,
            "rewards": False,
            "commitment": "finalized",
        }])
        if block is None:  # skipped slot or temporary error
            continue
        blocks_read += 1
        for entry in block.get("transactions", []):
            event = analyze(entry, slot, block.get("blockTime"))
            if event:
                found.append(event)

    # Merge with history, drop duplicates, newest first
    merged = {e["signature"]: e for e in load_events() if e.get("signature")}
    for e in found:
        merged[e["signature"]] = e
    events = sorted(merged.values(), key=lambda e: e["slot"], reverse=True)[:MAX_EVENTS]

    os.makedirs("data", exist_ok=True)
    with open(EVENTS_PATH, "w", encoding="utf-8") as f:
        json.dump(events, f)
    with open(STATUS_PATH, "w", encoding="utf-8") as f:
        json.dump({
            "updated": datetime.now(timezone.utc).isoformat(),
            "first_slot": first_slot,
            "last_slot": tip,
            "blocks_read": blocks_read,
            "new_events": len(found),
            "total_events": len(events),
        }, f)

    print(f"Scanned slots {first_slot}-{tip} ({blocks_read} blocks), "
          f"{len(found)} nonce events found, {len(events)} stored.")


if __name__ == "__main__":
    main()
