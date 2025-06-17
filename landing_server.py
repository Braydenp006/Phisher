from flask import Flask, request, send_file
import csv
import os
from datetime import datetime

app = Flask(__name__)

LOG_FILE = "logs/clicks.csv"
LANDING_PAGE = "landing_page.html"

@app.route("/track")
def track():
    uid = request.args.get("uid", "UNKNOWN")
    timestamp = datetime.now().isoformat()

    os.makedirs("logs", exist_ok=True)
    with open(LOG_FILE, "a", newline="") as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow([timestamp, uid, request.remote_addr, request.user_agent.string])

    return send_file(LANDING_PAGE)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000)