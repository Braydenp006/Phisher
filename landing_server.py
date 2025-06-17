from flask import Flask, request, send_file
import csv
import os
import json
from datetime import datetime
import gspread
from oauth2client.service_account import ServiceAccountCredentials

app = Flask(__name__)

LOG_FILE = "logs/clicks.csv"
LANDING_PAGE = "landing_page.html"
GOOGLE_SHEET_ID = "1hALSUrXjg_qcru93HeSjlbalYr04sFMtLz6xzGR8nvU"  # Replace this with your actual Sheet ID

# Google Sheets logging using environment variable
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
creds_json = os.environ.get("GOOGLE_CREDS")
creds_dict = json.loads(creds_json)
creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
client = gspread.authorize(creds)
sheet = client.open_by_key(GOOGLE_SHEET_ID).sheet1

def append_to_google_sheet(row):
    sheet.append_row(row)

@app.route("/track")
def track():
    uid = request.args.get("uid", "UNKNOWN")
    timestamp = datetime.now().isoformat()
    ip = request.remote_addr
    user_agent = request.user_agent.string

    row = [timestamp, uid, ip, user_agent]

    os.makedirs("logs", exist_ok=True)
    with open(LOG_FILE, "a", newline="") as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(row)

    append_to_google_sheet(row)

    return send_file(LANDING_PAGE)

@app.route("/")
def index():
    return send_file(LANDING_PAGE)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    app.run(host="0.0.0.0", port=port)
