"""TriGuard Dashboard API — Flask backend with SSE streaming."""
import os, json, time, queue, threading
from datetime import datetime, timezone
from flask import Flask, request, jsonify, Response, send_from_directory
from flask_cors import CORS
from dotenv import load_dotenv
from web3 import Web3
import requests as http_requests

load_dotenv()

app = Flask(__name__, static_folder="dashboard")
CORS(app)

# ── Shared state ──────────────────────────────────────────────────────────────
events_log   = []          # capped at 500
alerts_list  = []          # consensus alerts
flagged_txs  = []          # transactions flagged & sent to KeeperHub
risk_results = []          # risk assessment results returned from KeeperHub
agent_status = {
    "agent1": {"status":"offline","last_seen":None,"blocks":0,"alerts":0,"port":9002},
    "agent2": {"status":"offline","last_seen":None,"blocks":0,"alerts":0,"port":9003},
    "agent3": {"status":"offline","last_seen":None,"blocks":0,"alerts":0,"port":9004},
}
votes_table  = {}          # tx_hash -> {agent: verdict}
sse_queues   = []
lock         = threading.Lock()
LAST_BLOCK   = {"n": 0}

w3 = Web3(Web3.HTTPProvider(os.getenv("ALCHEMY_URL", "")))
GAS_THRESH   = 2           # gwei

# ── Helpers ───────────────────────────────────────────────────────────────────
def now_iso():
    return datetime.now(timezone.utc).isoformat()

def push_event(ev):
    """Append to log and fan-out to all SSE clients."""
    with lock:
        events_log.append(ev)
        if len(events_log) > 500:
            events_log.pop(0)
        dead = []
        for q in sse_queues:
            try:  q.put_nowait(json.dumps(ev))
            except: dead.append(q)
        for q in dead:
            try: sse_queues.remove(q)
            except: pass

# ── Block watcher thread ──────────────────────────────────────────────────────
def watcher():
    print("[Watcher] started")
    while True:
        try:
            blk = w3.eth.get_block("latest", full_transactions=True)
            bn  = blk.number
            if bn > LAST_BLOCK["n"]:
                LAST_BLOCK["n"] = bn
                for tx in blk.transactions[:5]:
                    h       = tx.hash.hex()
                    gas     = round(float(w3.from_wei(tx.gasPrice,"gwei")), 4)
                    verdict = "suspicious" if gas > GAS_THRESH else "clean"
                    for ag in ["agent1","agent2","agent3"]:
                        push_event({"type":"vote","agent":ag,"tx_hash":h,
                                    "gas_gwei":gas,"verdict":verdict,
                                    "block":bn,"timestamp":now_iso()})
                        with lock:
                            agent_status[ag]["status"]   = "online"
                            agent_status[ag]["last_seen"] = now_iso()
                            agent_status[ag]["blocks"]    = (agent_status[ag]["blocks"] or 0) + 1
                    # consensus
                    with lock:
                        votes_table.setdefault(h, {})\
                            .update({ag: verdict for ag in ["agent1","agent2","agent3"]})
                        sus = sum(1 for v in votes_table[h].values() if v=="suspicious")
                        if sus >= 2 and not any(a["tx_hash"]==h for a in alerts_list):
                            al = {"tx_hash":h,"gas_gwei":gas,"block":bn,
                                  "votes":sus,"timestamp":now_iso(),"consensus":f"{sus}-of-3"}
                            alerts_list.append(al)
                            for ag in ["agent1","agent2","agent3"]:
                                agent_status[ag]["alerts"] = (agent_status[ag]["alerts"] or 0) + 1
                    if sus >= 2:
                        push_event({"type":"alert","tx_hash":h,"gas_gwei":gas,
                                    "block":bn,"votes":sus,"timestamp":now_iso()})
        except Exception as e:
            print(f"[Watcher] {e}")
        time.sleep(12)

threading.Thread(target=watcher, daemon=True).start()

# ── REST ──────────────────────────────────────────────────────────────────────
@app.route("/api/status")
def api_status():
    with lock:
        votes = [e for e in events_log if e["type"]=="vote"]
        return jsonify({
            "agents":        agent_status,
            "total_alerts":  len(alerts_list),
            "total_events":  len(events_log),
            "suspicious":    sum(1 for e in votes if e.get("verdict")=="suspicious"),
            "clean":         sum(1 for e in votes if e.get("verdict")=="clean"),
            "latest_block":  LAST_BLOCK["n"],
            "network":       "Ethereum Sepolia",
            "timestamp":     now_iso(),
        })

