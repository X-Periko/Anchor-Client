import json
from pathlib import Path

QUEUE_PATH = Path.home() / ".config" / "anchor_queue.json"

def load_qeue():
    if not QUEUE_PATH.exists():
        return []
    else:
        with open(QUEUE_PATH, "r") as f:
            return json.load(f)

def save_qeue(qeue: list):
    with open(QUEUE_PATH, "w") as f:
        json.dump(qeue, f)

def enqeue(method: str, endpoint: str, payload: dict):
    qeue = load_qeue()
    qeue.append({"method":method, "endpoint":endpoint, "payload":payload})
    save_qeue(qeue=qeue)