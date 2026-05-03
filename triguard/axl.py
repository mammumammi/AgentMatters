import requests

def send_vote(axl_port, destination_key, payload_str):
    """
    /send is fire-and-forget raw binary.
    Encode our vote as UTF-8 bytes and send.
    """
    try:
        response = requests.post(
            f"http://127.0.0.1:{axl_port}/send",
            headers={
                "X-Destination-Peer-Id": destination_key,
                "Content-Type": "application/octet-stream"
            },
            data=payload_str.encode("utf-8"),  # raw bytes, not JSON
            timeout=5
        )
        if response.status_code == 200:
            sent = response.headers.get("X-Sent-Bytes", "?")
            print(f"[AXL] ✓ Sent {sent} bytes → {destination_key[:8]}...")
            return True
        else:
            print(f"[AXL] ✗ {response.status_code}: {response.text[:80]}")
            return False
    except Exception as e:
        print(f"[AXL] Error: {e}")
        return False

def receive_messages(axl_port):
    """Poll /recv for inbound raw binary messages"""
    messages = []
    try:
        response = requests.get(
            f"http://127.0.0.1:{axl_port}/recv",
            timeout=3
        )
        if response.status_code == 200:
            sender = response.headers.get("X-From-Peer-Id", "unknown")
            try:
                import json
                payload = json.loads(response.content.decode("utf-8"))
                messages.append({"from": sender, "payload": payload})
            except:
                pass
    except:
        pass
    return messages