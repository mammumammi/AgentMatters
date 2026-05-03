import requests
import os
import json
from datetime import datetime, timezone

KEEPERHUB_WEBHOOK_URL = os.getenv("KEEPERHUB_WEBHOOK_URL", "")
KEEPERHUB_API_KEY     = os.getenv("KEEPERHUB_API_KEY", "")

def log_alert(tx_hash, gas_price_gwei, agent_id, tx_data=None, votes=1, consensus="1-of-3"):
    """Send a consensus alert to KeeperHub webhook and the local dashboard."""

    payload = {
        "event":           "suspicious_transaction",
        "tx_hash":         tx_hash,
        "gas_price_gwei":  float(gas_price_gwei),
        "detected_by":     agent_id,
        "consensus":       consensus,
        "votes":           votes,
        "network":         "Ethereum Sepolia",
        "timestamp":       datetime.now(timezone.utc).isoformat(),
    }
    
    # Merge the deep transaction data so KeeperHub can assess it
    if tx_data:
        payload.update(tx_data)

    # ── Notify dashboard that this tx was flagged & sent to KeeperHub ─────────
    try:
        requests.post(
            "https://triguard.onrender.com/api/flag",
            json={**payload, **(tx_data or {})},
            timeout=3
        )
    except Exception:
        pass

    # ── Post to dashboard API ─────────────────────────────────────────────
    try:
        requests.post(
            "http://127.0.0.1:5050/api/agent/event",
            json={**payload, "type": "alert", "agent": agent_id},
            timeout=3
        )
    except Exception:
        pass  # dashboard may not be running

    # ── Post to KeeperHub ─────────────────────────────────────────────────
    if not KEEPERHUB_WEBHOOK_URL:
        print(f"[KeeperHub] No webhook URL set — skipping")
        return

    # Try multiple auth formats (KeeperHub docs are inconsistent)
    headers_options = [
        {"Authorization": f"Bearer {KEEPERHUB_API_KEY}", "Content-Type": "application/json"},
        {"Authorization": KEEPERHUB_API_KEY,              "Content-Type": "application/json"},
        {"X-API-Key":     KEEPERHUB_API_KEY,              "Content-Type": "application/json"},
    ]

    for headers in headers_options:
        try:
            r = requests.post(
                KEEPERHUB_WEBHOOK_URL,
                json=payload,
                headers=headers,
                timeout=8
            )
            if r.status_code in (200, 201, 202, 204):
                print(f"[KeeperHub] ✓ {r.status_code} — alert delivered for {tx_hash[:12]}")
                return
            elif r.status_code == 401:
                print(f"[KeeperHub] 401 with {list(headers.keys())[0]} — trying next auth format")
                continue
            else:
                print(f"[KeeperHub] {r.status_code}: {r.text[:120]}")
                return
        except Exception as e:
            print(f"[KeeperHub] Error: {e}")
            return

    print(f"[KeeperHub] ✗ All auth formats failed — check API key in dashboard")