@app.route("/api/events")
def api_events():
    limit = int(request.args.get("limit", 100))
    with lock:
        return jsonify(list(reversed(events_log[-limit:])))

@app.route("/api/alerts")
def api_alerts():
    with lock:
        return jsonify(list(reversed(alerts_list[-50:])))

@app.route("/api/agent/event", methods=["POST"])
def agent_event():
    ev = request.json or {}
    ev["timestamp"] = now_iso()
    push_event(ev)
    ag = ev.get("agent")
    if ag and ag in agent_status:
        with lock:
            agent_status[ag]["status"]   = "online"
            agent_status[ag]["last_seen"] = ev["timestamp"]
    return jsonify({"ok": True})

@app.route("/api/stream")
def sse():
    q = queue.Queue(maxsize=200)
    with lock: sse_queues.append(q)
    def gen():
        yield 'data: {"type":"connected"}\n\n'
        while True:
            try:    yield f"data: {q.get(timeout=28)}\n\n"
            except queue.Empty: yield ": heartbeat\n\n"
    return Response(gen(), mimetype="text/event-stream",
                    headers={"Cache-Control":"no-cache","X-Accel-Buffering":"no"})

@app.route("/api/axl")
def api_axl():
    """Return live AXL topology for all 3 nodes."""
    nodes = [
        {"agent": "agent1", "api_port": 9002, "key_prefix": "54b5ba77"},
        {"agent": "agent2", "api_port": 9003, "key_prefix": "2f7005fa"},
        {"agent": "agent3", "api_port": 9004, "key_prefix": "96121463"},
    ]
    result = []
    for n in nodes:
        try:
            r = http_requests.get(f"http://127.0.0.1:{n['api_port']}/topology", timeout=2)
            topo = r.json()
            peers_up = sum(1 for p in topo.get("peers", []) if p.get("up"))
            result.append({
                "agent":      n["agent"],
                "api_port":   n["api_port"],
                "key_prefix": n["key_prefix"],
                "running":    True,
                "peers_up":   peers_up,
                "tree_size":  len(topo.get("tree", [])),
                "ipv6":       topo.get("our_ipv6", ""),
                "public_key": topo.get("our_public_key", ""),
            })
        except Exception:
            result.append({"agent": n["agent"], "api_port": n["api_port"],
                           "running": False, "peers_up": 0})
    return jsonify(result)

@app.route("/")
def idx(): return send_from_directory("dashboard","index.html")

@app.route("/<path:p>")
def static_f(p): return send_from_directory("dashboard", p)

@app.route('/api/risk', methods=['POST'])
def risk_webhook():
    # force=True accepts JSON regardless of Content-Type header (KeeperHub compatibility)
    data = request.get_json(force=True, silent=True) or {}
    
    event = {
        "type": "risk_assessment",
        "tx_hash": data.get("tx_hash", "KeeperHub Analysis"),
        "risk_level": data.get("riskLevel", "unknown"),
        "risk_score": data.get("riskScore", 0),
        "reasoning": data.get("reasoning", ""),
        "factors": data.get("factors", []),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "agent": "KEEPERHUB AI"
    }
    
    with lock:
        risk_results.append(event)
        if len(risk_results) > 50:
            risk_results.pop(0)
    
    push_event(event)
    return jsonify({"status": "received", "event": event})

@app.route('/api/flagged', methods=['GET'])
def api_flagged():
    """Return all transactions that were flagged and sent to KeeperHub."""
    with lock:
        return jsonify(list(reversed(flagged_txs[-30:])))

@app.route('/api/risk/results', methods=['GET'])
def api_risk_results():
    """Return all KeeperHub risk assessment results."""
    with lock:
        return jsonify(list(reversed(risk_results[-30:])))

@app.route('/api/flag', methods=['POST'])
def flag_tx():
    """Called by keeper.py when a tx is sent to KeeperHub for assessment."""
    data = request.get_json(force=True, silent=True) or {}
    record = {
        "tx_hash": data.get("tx_hash", ""),
        "gas_price_gwei": data.get("gas_price_gwei", 0),
        "detected_by": data.get("detected_by", ""),
        "consensus": data.get("consensus", ""),
        "contract_address": data.get("contract_address", ""),
        "sender_address": data.get("sender_address", ""),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    with lock:
        flagged_txs.append(record)
        if len(flagged_txs) > 50:
            flagged_txs.pop(0)
    push_event({"type": "flagged", **record})
    return jsonify({"status": "ok"})

if __name__ == "__main__":
    print("TriGuard Dashboard → http://localhost:5050")
    app.run(host="0.0.0.0", port=5050, debug=False, threaded=True)
