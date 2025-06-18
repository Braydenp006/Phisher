from flask import Flask, request, redirect
import csv
import os
from datetime import datetime

app = Flask(__name__)
LOG_FILE = "logs/full_click_log.csv"

@app.route("/track")
def track():
    uid = request.args.get("uid", "unknown@example.com")
    ip = request.remote_addr
    user_agent = request.user_agent.string
    timestamp = datetime.now().isoformat()

    os.makedirs("logs", exist_ok=True)
    with open(LOG_FILE, "a", newline="") as f:
        writer = csv.writer(f)
        writer.writerow([uid, ip, timestamp, user_agent])

    return redirect("/landing")  # Replace with your actual page route

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    app.run(host="0.0.0.0", port=port)
