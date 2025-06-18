from flask import Flask, request, send_file, make_response, render_template_string, redirect, url_for
import csv
import os
import json
from datetime import datetime
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from collections import defaultdict

app = Flask(__name__)

LOG_FILE = "logs/events.csv"
LANDING_PAGE = "landing_page.html"
GOOGLE_SHEET_ID = "1hALSUrXjg_qcru93HeSjlbalYr04sFMtLz6xzGR8nvU"

# Setup Google Sheets client
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
creds_json = os.environ.get("GOOGLE_CREDS")
creds_dict = json.loads(creds_json)
creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
client = gspread.authorize(creds)
sheet = client.open_by_key(GOOGLE_SHEET_ID).sheet1

# Tracker to filter out known Defender opens
open_counts = defaultdict(int)

def is_defender(user_agent):
    defender_signatures = ["Microsoft", "Defender", "Outlook"]
    return any(sig.lower() in user_agent.lower() for sig in defender_signatures)

def log_event(event_type, uid, extra_data=None):
    timestamp = datetime.now().isoformat()
    ip = request.remote_addr
    user_agent = request.user_agent.string

    if event_type == "email_open" and is_defender(user_agent):
        open_counts[uid] += 1
        if open_counts[uid] <= 2:
            return  # skip first 2 opens if they're from Microsoft

    row = [timestamp, uid, event_type]
    os.makedirs("logs", exist_ok=True)
    with open(LOG_FILE, "a", newline="") as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(row)

    # Update spreadsheet to maintain a flat format
    cell = sheet.find(uid) if uid != "UNKNOWN" else None
    if not cell:
        new_row = [uid, "yes" if event_type == "email_open" else "", "yes" if event_type == "click" else ""]
        sheet.append_row(new_row)
    else:
        row_num = cell.row
        if event_type == "email_open":
            sheet.update_cell(row_num, 2, "yes")
        elif event_type == "click":
            sheet.update_cell(row_num, 3, "yes")

@app.route("/track")
def track():
    uid = request.args.get("uid", "UNKNOWN")
    log_event("click", uid)
    return redirect(url_for("landing", uid=uid))

@app.route("/landing")
def landing():
    uid = request.args.get("uid", "UNKNOWN")
    with open(LANDING_PAGE, "r") as f:
        html = f.read()
    html = html.replace("</form>", f'<input type="hidden" name="uid" value="{uid}" /></form>')
    return render_template_string(html)

@app.route("/submit", methods=["POST"])
def submit():
    uid = request.form.get("uid", "UNKNOWN")
    log_event("form_submit", uid)
    return """
    <h1>Thank you!</h1>
    <p>Your payroll verification has been received.</p>
    """

@app.route("/open")
def open_pixel():
    uid = request.args.get("uid", "UNKNOWN")
    log_event("email_open", uid)
    pixel = b'GIF89a\x01\x00\x01\x00\x80\x00\x00\x00\x00\x00\xff\xff\xff!\xf9\x04\x01\x00\x00\x00\x00,\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02\x02D\x01\x00;'
    response = make_response(pixel)
    response.headers.set("Content-Type", "image/gif")
    response.headers.set("Cache-Control", "no-cache, no-store, must-revalidate")
    return response

@app.route("/")
def index():
    return "Tracker is running."

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    app.run(host="0.0.0.0", port=port)
