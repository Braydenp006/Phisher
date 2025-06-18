from flask import Flask, request, redirect, url_for, render_template_string
import csv
import os
import json
from datetime import datetime, timedelta
import gspread
from oauth2client.service_account import ServiceAccountCredentials

app = Flask(__name__)

GOOGLE_SHEET_ID = "1hALSUrXjg_qcru93HeSjlbalYr04sFMtLz6xzGR8nvU"
LANDING_PAGE = "landing_page.html"
LOG_FILE = "logs/clicked_users.csv"

# Google Sheets setup
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
creds_json = os.environ.get("GOOGLE_CREDS")
creds_dict = json.loads(creds_json)
creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
client = gspread.authorize(creds)
sheet = client.open_by_key(GOOGLE_SHEET_ID).sheet1

# In-memory deduplication map: { uid: last_timestamp }
recent_clicks = {}

def is_bot(user_agent):
    bot_keywords = ["Microsoft", "Defender", "Outlook", "bot", "scanner", "prefetch", "curl", "wget"]
    return any(bot.lower() in user_agent.lower() for bot in bot_keywords)

def should_log(uid):
    now = datetime.now()
    if uid in recent_clicks:
        delta = now - recent_clicks[uid]
        if delta.total_seconds() < 5:
            return False
    recent_clicks[uid] = now
    return True

def log_email(uid):
    timestamp = datetime.now().isoformat()
    row = [uid, timestamp]

    os.makedirs("logs", exist_ok=True)
    with open(LOG_FILE, "a", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(row)

    sheet.append_row(row)

@app.route("/track")
def track():
    uid = request.args.get("uid", "UNKNOWN")
    user_agent = request.user_agent.string.lower()
    ip_address = request.remote_addr

    # Known bot indicators in User-Agent
    bot_indicators = [
        "microsoft", "defender", "prefetch", "bingpreview",
        "healthcheck", "outlook", "curl", "wget", "bot"
    ]

    # Known Microsoft Defender IP ranges (sample, partial list)
    defender_ips = [
        "13.66.", "13.67.", "20.36.", "20.37.", "20.38.",
        "20.40.", "20.41.", "20.42.", "52.174.", "40.94."
    ]

    is_bot_ua = any(bot in user_agent for bot in bot_indicators)
    is_defender_ip = any(ip_address.startswith(prefix) for prefix in defender_ips)

    if is_bot_ua or is_defender_ip:
        print(f"Filtered bot click from IP: {ip_address}, UA: {user_agent}")
        return redirect(url_for("landing", uid=uid))

    # Log only real user clicks
    log_email(uid)
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
