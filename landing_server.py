from flask import Flask, request, redirect, url_for, render_template_string
import csv
import os
import json
import re
from datetime import datetime, timedelta
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from collections import defaultdict

app = Flask(__name__)

GOOGLE_SHEET_ID = os.environ.get("GOOGLE_SHEET_ID")
LANDING_PAGE = "landing_page.html"
LOG_FILE = "logs/clicked_users.csv"

# Deduplication setup
recent_clicks = defaultdict(lambda: datetime.min)
DEDUPLICATION_WINDOW = timedelta(seconds=3)

# Setup Google Sheets API
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
creds_json = os.environ.get("GOOGLE_CREDS")
creds_dict = json.loads(creds_json)
creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
client = gspread.authorize(creds)

# Main user clicks sheet
sheet_user = client.open_by_key(GOOGLE_SHEET_ID).sheet1
# Bot clicks sheet
sheet_bot = client.open_by_key(GOOGLE_SHEET_ID).worksheet("BotClickData")

def is_bot(request):
    user_agent = request.user_agent.string

    # Chrome version
    match = re.search(r"Chrome/(\d+)", user_agent)
    if match:
        version = int(match.group(1))
        if version < 134:
            return True

    # Sec-Ch-Ua check
    sec_ch_ua = request.headers.get("Sec-Ch-Ua", "")
    if 'Not;A Brand' in sec_ch_ua and "Google Chrome" not in sec_ch_ua:
        return True

    # Local/internal IP check
    ip = request.headers.get("Cf-Connecting-Ip", "") or request.remote_addr or ""
    if ip.startswith("127.") or ip.startswith("192.") or ip == "":
        return True

    # User-Agent keywords
    bot_keywords = ["Microsoft", "Defender", "Outlook", "bot", "scanner", "prefetch", "curl", "wget"]
    if any(bot_kw.lower() in user_agent.lower() for bot_kw in bot_keywords):
        return True

    return False

def log_user_click(uid):
    now = datetime.now()
    if now - recent_clicks[uid] < DEDUPLICATION_WINDOW:
        return  # Skip duplicate click
    recent_clicks[uid] = now

    timestamp = now.isoformat()
    row = [uid, timestamp]

    os.makedirs("logs", exist_ok=True)
    with open(LOG_FILE, "a", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(row)

    try:
        sheet_user.append_row(row)
    except Exception as e:
        print(f"Error writing to user sheet: {e}")

def log_bot_click(info):
    try:
        sheet_bot.append_row(info)
    except Exception as e:
        print(f"Error writing to bot sheet: {e}")

@app.route("/track")
def track():
    uid = request.args.get("uid", "UNKNOWN")
    user_agent = request.user_agent.string
    headers = request.headers

    info = [
        uid,
        datetime.now().isoformat(),
        request.remote_addr or "",
        user_agent,
        headers.get("Host", ""),
        headers.get("Cf-Connecting-Ip", ""),
        headers.get("Cf-Ipcountry", ""),
        headers.get("Cf-Ray", ""),
        headers.get("Sec-Ch-Ua", ""),
        headers.get("Sec-Fetch-Site", ""),
    ]

    if is_bot(request):
        log_bot_click(info)
    else:
        log_user_click(uid)

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
