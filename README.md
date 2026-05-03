# TriGuard 🛡️

**TriGuard** is a decentralized, multi-agent Ethereum monitoring system. It leverages a cluster of independent AI agents to monitor the Sepolia testnet for suspicious transactions in real-time. By utilizing **Gensyn AXL** for peer-to-peer communication and **KeeperHub** for automated execution, TriGuard eliminates single points of failure in blockchain monitoring.

## 🏆 Hackathon Tracks
Built for ETHOnline 2026, targeting:
- **Gensyn AXL**
- **KeeperHub**

---

## 🧠 Architecture & How We Use the Tech

### 1. Gensyn AXL (Peer-to-Peer Communication)
We completely avoid centralized message brokers (like Kafka or Redis) for agent communication. 
Instead, we run 3 separate **AXL nodes** that peer with the Gensyn Yggdrasil backbone (`34.46.48.224`, `136.111.135.206`). 
- When an agent (e.g., Agent 1) analyzes a transaction and determines a verdict, it sends a payload to its local AXL node via the `/send` endpoint.
- The AXL node securely routes this message across the P2P mesh network to the other agents' AXL nodes.
- Agents constantly poll their local AXL `/recv` endpoint to gather peer votes and independently calculate consensus.
*(Code reference: `axl.py` and `agent.py`)*

### 2. KeeperHub (Execution Layer)
Once the agents reach a majority consensus (2-of-3 votes) that a transaction is suspicious (e.g., high gas price anomaly), they must trigger an alert.
Instead of hardcoding the alerting logic into the agents, we use **KeeperHub**.
- The consensus triggers a POST request to a **KeeperHub Webhook** using a `wfb_` User Key.
- KeeperHub acts as our execution layer, taking the consensus data and running a configured workflow (e.g., routing a notification to Discord, creating an audit log, or potentially triggering an automated smart contract pause).
*(Code reference: `keeper.py`)*

---

## 🚀 How to Run Locally

### Prerequisites
- Python 3.9+
- Gensyn AXL binary (`node`)

### Step 1: Start the AXL Mesh Network
Open 3 separate terminals and start the AXL nodes. They are configured to connect to the Gensyn backbone and share a virtual gVisor `tcp_port: 7000`.
```bash
cd axl
./node -config config1.json
./node -config config2.json
./node -config config3.json
```

### Step 2: Start the Dashboard API
In a new terminal, start the Flask backend which watches the blockchain and aggregates agent data.
```bash
cd triguard
source venv/bin/activate
python3 dashboard_api.py
```
*Visit `http://localhost:5050` to view the stunning GSAP-powered dashboard.*

### Step 3: Start the Agents
In 3 separate terminals, launch the monitoring agents.
```bash
cd triguard
source venv/bin/activate
python3 agent.py agent1 9002 54b5ba77fdb29c1adee936ce2436c1111cbea196e46a1a07107dfd62ae285335
python3 agent.py agent2 9003 2f7005fae681c47de877347d447d41ce7a6f01d648eb8617353bd54b9649fdbd
python3 agent.py agent3 9004 96121463ab01f53e855ce89902912447c68e1a3f73e6ceb67e80a7f065e3732d
```

As the agents run, you will see them communicate via AXL, reach consensus, and trigger the KeeperHub webhook in real-time on the dashboard!
