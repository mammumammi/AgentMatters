votes = {}

def cast_vote(tx_hash, agent_id, verdict):
    if tx_hash not in votes:
        votes[tx_hash] = {}
    votes[tx_hash][agent_id] = verdict
    return check_consensus(tx_hash)

def check_consensus(tx_hash):
    v = votes.get(tx_hash, {})
    suspicious = sum(1 for val in v.values() if val == "suspicious")
    clean = len(v) - suspicious
    if suspicious >= 1:   # trigger on 1 vote for demo
        return "ALERT"
    if clean >= 1:
        return "CLEAN"
    return None