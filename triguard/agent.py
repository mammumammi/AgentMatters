import os
import sys
import time
import json
import requests
from web3 import Web3
from dotenv import load_dotenv
from axl import send_vote, receive_messages
from consensus import cast_vote
from keeper import log_alert

load_dotenv()

DASHBOARD_URL = "http://127.0.0.1:5050/api/agent/event"

def post_dashboard(ev):
    try:
        requests.post(DASHBOARD_URL, json=ev, timeout=2)
    except Exception:
        pass

# ── Config from args ──────────────────────────────────────────
AGENT_ID  = sys.argv[1]          # agent1 / agent2 / agent3
AXL_PORT  = int(sys.argv[2])     # 9002 / 9003 / 9004
MY_KEY    = sys.argv[3]          # this agent's own public key

# All peer keys
ALL_KEYS = {
    "agent1": os.getenv("PEER_KEY_1"),
    "agent2": os.getenv("PEER_KEY_2"),
    "agent3": os.getenv("PEER_KEY_3"),
}

# Peers = everyone except myself
PEER_KEYS = {
    name: key
    for name, key in ALL_KEYS.items()
    if key != MY_KEY
}

# ── Chain setup ───────────────────────────────────────────────
w3 = Web3(Web3.HTTPProvider(os.getenv("ALCHEMY_URL")))
GAS_THRESHOLD_GWEI = 2  # Sepolia testnet has low gas, keep threshold low

alerted = set()  # don't double-alert same tx

def broadcast(tx_hash, verdict):
    import json
    msg_str = json.dumps({
        "from": AGENT_ID,
        "tx_hash": tx_hash,
        "verdict": verdict
    })
    for peer_name, peer_key in PEER_KEYS.items():
        ok = send_vote(AXL_PORT, peer_key, msg_str)
        status = "✓" if ok else "✗"
        print(f"[{AGENT_ID}] {status} Sent {verdict} → {peer_name}")
def process_incoming():
    """Drain AXL inbox and process peer votes"""
    messages = receive_messages(AXL_PORT)
    for msg in messages:
        payload = msg.get("payload", {})
        tx_hash = payload.get("tx_hash")
        sender  = payload.get("from")
        verdict = payload.get("verdict")

        if not all([tx_hash, sender, verdict]):
            continue

        print(f"[{AGENT_ID}] ← Received {verdict} vote "
              f"from {sender} for {tx_hash[:12]}...")

        result = cast_vote(tx_hash, sender, verdict)

        if result == "ALERT" and tx_hash not in alerted:
            alerted.add(tx_hash)
            print(f"[{AGENT_ID}] 🔴 CONSENSUS: ALERT on {tx_hash[:12]}!")
            log_alert(tx_hash, 0, AGENT_ID)

def check_block():
    try:
        block = w3.eth.get_block("latest", full_transactions=True)
        print(f"\n[{AGENT_ID}] 📦 Block {block.number} "
              f"— {len(block.transactions)} txs")

        # Report block check to dashboard
        post_dashboard({"type": "block", "agent": AGENT_ID,
                        "block": block.number, "tx_count": len(block.transactions)})

        for tx in block.transactions[:5]:  # check first 5 txs
            tx_hash   = tx.hash.hex()
            gas_gwei  = round(float(w3.from_wei(tx.gasPrice, "gwei")), 4)
            verdict   = "suspicious" if gas_gwei > GAS_THRESHOLD_GWEI \
                        else "clean"
            
            # Extract deep transaction data for KeeperHub Risk Assessment
            tx_data = {
                "contract_address": tx.to if tx.to else "",
                "sender_address": tx.get("from", ""),
                "transaction_value": str(tx.value),
                "transaction_calldata": tx.input.hex() if hasattr(tx.input, 'hex') else "0x"
            }

            if verdict == "suspicious":
                print(f"[{AGENT_ID}] 🚨 High gas: "
                      f"{gas_gwei:.2f} gwei → {tx_hash[:12]}...")
            else:
                print(f"[{AGENT_ID}] ✓ Clean: "
                      f"{gas_gwei:.2f} gwei → {tx_hash[:12]}...")

            # Report vote to dashboard
            post_dashboard({"type": "vote", "agent": AGENT_ID,
                            "tx_hash": tx_hash, "gas_gwei": gas_gwei,
                            "verdict": verdict, "block": block.number})

            # Cast own vote locally
            result = cast_vote(tx_hash, AGENT_ID, verdict)

            # Broadcast to peers via AXL
            broadcast(tx_hash, verdict)

            # Check if own vote already triggers consensus
            if result == "ALERT" and tx_hash not in alerted:
                alerted.add(tx_hash)
                print(f"[{AGENT_ID}] 🔴 CONSENSUS: ALERT!")
                log_alert(tx_hash, gas_gwei, AGENT_ID, tx_data=tx_data)

    except Exception as e:
        print(f"[{AGENT_ID}] RPC error: {e}")

# ── Main loop ─────────────────────────────────────────────────
if __name__ == "__main__":
    print(f"[{AGENT_ID}] TriGuard started on AXL port {AXL_PORT}")
    print(f"[{AGENT_ID}] Watching peers: {list(PEER_KEYS.keys())}")
    while True:
        check_block()
        process_incoming()
        time.sleep(15)