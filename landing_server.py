from flask import Flask, request, redirect, url_for, render_template_string
import json
from datetime import datetime
import os
import csv
import gspread
from oauth2client.service_account import ServiceAccountCredentials

app = Flask(__name__)

GOOGLE_SHEET_ID = "1hALSUrXjg_qcru93HeSjlbalYr04sFMtLz6xzGR8nvU"
LANDING_PAGE = "landing_page.html"
LOG_FILE = "logs/clicked_users.csv"

# Setup Google Sheets API
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
creds_json = os.environ.get("GOOGLE_CREDS")
creds_dict = json.loads(creds_json)
creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
client = gspread.authorize(creds)

# Use the BotClickData sheet for all logs
bot_sheet = client.open_by_key(GOOGLE_SHEET_ID).worksheet("BotClickData")

def log_all_clicks(uid, ip, user_agent, headers):
    timestamp = datetime.now().isoformat()
    headers_str = " | ".join(f"{k}: {v}" for k, v in headers.items())
    row = [uid, timestamp, ip, user_agent, headers_str]

    # Save locally as well for backup
    os.makedirs("logs", exist_ok=True)
    with open(LOG_FILE, "a", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(row)

    # Append to Google Sheet
    bot_sheet.append_row(row)

@app.route("/track")
def track():
    uid = request.args.get("uid", "UNKNOWN")
    user_agent = request.user_agent.string
    ip = request.remote_addr
    headers = dict(request.headers)

    log_all_clicks(uid, ip, user_agent, headers)

    return redirect(url_for("landing", uid=uid))

@app.route("/landing")
def landing():
    uid = request.args.get("uid", "UNKNOWN")
    with open(LANDING_PAGE, "r") as f:
        html = f.read()
    html = html.replace("</form>", f'<input type="hidden" name="uid" value="{uid}"></form>')
    return render_template_string(html)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    app.run(host="0.0.0.0", port=port)
