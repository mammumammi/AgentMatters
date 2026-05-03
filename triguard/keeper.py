import requests
import os

def log_alert(tx_hash, gas_price_gwei, agent_id):
    api_key = os.getenv("KEEPERHUB_API_KEY")
    if not api_key or api_key == "your_keeperhub_key_here":
        print(f"[KeeperHub] No API key — logging locally:")
        print(f"  ALERT: tx={tx_hash[:16]}... gas={gas_price_gwei:.1f} gwei")
        return

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    payload = {
        "description": f"TriGuard: suspicious tx {tx_hash[:16]}",
        "metadata": {
            "tx_hash": tx_hash,
            "gas_price_gwei": gas_price_gwei,
            "detected_by": agent_id,
            "consensus": "2-of-3 agents flagged"
        }
    }
    try:
        r = requests.post(
            "https://api.keeperhub.com/v1/jobs",
            json=payload,
            headers=headers,
            timeout=5
        )
        print(f"[KeeperHub] Logged alert: {r.status_code}")
    except Exception as e:
        print(f"[KeeperHub] Error: {e}")