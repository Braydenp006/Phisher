from flask import Flask, request, send_file, make_response, render_template_string, redirect, url_for
import csv
import os
import json
from datetime import datetime
import gspread
from oauth2client.service_account import ServiceAccountCredentials

app = Flask(__name__)

LOG_FILE = "logs/clicks.csv"
LANDING_PAGE = "landing_page.html"
GOOGLE_SHEET_ID = "1hALSUrXjg_qcru93HeSjlbalYr04sFMtLz6xzGR8nvU"

# Setup Google Sheets client
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
creds_json = os.environ.get("GOOGLE_CREDS")
creds_dict = json.loads(creds_json)
creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
client = gspread.authorize(creds)
sheet = client.open_by_key(GOOGLE_SHEET_ID).sheet1

def is_defender(user_agent):
    defender_signatures = ["Microsoft", "Defender", "Outlook", "PreFetch"]
    return any(sig.lower() in user_agent.lower() for sig in defender_signatures)

def log_click(uid):
    timestamp = datetime.now().isoformat()
    ip = request.remote_addr
    user_agent = request.user_agent.string

    if is_defender(user_agent):
        return  # Skip logging if it's Microsoft Defender or similar

    row = [uid, timestamp]
    os.makedirs("logs", exist_ok=True)
    with open(LOG_FILE, "a", newline="") as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(row)

    sheet.append_row(row)

@app.route("/track")
def track():
    uid = request.args.get("uid", "UNKNOWN")
    log_click(uid)
    return redirect(url_for("landing", uid=uid))

@app.route("/landing")
def landing():
    uid = request.args.get("uid", "UNKNOWN")
    with open(LANDING_PAGE, "r") as f:
        html = f.read()
    html = html.replace("</form>", f'<input type="hidden" name="uid" value="{uid}" /></form>')
    return render_template_string(html)

@app.route("/")
def index():
    return "Click tracker is running."

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    app.run(host="0.0.0.0", port=port)
