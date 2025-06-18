from flask import Flask, request, jsonify
from datetime import datetime, timedelta
import csv
import os
import threading

app = Flask(__name__)
LOG_FILE = "logs/activity.csv"
os.makedirs("logs", exist_ok=True)

# In-memory store for tracking counts and timestamps of opens
open_tracker = {}
lock = threading.Lock()

# Parameters
IGNORE_FIRST_N = 2
TRACKING_WINDOW_SECONDS = 60 * 5  # 5 minutes window to reset counts

# Known scanning user agents (case-insensitive)
SCANNER_USER_AGENTS = [
    "Microsoft Outlook",        # Outlook web preview user agent often used by Defender
    "Microsoft Office/16.0",    # MS Office/Defender UA pattern
    "Microsoft Defender",
    "OutlookService",
    "MSIPC",
    "microsoft-safe-links"
]

def is_scanner(user_agent):
    if not user_agent:
        return False
    ua_lower = user_agent.lower()
    for pattern in SCANNER_USER_AGENTS:
        if pattern.lower() in ua_lower:
            return True
    return False

def clean_old_entries():
    """Remove entries older than tracking window."""
    cutoff = datetime.now() - timedelta(seconds=TRACKING_WINDOW_SECONDS)
    with lock:
        for key in list(open_tracker.keys()):
            last_time, count = open_tracker[key]
            if last_time < cutoff:
                del open_tracker[key]

def should_log_open(uid, ip, user_agent):
    """Return True if this open event should be logged, False if ignored."""
    # Ignore known scanners completely
    if is_scanner(user_agent):
        return False

    now = datetime.now()
    key = (uid, ip)
    with lock:
        clean_old_entries()
        if key not in open_tracker:
            open_tracker[key] = (now, 1)
            return False  # First open ignored
        else:
            last_time, count = open_tracker[key]
            count += 1
            open_tracker[key] = (now, count)
            if count <= IGNORE_FIRST_N:
                return False  # Ignore first N opens
            else:
                return True  # Log from (N+1)th open onwards

def log_event(event_type, uid, data=None):
    with open(LOG_FILE, "a", newline="") as f:
        writer = csv.writer(f)
        writer.writerow([datetime.now().isoformat(), uid, event_type, data or ""])

@app.route('/log', methods=['POST'])
def log():
    uid = request.args.get('uid', 'UNKNOWN')
    event = request.args.get('event', 'UNKNOWN')
    ip = request.remote_addr
    user_agent = request.user_agent.string

    if event == 'open':
        if should_log_open(uid, ip, user_agent):
            log_event(event, uid)
            return jsonify({"status": "logged"})
        else:
            # Ignored due to scanner or first 2 opens
            return jsonify({"status": "ignored"})
    else:
        # Log all other events immediately
        log_event(event, uid)
        return jsonify({"status": "logged"})

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    app.run(host="0.0.0.0", port=port)
